# AgentOpsCLI

**AgentOpsCLI** is a commercial-grade, production-oriented AI coding agent and terminal operations platform implemented entirely in Python.

It provides an agentic pair-programming loop with native local Ollama support, OpenAI-compatible APIs, Anthropic Messages API, transparent multi-provider routing, intelligent context discovery, and safe agent tools.

---

## Key Features

- **Unified Multi-Provider Support**: Seamlessly interact with local models via Ollama (`llama3.1:8b`, `qwen2.5-coder:14b`), OpenAI (`gpt-4o`, `o3-mini`), Anthropic (`claude-3-5-sonnet`), and Google Gemini.
- **Intelligent Model Router**: Real-time scoring by observed latency, cost, and health, with automatic circuit breaking and bounded fallback.
- **Local-Only Privacy Mode**: Strict privacy enforcement (`LOCAL_ONLY=true`) guarantees that no code or project data ever leaves your machine.
- **Project-Aware Context Engine**: Respects `.gitignore` and default exclusions (`.git`, `node_modules`, `__pycache__`, `.venv`, binaries, and large files), ranking files by relevance to fit strict token budgets.
- **Safe Agent Tools**:
  - `read_file`: Workspace containment and directory traversal protection.
  - `edit_file`: Generates colored unified diff previews and enforces explicit user confirmation before writing changes atomically.
  - `run_command`: Enforces approval before execution, applies strict timeouts, and automatically masks credentials and secrets in output.
- **Session & Cost Management**: Persistent atomic storage in `~/.agentops/sessions`, resuming past conversations, and tracking input/output tokens and estimated costs.
- **Rich Terminal Interface**: Syntax-highlighted code blocks and diffs, real-time streaming, and interactive slash commands (`/help`, `/model`, `/provider`, `/sessions`, `/cost`, `/doctor`, `/clear`).

---

## Architecture Overview

```text
agentops/
├── cli/
│   ├── main.py              # Command-line entrypoint & argument parser
│   └── commands/            # doctor, profile, mcp, auth, tasks, sessions
├── core/
│   ├── agent.py             # AgentOpsEngine main agentic execution loop
│   ├── conversation.py      # Conversation turns and system prompts
│   ├── events.py            # Event emitter and streaming lifecycle
│   └── errors.py            # Typed error hierarchy
├── providers/
│   ├── base.py              # BaseProvider interface & data models
│   ├── ollama.py            # Native Ollama client (streaming & local inference)
│   ├── openai_compatible.py # OpenAI / DeepSeek / vLLM adapter
│   ├── anthropic.py         # Anthropic Messages API adapter
│   ├── gemini.py            # Google Gemini adapter
│   └── registry.py          # Provider lifecycle registry
├── router/
│   ├── router.py            # SmartRouter transparent routing engine
│   ├── scoring.py           # Latency, cost, and reliability scoring
│   ├── policies.py          # Task complexity classification & privacy rules
│   └── fallback.py          # Circuit breaking and bounded retries
├── context/
│   ├── indexer.py           # Workspace file discovery and filtering
│   ├── ignore.py            # Gitignore pattern matching
│   ├── token_budget.py      # Token limits and safe truncation
│   └── builder.py           # Relevance ranking & delimited context assembler
├── tools/
│   ├── base.py              # BaseTool interface & JSON schema generation
│   ├── read_file.py         # Safe file reader
│   ├── edit_file.py         # Diff preview & atomic file editor
│   ├── run_command.py       # Sandboxed command execution & secret masking
│   ├── diff.py              # Unified diff generation & ANSI formatting
│   └── registry.py          # Tool discovery and execution registry
├── sessions/
│   ├── store.py             # Atomic session persistence
│   ├── history.py           # Session & Turn models
│   └── costs.py             # Token & USD cost tracking
├── security/
│   ├── paths.py             # Path boundary validation & traversal protection
│   ├── approvals.py         # Explicit human approval enforcement
│   └── secrets.py           # Secret & credential redaction
└── ui/
    ├── terminal.py          # Rich terminal renderer
    ├── repl.py              # Interactive prompt loop
    ├── themes.py            # Dark & Light palettes
    └── shortcuts.py         # Slash command handlers
```

---

## Requirements & Installation

### Requirements
- Python 3.10, 3.11, or 3.12
- Git

### Installation

Install via pip in editable development mode:

```bash
git clone https://github.com/mohdshamii/AgentOps-CLI.git
cd AgentOps-CLI
pip install -r requirements-dev.txt
pip install -e .
```

Verify the installation:
```bash
agentops --version
agentops doctor
```

The CLI executable is registered as `agentops`, with backward-compatible aliases `mycodecli` and `agentopscli`.

---

## Quickstart & Daily Use

### 1. Interactive Session (Default)
Start the interactive REPL:
```bash
agentops
```

Inside the REPL, type queries or use slash commands:
- `/help` — Display shortcuts and commands
- `/model <name>` — Inspect or switch the active model
- `/provider <name>` — Inspect or switch the active provider
- `/sessions` — List saved conversations
- `/cost` — View token usage and estimated cost
- `/doctor` — Run runtime health diagnostics
- `/clear` — Clear the terminal screen
- `/exit` — Exit safely

### 2. Print / Pipe Mode (Non-interactive)
```bash
agentops -p "Explain the router architecture in agentops/router/router.py"
```

Output formatted as JSON for CI or automation:
```bash
agentops -p "List all functions in calculator.py" --output-format json
```

### 3. Provider Setup & Profiles

Configure a profile quickly:
```bash
# Set up for local Ollama
agentops profile init --provider ollama --model llama3.1:8b --goal coding

# Auto-detect best provider
agentops profile auto
```

---

## Configuration Reference

Configuration can be set via `.env`, environment variables, `.agentops-profile.json`, or `agentops.yaml`.

| Variable | Description | Default |
|---|---|---|
| `PREFERRED_PROVIDER` | Default provider (`ollama`, `openai`, `anthropic`, `gemini`) | `ollama` |
| `ROUTER_MODE` | Router mode (`smart`, `fixed`) | `smart` |
| `ROUTER_STRATEGY` | Routing strategy (`balanced`, `latency`, `cost`) | `balanced` |
| `ROUTER_FALLBACK` | Automatically fall back on error (`true`, `false`) | `true` |
| `LOCAL_ONLY` | Enforce strict local-only privacy (`true`, `false`) | `false` |
| `OLLAMA_BASE_URL` | Ollama service endpoint | `http://localhost:11434` |
| `OPENAI_API_KEY` | OpenAI API key | None |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key | None |
| `GEMINI_API_KEY` | Google Gemini API key | None |

---

## Security & Privacy Guarantees

1. **Path Boundary Containment**: Every file operation strictly validates that target paths resolve within the active workspace root. Path traversal attempts (`../../`) raise immediate security violations.
2. **Explicit Approval Workflow**:
   - File edits show a unified diff and require user confirmation before applying.
   - Terminal commands show the exact command and working directory and require explicit approval.
   - The agent cannot approve its own actions.
3. **Secret Redaction**: API keys and tokens matching credential patterns are masked automatically in command output and logs.

---

## Testing

Run the test suite:
```bash
pytest -v
```

All 80 tests cover unit components and end-to-end integration workflows without external network dependencies.

---

## License

This project incorporates third-party open-source components with verified MIT and BSD-family licenses. For full details, see [THIRD_PARTY_LICENSES](THIRD_PARTY_LICENSES).
