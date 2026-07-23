# Tests

Install the locked project and development dependencies, then run the P1
contract and OFFLINE integration gates:

```bash
uv sync --locked
uv run python -m unittest discover -s tests/unit -p "test_*.py" -v
uv run python -m pytest -q tests
uv run ruff check \
  arc3_agi_agent \
  agents/__init__.py \
  agents/recorder.py \
  tests/conftest.py \
  tests/unit
uv run python sample_main.py --all-samples --max-actions 1
```

The final command is a one-action execution-path smoke test, not a P2 level
completion score. Current phase boundaries and the complete validation contract
are documented in the repository root `AGENTS.md`.
