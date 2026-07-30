from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
BUILDER_PATH = REPOSITORY_ROOT / "scripts" / "build_kaggle_submission.py"
BUILDER_SPEC = importlib.util.spec_from_file_location(
    "arc3_kaggle_builder_test_target",
    BUILDER_PATH,
)
assert BUILDER_SPEC is not None and BUILDER_SPEC.loader is not None
BUILDER = importlib.util.module_from_spec(BUILDER_SPEC)
BUILDER_SPEC.loader.exec_module(BUILDER)
VALIDATOR_PATH = (
    REPOSITORY_ROOT / "scripts" / "validate_kaggle_submission.py"
)
VALIDATOR_SPEC = importlib.util.spec_from_file_location(
    "arc3_kaggle_validator_test_target",
    VALIDATOR_PATH,
)
assert VALIDATOR_SPEC is not None and VALIDATOR_SPEC.loader is not None
sys.path.insert(0, str(VALIDATOR_PATH.parent))
try:
    VALIDATOR = importlib.util.module_from_spec(VALIDATOR_SPEC)
    VALIDATOR_SPEC.loader.exec_module(VALIDATOR)
finally:
    sys.path.remove(str(VALIDATOR_PATH.parent))


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
    assert '"arc-agi==' not in install
    assert '"python-dotenv==' not in install
    assert "if competition_rerun:" in install
    assert 'Path("/kaggle/working/submission.parquet")' in install
    assert "fallback_bytes = zlib.decompress(" in install
    assert "fallback_path.write_bytes(fallback_bytes)" in install
    assert BUILDER.OFFICIAL_PLACEHOLDER_PARQUET_SHA256 in install
    assert str(BUILDER.OFFICIAL_PLACEHOLDER_PARQUET_SIZE) in install
    assert '"INSTALL_EXCEPTION"' in install
    assert '"/kaggle/working/arc3_install_status.json"' in install

    payload = sources["verify-runtime-payload"]
    assert '"PAYLOAD_EXCEPTION"' in payload
    assert '"/kaggle/working/arc3_payload_status.json"' in payload

    competition = sources["execute-generic-runtime"]
    assert "KAGGLE_IS_COMPETITION_RERUN" in competition
    assert "to_parquet" not in competition
    assert "arc3_agi_agent.generic_competition_runner" in competition
    assert '"main.py"' not in competition
    assert '"--agent"' not in competition
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
    check_keywords = [
        keyword
        for keyword in subprocess_calls[0].keywords
        if keyword.arg == "check"
    ]
    assert len(check_keywords) == 1
    assert isinstance(check_keywords[0].value, ast.Constant)
    assert check_keywords[0].value.value is False
    assert 'runtime_status["runner_returncode"]' in competition
    assert '"RUNNER_NONZERO"' in competition
    assert '"BOOTSTRAP_EXCEPTION"' in competition
    assert "traceback.print_exc()" in competition
    assert '"/kaggle/working/arc3_runtime_status.json"' in competition

    placeholder = sources["write-official-placeholder"]
    assert 'data=[["1_0", "1", True, 1]]' in placeholder
    assert (
        'columns=["row_id", "game_id", "end_of_game", "score"]'
        in placeholder
    )
    assert "dry-run" not in placeholder
    assert BUILDER.ACTION_BUDGET == 128
    assert "generic_competition_runner.py" in BUILDER.RUNTIME_MODULES


def test_kaggle_runtime_archive_is_exact_generic_runtime_closure() -> None:
    excluded_infrastructure = {
        "canonical_artifact.py",
        "compiled_policy.py",
        "initial_state_compiler.py",
        "negative_transfer.py",
        "p22_evaluator.py",
        "p_bundle.py",
        "p_compiler_v2.py",
        "p_evaluator.py",
        "p_registry.py",
    }

    resolved = BUILDER._validate_relative_import_closure()
    _, manifest = BUILDER.build_runtime_archive()

    assert resolved == BUILDER.RUNTIME_MODULES
    assert excluded_infrastructure.isdisjoint(BUILDER.RUNTIME_MODULES)
    assert manifest["runtime_entry_modules"] == list(
        BUILDER.RUNTIME_ENTRY_MODULES
    )
    assert manifest["runtime_modules"] == list(BUILDER.RUNTIME_MODULES)
    assert manifest["teacher_included"] is False
    assert manifest["known_sample_policy_included"] is False
    assert manifest["runtime_identity_routing_included"] is False


def test_kaggle_runtime_archive_import_smoke_uses_current_session_api() -> None:
    runtime_archive, _ = BUILDER.build_runtime_archive()

    result = VALIDATOR._runtime_import_smoke(runtime_archive)

    assert VALIDATOR.RUNTIME_SMOKE_EXPECTED_OUTPUT == "WIN:2:True:True"
    assert result["passed"] is True
    assert result["returncode"] == 0
    assert result["stdout"] == VALIDATOR.RUNTIME_SMOKE_EXPECTED_OUTPUT
    assert result["stderr"] == ""


def test_kaggle_validator_accepts_external_notebook_report_path() -> None:
    external_path = (
        Path(REPOSITORY_ROOT.anchor)
        / "arc3-external-validation"
        / "submission.ipynb"
    )

    assert VALIDATOR._report_notebook_path(
        external_path
    ) == external_path.as_posix()


def test_kaggle_runtime_allowlist_rejects_extraneous_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        BUILDER,
        "RUNTIME_MODULES",
        BUILDER.RUNTIME_MODULES + ("negative_transfer.py",),
    )

    with pytest.raises(
        RuntimeError,
        match="KAGGLE_RUNTIME_ALLOWLIST_EXTRANEOUS:negative_transfer",
    ):
        BUILDER._validate_relative_import_closure()


def test_kaggle_runtime_allowlist_rejects_quarantined_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        BUILDER,
        "RUNTIME_MODULES",
        BUILDER.RUNTIME_MODULES + ("compiled_policy.py",),
    )

    with pytest.raises(
        RuntimeError,
        match="KAGGLE_RUNTIME_QUARANTINED_MODULE_ALLOWED:compiled_policy",
    ):
        BUILDER._validate_relative_import_closure()
