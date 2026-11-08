"""
Central Agentic loop and query execution engine for AgentOpsCLI.
"""

import time
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any, AsyncIterator
import httpx

from agentops.config.schema import AgentOpsConfig
from agentops.config.loader import load_config
from agentops.core.conversation import DEFAULT_SYSTEM_PROMPT, build_conversation_messages
from agentops.core.events import EventEmitter, EventType
from agentops.core.errors import AgentOpsError, ProviderError
from agentops.providers.base import BaseProvider, LLMMessage, LLMResponse, StreamChunk
from agentops.providers.registry import ProviderRegistry
from agentops.router.router import SmartRouter
from agentops.context.indexer import RepositoryIndexer
from agentops.context.builder import ContextBuilder
from agentops.tools.registry import ToolRegistry, create_default_tool_registry
from agentops.security.approvals import ApprovalManager, PermissionMode
from agentops.sessions.history import Session, SessionTurn, ToolExecutionRecord
from agentops.sessions.store import SessionStore
from agentops.sessions.costs import CostTracker


class AgentOpsEngine:
    def __init__(
        self,
        config: Optional[AgentOpsConfig] = None,
        workspace_root: Optional[Path] = None,
        session_id: Optional[str] = None,
        permission_mode: PermissionMode = PermissionMode.DEFAULT,
    ):
        self.workspace_root = workspace_root or Path.cwd()
        self.config = config or load_config(self.workspace_root)
        self.events = EventEmitter()

        # Approval manager
        self.approval_manager = ApprovalManager(mode=permission_mode)

        # Registries
        self.provider_registry = ProviderRegistry(self.config)
        self.tool_registry = create_default_tool_registry(
            workspace_root=self.workspace_root,
            approval_manager=self.approval_manager,
        )

        # Context builder
        indexer = RepositoryIndexer(
            workspace_root=self.workspace_root,
            max_file_size_bytes=self.config.context.per_file_max_bytes,
            custom_ignore_patterns=self.config.context.ignore_patterns,
        )
        self.context_builder = ContextBuilder(
            indexer=indexer,
            max_context_tokens=self.config.context.max_tokens,
            per_file_max_tokens=self.config.context.per_file_max_tokens,
        )

        # Router
        self.router = SmartRouter(
            strategy=self.config.router.strategy,
            local_only=self.config.router.local_only,
        )

        # Sessions and cost
        self.session_store = SessionStore()
        self.cost_tracker = CostTracker()

        # Load or initialize session
        if session_id:
            existing = self.session_store.load_session(session_id)
            self.current_session = existing or Session(session_id=session_id, workspace_dir=str(self.workspace_root))
        else:
            self.current_session = Session(workspace_dir=str(self.workspace_root))

    async def execute_prompt(
        self,
        prompt: str,
        stream: bool = True,
        model_override: Optional[str] = None,
        provider_override: Optional[str] = None,
        stream_callback: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Executes a single agent turn with context gathering, provider routing,
        tool execution, and session recording.
        """
        start_time = time.time()
        self.events.emit(EventType.PROMPT_START, {"prompt": prompt})

        # 1. Build context
        context_pkg = self.context_builder.build_context(prompt)

        # 2. Assemble messages
        messages = build_conversation_messages(
            turns=self.current_session.turns,
            current_prompt=prompt,
            context_text=context_pkg.prompt_context,
            max_history_turns=self.config.session.max_history_turns,
        )

        # 3. Route to provider
        if provider_override:
            p_obj = self.config.providers.get(provider_override)
            chosen_model = model_override or (p_obj.big_model if p_obj else "auto")
            provider_name = provider_override
            model_name = chosen_model
        else:
            route_meta = await self.router.route(
                messages=[{"role": m.role, "content": m.get_text_content()} for m in messages],
                model=model_override,
                stream=stream,
            )
            provider_name = route_meta["provider"]
            model_name = model_override or route_meta["model"]

        provider = self.provider_registry.get_provider(provider_name)
        tool_schemas = self.tool_registry.get_schemas()

        assistant_text = ""
        tool_executions: List[ToolExecutionRecord] = []
        input_tokens = 0
        output_tokens = 0
        cost_usd = 0.0

        try:
            # 4. Stream or non-stream execution
            if stream and not tool_schemas:
                async for chunk in provider.stream(
                    messages=messages,
                    model=model_name,
                    system=DEFAULT_SYSTEM_PROMPT,
                    tools=tool_schemas,
                ):
                    delta = chunk.delta_text
                    if delta:
                        assistant_text += delta
                        self.events.emit(EventType.STREAM_CHUNK, {"delta": delta})
                        if stream_callback:
                            stream_callback(delta)
                    if chunk.usage:
                        input_tokens = chunk.usage.input_tokens
                        output_tokens = chunk.usage.output_tokens
                        cost_usd = chunk.usage.estimated_cost
            else:
                resp = await provider.chat(
                    messages=messages,
                    model=model_name,
                    system=DEFAULT_SYSTEM_PROMPT,
                    tools=tool_schemas,
                )
                assistant_text = resp.content
                input_tokens = resp.usage.input_tokens
                output_tokens = resp.usage.output_tokens
                cost_usd = resp.usage.estimated_cost

                # Handle tool calls if returned by model
                if resp.tool_calls:
                    for tc in resp.tool_calls:
                        self.events.emit(EventType.TOOL_CALL_DETECTED, {"tool": tc.name, "args": tc.arguments})
                        tool_res = await self.tool_registry.execute(
                            tc.name,
                            tc.arguments,
                            context={"workspace_root": self.workspace_root, "approval_manager": self.approval_manager},
                        )
                        self.events.emit(EventType.TOOL_EXECUTED, {"tool": tc.name, "result": tool_res})
                        tool_executions.append(
                            ToolExecutionRecord(
                                tool_name=tc.name,
                                arguments=tc.arguments,
                                result=tool_res,
                            )
                        )

                    # Follow-up with tool results to synthesize final answer
                    followup_messages = list(messages)
                    followup_messages.append(LLMMessage(role="assistant", content=assistant_text or "Running tool..."))
                    for te in tool_executions:
                        followup_messages.append(
                            LLMMessage(
                                role="user",
                                content=f"Tool '{te.tool_name}' result:\n{te.result}",
                            )
                        )
                    final_resp = await provider.chat(
                        messages=followup_messages,
                        model=model_name,
                        system=DEFAULT_SYSTEM_PROMPT,
                    )
                    assistant_text = final_resp.content
                    output_tokens += final_resp.usage.output_tokens
                    cost_usd += final_resp.usage.estimated_cost

            # Record router success
            latency_ms = (time.time() - start_time) * 1000.0
            self.router.record_result(provider_name, latency_ms=latency_ms, success=True)

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000.0
            self.router.record_result(provider_name, latency_ms=latency_ms, success=False)
            self.events.emit(EventType.ERROR, {"error": str(e)})
            raise ProviderError(f"Error executing with {provider_name}/{model_name}: {e}") from e

        # Calculate / track costs
        if cost_usd == 0.0 and (input_tokens > 0 or output_tokens > 0):
            cost_usd = provider.calculate_cost(input_tokens, output_tokens, model_name)

        self.cost_tracker.record_usage(
            model=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
        )

        # 5. Create turn and persist
        turn = SessionTurn(
            turn_id=str(uuid.uuid4()),
            user_prompt=prompt,
            assistant_response=assistant_text,
            model=model_name,
            provider=provider_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            tool_executions=tool_executions,
        )
        self.current_session.add_turn(turn)

        if self.config.session.persistence:
            self.session_store.save_session(self.current_session)

        self.events.emit(EventType.TURN_COMPLETE, {"turn_id": turn.turn_id, "cost_usd": cost_usd})

        return {
            "response": assistant_text,
            "provider": provider_name,
            "model": model_name,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost_usd,
            "tool_executions": [t.__dict__ for t in tool_executions],
            "context_files": context_pkg.included_files,
            "session_id": self.current_session.session_id,
        }
