# Contributing to QA Pipe

Thank you for your interest in contributing!

## Quick start

```bash
git clone https://github.com/yourname/qa-pipe.git
cd qa-pipe
uv sync
cp config.example.json config.json
uv run alembic upgrade head
uv run pytest
```

## Workflow

1. **Fork** the repository and create a branch: `git checkout -b feat/your-feature`
2. **Write tests first** or alongside your changes — all new code must be covered
3. Ensure `uv run pytest` passes with no failures
4. **Open a Pull Request** against `main` with a clear description of what and why

## Code style

- Python 3.11+, type hints everywhere
- No comments unless the _why_ is non-obvious
- Keep functions small and focused
- `uv run ruff check src/` should produce no errors (if ruff is installed)

## Commit messages

Use conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.

## Reporting bugs

Use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.yml).  
For security issues — see [SECURITY.md](SECURITY.md).
