"""
Tool registry for discovering, registering, and executing tools.
"""

from typing import Dict, List, Optional, Any
from agentops.tools.base import BaseTool
from agentops.tools.read_file import ReadFileTool
from agentops.tools.edit_file import EditFileTool
from agentops.tools.run_command import RunCommandTool


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def list_tools(self) -> List[BaseTool]:
        return list(self._tools.values())

    def get_schemas(self, allowed_tools: Optional[List[str]] = None, disallowed_tools: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        schemas = []
        for name, tool in self._tools.items():
            if allowed_tools and name not in allowed_tools:
                continue
            if disallowed_tools and name in disallowed_tools:
                continue
            schemas.append(tool.to_json_schema())
        return schemas

    async def execute(self, name: str, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        tool = self.get(name)
        if not tool:
            return {"error": f"Tool '{name}' not found"}
        return await tool.execute(arguments, context)


def create_default_tool_registry(workspace_root=None, approval_manager=None) -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(ReadFileTool(workspace_root=workspace_root))
    reg.register(EditFileTool(workspace_root=workspace_root, approval_manager=approval_manager))
    reg.register(RunCommandTool(workspace_root=workspace_root, approval_manager=approval_manager))
    return reg

