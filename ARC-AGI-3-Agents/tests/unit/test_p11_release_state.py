from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from arc3_agi_agent.schema import digest_object
from arc3_agi_agent.teacher.p11_regression import (
    _SECRET_PATTERNS,
    P10_REPRODUCIBILITY_AUDIT_DIGEST_PREFIX,
    compile_p10_reproducibility_audit,
    load_p10_reproducibility_audit,
)
from arc3_agi_agent.teacher.p11_release import (
    inspect_reproducible_wheels,
    p11_initial_state_descriptors,
)


def _digest_report(
    body: dict[str, object],
    prefix: str,
) -> dict[str, object]:
    return {
        **body,
        "content_digest": prefix + digest_object(body),
    }


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, sort_keys=True),
        encoding="utf-8",
    )


def test_secret_scan_does_not_treat_embedded_task_suffix_as_key() -> None:
    openai_style_pattern = _SECRET_PATTERNS[0]
    task_identifier = b"H47-promote-ta" + b"sk-" + (b"x" * 24)
    key_assignment = b"OPENAI_API_KEY=" + b"sk-" + (b"x" * 24)

    assert openai_style_pattern.search(task_identifier) is None
    assert openai_style_pattern.search(key_assignment) is not None


def test_p10_reproducibility_audit_requires_exact_s5_and_s6_bytes(
    tmp_path: Path,
) -> None:
    s5_body: dict[str, object] = {
        "all_complete": True,
        "completed_levels": 183,
        "environment_count": 25,
        "error_count": 0,
        "deterministic_seed": 0,
    }
    s6_body: dict[str, object] = {
        "status": "COMPLETE",
        "covered_level_count": 183,
        "covered_game_count": 25,
        "total_measurement_count": 14_336,
        "exception_count": 0,
        "generalization_claim": "MEASURED_NOT_PROVEN",
    }
    s5 = _digest_report(
        s5_body,
        "arc3_s5_rendered_runtime_closure:",
    )
    s6 = _digest_report(
        s6_body,
        "arc3_s6_perturbation_measurement:",
    )
    paths = {
        name: tmp_path / f"{name}.json"
        for name in ("s5_primary", "s5_reproduction", "s6_primary", "s6_reproduction")
    }
    for name in ("s5_primary", "s5_reproduction"):
        _write_json(paths[name], s5)
    for name in ("s6_primary", "s6_reproduction"):
        _write_json(paths[name], s6)

    report = compile_p10_reproducibility_audit(
        s5_primary_path=paths["s5_primary"],
        s5_reproduction_path=paths["s5_reproduction"],
        s6_primary_path=paths["s6_primary"],
        s6_reproduction_path=paths["s6_reproduction"],
    )

    assert report["status"] == "PASS"
    assert report["s5_byte_equal"] is True
    assert report["s6_byte_equal"] is True
    output = tmp_path / "audit.json"
    _write_json(output, report)
    loaded = load_p10_reproducibility_audit(output)
    assert loaded["content_digest"].startswith(
        P10_REPRODUCIBILITY_AUDIT_DIGEST_PREFIX
    )

    paths["s6_reproduction"].write_text(
        paths["s6_reproduction"].read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="S6_PERTURBATION_MEASUREMENT_BYTE_MISMATCH"):
        compile_p10_reproducibility_audit(
            s5_primary_path=paths["s5_primary"],
            s5_reproduction_path=paths["s5_reproduction"],
            s6_primary_path=paths["s6_primary"],
            s6_reproduction_path=paths["s6_reproduction"],
        )


def test_p11_initial_state_is_empty_versioned_and_identity_free() -> None:
    states = p11_initial_state_descriptors()

    assert states["P0"]["body_version"] == "s5-rendered-history-mlp-v1"
    assert states["P0"]["parameter_count"] == 4_269_485
    assert states["P0"]["runtime_identity_free"] is True
    assert (
        states["P0"]["runtime_artifact_contains_training_examples"]
        is False
    )
    assert not any(states["J0"]["initial_counts"].values())
    assert states["M0"]["version"] == 0
    assert states["M0"]["active_entry_count"] == 0
    assert states["M0"]["archive_entry_count"] == 0
    assert states["M0"]["retained_snapshot_versions"] == [0]


def _write_test_wheel(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "arc3_agi_agent/bundles/s5_rendered_policy_v1.json",
            "{}",
        )
        archive.writestr(
            "arc3_agi_agent/bundles/s5_rendered_policy_v1.npz",
            b"weights",
        )
        archive.writestr(
            "arc3_agi_agent/teacher/compiler.py",
            "# development compiler\n",
        )
        archive.writestr(
            "arc_agi_3_agents-0.1.0.dist-info/WHEEL",
            "Wheel-Version: 1.0\n"
            "Generator: setuptools (83.0.0)\n"
            "Root-Is-Purelib: true\n"
            "Tag: py3-none-any\n",
        )


def test_wheel_audit_requires_reproducible_runtime_bundle(
    tmp_path: Path,
) -> None:
    primary = tmp_path / "package.whl"
    reproduction = tmp_path / "package-reproduction.whl"
    _write_test_wheel(primary)
    _write_test_wheel(reproduction)

    report = inspect_reproducible_wheels(primary, reproduction)

    assert report["byte_reproducible"] is True
    assert report["contains_runtime_policy_manifest"] is True
    assert report["contains_runtime_policy_weights"] is True
    assert report["contains_training_corpus"] is False
    assert report["development_compiler_modules_included"] is True
    assert (
        report["build_contract"]["backend_generator"]
        == "setuptools (83.0.0)"
    )

    reproduction.write_bytes(reproduction.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="P11_PACKAGE_BYTE_MISMATCH"):
        inspect_reproducible_wheels(primary, reproduction)
