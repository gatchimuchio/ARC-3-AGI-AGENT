# Tests

Install the locked project and development dependencies, then run both supported
test entry points:

```bash
uv sync --locked
uv run python -m unittest discover -s tests/unit -p "test_*.py" -v
uv run python -m pytest -q tests/unit
```

For more information on tests, please see the [tests documentation](https://three.arcprize.org/docs#testing).
