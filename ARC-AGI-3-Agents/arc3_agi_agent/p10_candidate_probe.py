"""HDS-authorized isolated OFFLINE probe for a compiled P10 candidate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from p10_main import run_p10_offline_samples

from .p10_instruction_compiler import active_p10_manifest_digest
from .p10_promotion import (
    hybrid_candidate_from_trace,
    p_update_proposal_from_mapping,
)
from .p_update import HDSPUpdateAuthority
from .schema import digest_object


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected object: {path}")
    return value


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def run_p10_candidate_probe(
    *,
    environments_dir: Path,
    environment_selector: str,
    max_actions: int,
    bundle_dir: Path,
    trace_path: Path,
    report_path: Path,
    record: bool = False,
    recordings_dir: Path | None = None,
) -> dict[str, object]:
    trace = _json(trace_path)
    trace_core = {
        key: value for key, value in trace.items() if key != "content_digest"
    }
    trace_digest = "p10-p-update-workflow:" + digest_object(trace_core)
    if trace.get("content_digest") != trace_digest:
        raise ValueError("P10_CANDIDATE_PROBE_TRACE_DIGEST_MISMATCH")
    if trace.get("operation_mode") != "offline":
        raise ValueError("P10_CANDIDATE_PROBE_TRACE_NOT_OFFLINE")
    if trace.get("active_changed") is not False:
        raise ValueError("P10_CANDIDATE_PROBE_TRACE_ACTIVE_CHANGED")
    proposal = p_update_proposal_from_mapping(trace.get("proposal"))
    candidate = hybrid_candidate_from_trace(trace)
    if active_p10_manifest_digest(bundle_dir) != proposal.source_p_digest:
        raise ValueError("P10_CANDIDATE_PROBE_ACTIVE_MANIFEST_CHANGED")
    candidate_manifest = _json(bundle_dir / "p10_candidate_manifest.json")
    if digest_object(candidate_manifest) != candidate.manifest_digest:
        raise ValueError("P10_CANDIDATE_PROBE_MANIFEST_MISMATCH")

    authority = HDSPUpdateAuthority()
    decision = authority.decide(
        proposal,
        status="PROBE",
        reason_codes=(
            "bounded-offline-candidate-probe",
            "active-manifest-remains-unchanged",
        ),
        candidate_bundle=candidate,
    )
    run = run_p10_offline_samples(
        environments_dir=environments_dir,
        requested_games=[environment_selector],
        max_actions=max_actions,
        instruction_variant="hybrid",
        instruction_lifecycle="candidate",
        p_update_authority=authority,
        p_update_decision=decision,
        candidate_bundle=candidate,
        record=record,
        recordings_dir=recordings_dir,
    )
    core: dict[str, object] = {
        "schema_version": "arc3-p10-candidate-probe-v1",
        "operation_mode": "offline",
        "source_trace_digest": trace_digest,
        "active_manifest_digest": proposal.source_p_digest,
        "candidate_manifest_digest": candidate.manifest_digest,
        "candidate_bundle_digest": candidate.digest,
        "hds_decision": {
            "decision_id": decision.decision_id,
            "decision_digest": decision.digest,
            "status": decision.status,
            "reason_codes": list(decision.reason_codes),
            "authority": decision.authority,
        },
        "run": run,
    }
    evidence = {
        **core,
        "content_digest": "p10-candidate-probe:" + digest_object(core),
    }
    _write_json(report_path, evidence)
    return evidence


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run one HDS-authorized candidate in an isolated OFFLINE sample "
            "session without changing active P."
        )
    )
    parser.add_argument("--environments-dir", type=Path, required=True)
    parser.add_argument("--game", required=True)
    parser.add_argument("--max-actions", type=int, required=True)
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--record", action="store_true")
    parser.add_argument("--recordings-dir", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    evidence = run_p10_candidate_probe(
        environments_dir=args.environments_dir,
        environment_selector=args.game,
        max_actions=args.max_actions,
        bundle_dir=args.bundle_dir,
        trace_path=args.trace,
        report_path=args.report,
        record=args.record,
        recordings_dir=args.recordings_dir,
    )
    print(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True))
    run = evidence["run"]
    if not isinstance(run, dict):
        return 2
    return 0 if run.get("error_count") == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "main",
    "run_p10_candidate_probe",
]
