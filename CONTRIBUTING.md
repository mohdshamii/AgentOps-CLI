# Contributing to AgentOpsCLI

Thank you for your interest in contributing to **AgentOpsCLI**!

## Development Setup

1. **Prerequisites**:
   - Python 3.10 or higher
   - Git

2. **Clone and Install**:
   ```bash
   git clone https://github.com/your-username/codeforkcli.git
   cd codeforkcli
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\Activate.ps1
   pip install -r requirements-dev.txt
   pip install -e .
   ```

3. **Verify Environment**:
   ```bash
   agentops doctor
   pytest -v
   ```

## Coding Standards

- **Language**: Python 3.10+ with type annotations on public functions and classes.
- **Style**: Follow PEP 8 guidelines. Write clear docstrings.
- **Safety**:
  - Always validate paths with `resolve_safe_path()` before file access.
  - Require user approval through `ApprovalManager` for file modifications and shell commands.
  - Mask secrets in command output and logs using `mask_secrets()`.
  - Maintain privacy boundaries (respect `LOCAL_ONLY` flags).

## Running Tests

Run the test suite before submitting pull requests:
```bash
pytest -v
```

All 80+ unit and integration tests must pass cleanly without network dependencies.

## Pull Request Guidelines

1. Create a feature branch from `main`.
2. Ensure changes are accompanied by unit tests.
3. Verify that `agentops doctor --json` and `pytest -v` pass.
4. Keep commits descriptive and atomic.

## Security Vulnerability Reporting

If you discover a security vulnerability or path traversal issue, please report it privately via security advisory rather than opening a public issue.

