"""Process-safe all-sample checkpointing for one retained P10 candidate.

Each worker reconstructs a fresh owner-bound HDS PROBE decision from the
content-addressed target intervention.  Checkpoints are bound to the complete
sample inventory, active manifest, candidate manifest, runtime source tree,
environment tree, Python, ARC Toolkit, budget, and candidate workflow.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from p10_main import (
    _resolve_p10_batch_game_ids,
    run_p10_offline_samples,
)

from .p10_batch_checkpoint import (
    assemble_checkpointed_report,
    checkpoint_path,
    environment_inventory_digest,
    load_game_checkpoint,
    runtime_source_inventory_digest,
    write_checkpoint_index,
    write_game_checkpoint,
)
from .p10_instruction_compiler import active_p10_manifest_digest
from .p10_prospective_composition_candidate_workflow import (
    P10_PROSPECTIVE_COMPOSITION_CANDIDATE_WORKFLOW_SCHEMA_VERSION,
)
from .p_update import (
    CandidatePBundle,
    HDSPUpdateAuthority,
    PUpdateProposal,
)
from .schema import digest_object

P10_PROSPECTIVE_CANDIDATE_BATCH_CONDITIONS_SCHEMA_VERSION = (
    "arc3-p10-prospective-candidate-batch-conditions-v1"
)
_TARGET_WORKFLOW_DIGEST_PREFIX = (
    "arc3_p10_prospective_composition_candidate_intervention:"
)
_RunFunction = Callable[..., dict[str, Any]]


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    return value


def _content_digest_valid(
    value: Mapping[str, Any],
    prefix: str,
) -> bool:
    body = dict(value)
    claimed = str(body.pop("content_digest", ""))
    return claimed == prefix + digest_object(body)


def _proposal(value: object) -> PUpdateProposal:
    if not isinstance(value, Mapping):
        raise TypeError("prospective candidate proposal invalid")
    normalized = dict(value)
    for key in (
        "evidence_refs",
        "expected_affected_capabilities",
        "expected_unaffected_capabilities",
        "falsifiers",
        "provenance",
    ):
        raw = normalized.get(key)
        if not isinstance(raw, list):
            raise TypeError(
                f"prospective candidate proposal field invalid: {key}"
            )
        normalized[key] = tuple(str(item) for item in raw)
    return PUpdateProposal(**normalized)


def _candidate(value: object) -> CandidatePBundle:
    if not isinstance(value, Mapping):
        raise TypeError("prospective candidate descriptor invalid")
    return CandidatePBundle(**dict(value))


def load_prospective_candidate_context(
    *,
    bundle_dir: Path,
    target_workflow_path: Path,
) -> tuple[
    dict[str, Any],
    PUpdateProposal,
    CandidatePBundle,
]:
    """Validate and reconstruct the candidate authority inputs."""

    workflow = _json(target_workflow_path)
    evaluation = workflow.get("evaluation")
    judgment = workflow.get("hds_judgment")
    failures: list[str] = []
    if (
        workflow.get("schema_version")
        != P10_PROSPECTIVE_COMPOSITION_CANDIDATE_WORKFLOW_SCHEMA_VERSION
    ):
        failures.append(
            "P10_PROSPECTIVE_BATCH_WORKFLOW_SCHEMA_INVALID"
        )
    if not _content_digest_valid(
        workflow,
        _TARGET_WORKFLOW_DIGEST_PREFIX,
    ):
        failures.append(
            "P10_PROSPECTIVE_BATCH_WORKFLOW_DIGEST_INVALID"
        )
    if (
        not isinstance(evaluation, Mapping)
        or evaluation.get("bounded_positive") is not True
        or evaluation.get("candidate_reproducible") is not True
        or evaluation.get("active_manifest_unchanged") is not True
    ):
        failures.append(
            "P10_PROSPECTIVE_BATCH_TARGET_GATE_NOT_PASS"
        )
    if (
        not isinstance(judgment, Mapping)
        or judgment.get("status") != "HOLD"
        or judgment.get("all_sample_regression_authorized") is not True
        or judgment.get("runtime_p_promotion_authorized") is not False
        or judgment.get("candidate_slot_retained") is not True
    ):
        failures.append(
            "P10_PROSPECTIVE_BATCH_HDS_AUTHORIZATION_INVALID"
        )
    if failures:
        raise ValueError(";".join(sorted(set(failures))))

    proposal = _proposal(workflow.get("proposal"))
    candidate = _candidate(workflow.get("candidate_descriptor"))
    if workflow.get("proposal_digest") != proposal.digest:
        raise ValueError(
            "P10_PROSPECTIVE_BATCH_PROPOSAL_DIGEST_MISMATCH"
        )
    if workflow.get("candidate_descriptor_digest") != candidate.digest:
        raise ValueError(
            "P10_PROSPECTIVE_BATCH_CANDIDATE_DIGEST_MISMATCH"
        )
    bundle_dir = bundle_dir.resolve()
    active_digest = active_p10_manifest_digest(bundle_dir)
    if active_digest != proposal.source_p_digest:
        raise ValueError(
            "P10_PROSPECTIVE_BATCH_ACTIVE_MANIFEST_CHANGED"
        )
    candidate_manifest = _json(
        bundle_dir / "p10_candidate_manifest.json"
    )
    if candidate_manifest.get("lifecycle") != "CANDIDATE":
        raise ValueError(
            "P10_PROSPECTIVE_BATCH_CANDIDATE_SLOT_NOT_STAGED"
        )
    candidate_manifest_digest = digest_object(candidate_manifest)
    if (
        candidate_manifest_digest != candidate.manifest_digest
        or workflow.get("candidate_manifest_digest")
        != candidate_manifest_digest
    ):
        raise ValueError(
            "P10_PROSPECTIVE_BATCH_CANDIDATE_MANIFEST_MISMATCH"
        )
    return workflow, proposal, candidate


def _arc_agi_version() -> str:
    try:
        return importlib.metadata.version("arc-agi")
    except importlib.metadata.PackageNotFoundError as error:
        raise ValueError(
            "P10_ARC_AGI_DISTRIBUTION_MISSING"
        ) from error


def build_prospective_candidate_batch_conditions(
    *,
    environments_dir: Path,
    game_ids: Sequence[str],
    bundle_dir: Path,
    workflow: Mapping[str, Any],
    candidate: CandidatePBundle,
    max_actions: int = 450,
) -> dict[str, Any]:
    """Return exact candidate checkpoint conditions."""

    normalized_game_ids = [str(game_id) for game_id in game_ids]
    if (
        len(normalized_game_ids) != 25
        or len(set(normalized_game_ids)) != 25
        or max_actions != 450
    ):
        raise ValueError(
            "P10_PROSPECTIVE_BATCH_STANDARD_CONDITIONS_REQUIRED"
        )
    active_digest = active_p10_manifest_digest(bundle_dir)
    candidate_manifest_digest = digest_object(
        _json(bundle_dir / "p10_candidate_manifest.json")
    )
    body: dict[str, object] = {
        "schema_version": (
            P10_PROSPECTIVE_CANDIDATE_BATCH_CONDITIONS_SCHEMA_VERSION
        ),
        "operation_mode": "offline",
        "instruction_lifecycle": "candidate",
        "instruction_variant": "hybrid",
        "max_actions": max_actions,
        "game_ids": normalized_game_ids,
        "environment_inventory_digest": environment_inventory_digest(
            environments_dir
        ),
        "runtime_source_inventory_digest": (
            runtime_source_inventory_digest()
        ),
        "python_version": platform.python_version(),
        "arc_agi_version": _arc_agi_version(),
        "active_manifest_digest": active_digest,
        "candidate_manifest_digest": candidate_manifest_digest,
        "candidate_descriptor_digest": candidate.digest,
        "candidate_body_digest": candidate.body_digest,
        "target_workflow_digest": workflow["content_digest"],
    }
    return {
        **body,
        "conditions_digest": digest_object(body),
    }


def _context_and_conditions(
    *,
    environments_dir: Path,
    bundle_dir: Path,
    target_workflow_path: Path,
    max_actions: int,
) -> tuple[
    list[str],
    dict[str, Any],
    PUpdateProposal,
    CandidatePBundle,
]:
    workflow, proposal, candidate = load_prospective_candidate_context(
        bundle_dir=bundle_dir,
        target_workflow_path=target_workflow_path,
    )
    game_ids = _resolve_p10_batch_game_ids(
        environments_dir=environments_dir,
        requested_games=None,
        all_samples=True,
        recordings_dir=None,
    )
    conditions = build_prospective_candidate_batch_conditions(
        environments_dir=environments_dir,
        game_ids=game_ids,
        bundle_dir=bundle_dir,
        workflow=workflow,
        candidate=candidate,
        max_actions=max_actions,
    )
    return game_ids, conditions, proposal, candidate


def run_prospective_candidate_checkpoint_worker(
    *,
    environments_dir: Path,
    checkpoint_dir: Path,
    bundle_dir: Path,
    target_workflow_path: Path,
    game_id: str,
    max_actions: int = 450,
    resume: bool = False,
    runner: _RunFunction = run_p10_offline_samples,
) -> dict[str, object]:
    """Execute or reuse one HDS-authorized candidate worker."""

    environments_dir = environments_dir.resolve()
    checkpoint_dir = checkpoint_dir.resolve()
    bundle_dir = bundle_dir.resolve()
    (
        game_ids,
        conditions,
        proposal,
        candidate,
    ) = _context_and_conditions(
        environments_dir=environments_dir,
        bundle_dir=bundle_dir,
        target_workflow_path=target_workflow_path,
        max_actions=max_actions,
    )
    if game_id not in game_ids:
        raise ValueError(
            f"P10_PROSPECTIVE_BATCH_GAME_NOT_IN_SAMPLE_SET:{game_id}"
        )
    existing = load_game_checkpoint(
        checkpoint_dir=checkpoint_dir,
        conditions=conditions,
        game_id=game_id,
    )
    status = "REUSED"
    if existing is None:
        authority = HDSPUpdateAuthority()
        decision = authority.decide(
            proposal,
            status="PROBE",
            reason_codes=(
                "target-double-run-positive",
                "all-retained-sample-candidate-regression",
                "active-p-remains-unchanged",
            ),
            candidate_bundle=candidate,
        )
        result = runner(
            environments_dir=environments_dir,
            requested_games=[game_id],
            max_actions=max_actions,
            instruction_variant="hybrid",
            instruction_lifecycle="candidate",
            p_update_authority=authority,
            p_update_decision=decision,
            candidate_bundle=candidate,
        )
        path = write_game_checkpoint(
            checkpoint_dir=checkpoint_dir,
            conditions=conditions,
            game_id=game_id,
            result=result,
        )
        status = "EXECUTED"
    else:
        if not resume:
            raise FileExistsError(
                "P10_CHECKPOINT_EXISTS_USE_RESUME:"
                + str(checkpoint_path(checkpoint_dir, game_id))
            )
        raw_result = existing.get("single_game_report")
        if not isinstance(raw_result, Mapping):
            raise TypeError(
                "P10_PROSPECTIVE_BATCH_CHECKPOINT_REPORT_MISSING"
            )
        result = dict(raw_result)
        path = checkpoint_path(checkpoint_dir, game_id)

    reports = result.get("reports")
    if not isinstance(reports, list):
        raise TypeError("P10_PROSPECTIVE_BATCH_REPORTS_INVALID")
    report: Mapping[str, Any] = {}
    if reports:
        first = reports[0]
        if not isinstance(first, Mapping):
            raise TypeError(
                "P10_PROSPECTIVE_BATCH_GAME_REPORT_INVALID"
            )
        report = first
    return {
        "status": status,
        "game_id": game_id,
        "checkpoint": str(path),
        "conditions_digest": str(conditions["conditions_digest"]),
        "candidate_descriptor_digest": candidate.digest,
        "completed_count": _integer(
            result.get("completed_count"),
            "completed_count",
        ),
        "error_count": _integer(
            result.get("error_count"),
            "error_count",
        ),
        "actions": _integer(report.get("actions", 0), "actions"),
        "levels_completed": _integer(
            report.get("levels_completed", 0),
            "levels_completed",
        ),
        "win_levels": _integer(
            report.get("win_levels", 0),
            "win_levels",
        ),
    }


def assemble_prospective_candidate_checkpointed_report(
    *,
    environments_dir: Path,
    checkpoint_dir: Path,
    bundle_dir: Path,
    target_workflow_path: Path,
    output_path: Path,
    max_actions: int = 450,
) -> dict[str, Any]:
    """Assemble all 25 candidate checkpoints into an oracle input."""

    game_ids, conditions, _proposal_value, _candidate_value = (
        _context_and_conditions(
            environments_dir=environments_dir.resolve(),
            bundle_dir=bundle_dir.resolve(),
            target_workflow_path=target_workflow_path,
            max_actions=max_actions,
        )
    )
    report = assemble_checkpointed_report(
        checkpoint_dir=checkpoint_dir.resolve(),
        conditions=conditions,
    )
    write_checkpoint_index(
        checkpoint_dir=checkpoint_dir.resolve(),
        conditions=conditions,
        completed_game_ids=game_ids,
        reused_game_ids=(),
    )
    _write_json(output_path.resolve(), report)
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run or assemble the content-bound P10 candidate all-sample "
            "checkpoint batch."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("worker", "assemble"):
        child = subparsers.add_parser(name)
        child.add_argument("--environments-dir", type=Path, required=True)
        child.add_argument("--checkpoint-dir", type=Path, required=True)
        child.add_argument("--bundle-dir", type=Path, required=True)
        child.add_argument("--target-workflow", type=Path, required=True)
        child.add_argument("--max-actions", type=int, default=450)
        if name == "worker":
            child.add_argument("--game", required=True)
            child.add_argument("--resume", action="store_true")
        else:
            child.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "worker":
        result = run_prospective_candidate_checkpoint_worker(
            environments_dir=args.environments_dir,
            checkpoint_dir=args.checkpoint_dir,
            bundle_dir=args.bundle_dir,
            target_workflow_path=args.target_workflow,
            game_id=args.game,
            max_actions=args.max_actions,
            resume=args.resume,
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if result["error_count"] == 0 else 1
    report = assemble_prospective_candidate_checkpointed_report(
        environments_dir=args.environments_dir,
        checkpoint_dir=args.checkpoint_dir,
        bundle_dir=args.bundle_dir,
        target_workflow_path=args.target_workflow,
        output_path=args.output,
        max_actions=args.max_actions,
    )
    print(
        json.dumps(
            {
                "completed_levels": report["completed_levels"],
                "total_levels": report["total_levels"],
                "error_count": report["error_count"],
                "all_complete": report["all_complete"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "P10_PROSPECTIVE_CANDIDATE_BATCH_CONDITIONS_SCHEMA_VERSION",
    "assemble_prospective_candidate_checkpointed_report",
    "build_prospective_candidate_batch_conditions",
    "load_prospective_candidate_context",
    "main",
    "run_prospective_candidate_checkpoint_worker",
]
