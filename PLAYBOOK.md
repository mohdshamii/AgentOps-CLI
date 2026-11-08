# AgentOpsCLI Local Agent Playbook

This playbook is a practical guide to running **AgentOpsCLI** with a local model (Ollama) or cloud providers, working safely, and achieving strong day-to-day results in Python.

---

## 1. What You Have

- A fast, native Python agent loop that can read/write files safely, run terminal commands with explicit approval, and assist with coding workflows.
- A local provider profile system (`agentops profile init`, `agentops profile recommend`, `agentops profile auto`).
- Runtime checks (`agentops doctor`) and report generation (`agentops doctor --out reports/doctor-runtime.json`).
- Resumable sessions and cost tracking stored in `~/.agentops/sessions`.

---

## 2. Daily Start (Fast Path)

Run this in your project root:

```powershell
agentops
```

For quick command-line queries without entering the interactive REPL:

```powershell
# Quick question or code explanation
agentops -p "Explain how the router works in agentops/router/router.py"

# Output as JSON
agentops -p "Summarize project structure" --output-format json
```

---

## 3. One-Time Setup

### 3.1 Initialize a local profile

```powershell
agentops profile init --provider ollama --model llama3.1:8b
```

Or let AgentOpsCLI recommend the best local model for your goal:

```powershell
agentops profile init --provider ollama --goal coding
```

Preview recommendations:

```powershell
agentops profile recommend --goal coding
```

### 3.2 Confirm profile file

```powershell
Get-Content .\.agentops-profile.json
```

### 3.3 Validate environment

```powershell
agentops doctor
```

---

## 4. Health and Diagnostics

### 4.1 Human-readable checks

```powershell
agentops doctor
```

### 4.2 JSON diagnostics (automation/logging)

```powershell
agentops doctor --json
```

### 4.3 Persist runtime report

```powershell
agentops doctor --out reports/doctor-runtime.json
```

---

## 5. Provider Modes

### 5.1 Local mode (Ollama)

```powershell
agentops profile init --provider ollama --model llama3.1:8b
agentops
```

Expected behavior:
- No API key required.
- `OLLAMA_BASE_URL` defaults to `http://localhost:11434`.

### 5.2 OpenAI mode

```powershell
agentops profile init --provider openai --api-key sk-... --model gpt-4o
agentops
```

### 5.3 Anthropic Claude mode

```powershell
agentops profile init --provider anthropic --api-key sk-ant-... --model claude-3-5-sonnet-20241022
agentops
```

---

## 6. Safe Working Rules

1. Run `agentops doctor` before debugging provider connectivity issues.
2. Review unified diff previews carefully before approving file modifications.
3. Keep `.agentops-profile.json` and `.env` local (already ignored by `.gitignore`).
4. Use `LOCAL_ONLY=true` in `.env` if working in privacy-restricted repositories.
