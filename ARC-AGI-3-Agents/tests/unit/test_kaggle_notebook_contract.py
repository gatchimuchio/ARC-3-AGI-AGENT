from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
BUILDER_PATH = REPOSITORY_ROOT / "scripts" / "build_kaggle_submission.py"
BUILDER_SPEC = importlib.util.spec_from_file_location(
    "arc3_kaggle_builder_test_target",
    BUILDER_PATH,
)
assert BUILDER_SPEC is not None and BUILDER_SPEC.loader is not None
BUILDER = importlib.util.module_from_spec(BUILDER_SPEC)
BUILDER_SPEC.loader.exec_module(BUILDER)


def _sources_by_id(notebook: dict[str, object]) -> dict[str, str]:
    cells = notebook["cells"]
    assert isinstance(cells, list)
    return {
        str(cell["id"]): str(cell["source"])
        for cell in cells
        if isinstance(cell, dict)
    }


def test_kaggle_notebook_matches_official_submission_shape() -> None:
    notebook, _ = BUILDER.build_notebook()
    cells = notebook["cells"]
    assert isinstance(cells, list)
    assert notebook["nbformat"] == 4
    assert notebook["nbformat_minor"] == 4
    assert [cell["cell_type"] for cell in cells] == ["code"] * 4
    assert [cell["id"] for cell in cells] == [
        "install-official-offline-wheels",
        "verify-runtime-payload",
        "execute-generic-runtime",
        "write-official-placeholder",
    ]

    sources = _sources_by_id(notebook)
    install = sources["install-official-offline-wheels"]
    assert "if wheel_dir.is_dir()" in install
    assert 'elif os.getenv("KAGGLE_IS_COMPETITION_RERUN")' in install
    assert "raise FileNotFoundError" in install
    assert '"arc-agi"' in install
    assert '"python-dotenv"' in install
    assert "==" not in install

    competition = sources["execute-generic-runtime"]
    assert "KAGGLE_IS_COMPETITION_RERUN" in competition
    assert "to_parquet" not in competition
    subprocess_calls = [
        node
        for node in ast.walk(ast.parse(competition))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "subprocess"
        and node.func.attr == "run"
    ]
    assert len(subprocess_calls) == 1
    assert all(
        keyword.arg != "timeout"
        for keyword in subprocess_calls[0].keywords
    )

    placeholder = sources["write-official-placeholder"]
    assert 'data=[["1_0", "1", True, 1]]' in placeholder
    assert (
        'columns=["row_id", "game_id", "end_of_game", "score"]'
        in placeholder
    )
    assert "dry-run" not in placeholder
    assert BUILDER.ACTION_BUDGET == 128
