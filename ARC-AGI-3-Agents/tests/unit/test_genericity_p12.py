from __future__ import annotations

from pathlib import Path

from arc3_agi_agent.competition_contract import (
    run_competition_contract_dry_run,
)
from arc3_agi_agent.generic_compute import HybridRelationalInstructionBody
from arc3_agi_agent.generic_package import audit_generic_runtime_package
from arc3_agi_agent.p12_audit import (
    executable_transformation_evaluation,
    mechanism_holdout_evaluation,
    operational_conformance_suite,
    sealed_custom_evaluation,
    version_learning_evaluation,
)


def test_p12_operational_conformance_is_executable() -> None:
    report = operational_conformance_suite()

    assert report["status"] == "PASS"
    assert report["failed_requirement_ids"] == ()
    assert all(report["checks"].values())
    assert report["nominal_run"]["state"] == "WIN"
    assert report["nominal_run"]["no_fallback_used"] is True


def test_mechanism_and_transformation_holdouts_execute() -> None:
    mechanism = mechanism_holdout_evaluation()
    transformations = executable_transformation_evaluation()

    assert mechanism["status"] == "PASS"
    assert mechanism["generic_runtime_progress"] > (
        mechanism["fixed_policy_progress"]
    )
    assert transformations["status"] == "PASS"
    assert transformations["family_count"] == 7
    assert transformations["win_count"] == 7


def test_sealed_evaluator_is_a_separate_executable_process() -> None:
    project_root = Path(__file__).resolve().parents[2]
    report = sealed_custom_evaluation(
        evaluator_script=project_root / "tools/p12_sealed_evaluator.py",
        code_commit="unit-test-frozen-code",
        body=HybridRelationalInstructionBody(),
        seed=0,
    )

    assert report["status"] == "PASS"
    assert report["evaluator_process_separate"] is True
    assert report["runtime_source_read"] is False
    assert report["win_count"] == 3


def test_version_learning_and_competition_mock_contract_execute() -> None:
    learning = version_learning_evaluation()
    competition = run_competition_contract_dry_run()

    assert learning["status"] == "PASS"
    assert learning["promotion"]["status"] == "PROMOTE"
    assert learning["runtime_called_trainer"] is False
    assert competition["status"] == "PASS"
    assert not competition["failed_requirement_ids"]
    assert all(competition["checks"].values())


def test_generic_runtime_package_is_reproducible_and_allow_listed(
    tmp_path: Path,
) -> None:
    package_dir = Path(__file__).resolve().parents[2] / "arc3_agi_agent"
    report = audit_generic_runtime_package(
        package_dir=package_dir,
        first_output=tmp_path / "first.zip",
        second_output=tmp_path / "second.zip",
    )

    assert report.passed()
    assert report.reproducible is True
    assert report.forbidden_member_count == 0
    assert report.forbidden_content_count == 0
    assert report.teacher_graph_included is False
    assert report.training_examples_included is False
    assert report.sealed_source_included is False
