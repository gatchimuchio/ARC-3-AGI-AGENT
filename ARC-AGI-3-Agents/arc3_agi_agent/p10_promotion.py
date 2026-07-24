"""Revalidate a P10 regression trace and execute HDS-controlled promotion."""

from __future__ import annotations

import argparse
import dataclasses
import json
from pathlib import Path
from typing import Any

from .p10_instruction_compiler import active_p10_manifest_digest
from .p10_manifest_lifecycle import (
    promote_p10_candidate_manifest,
    promotion_receipt_mapping,
)
from .p_update import (
    CandidatePBundle,
    HDSPUpdateAuthority,
    PRegressionReport,
    PUpdateProposal,
)
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


def p_update_proposal_from_mapping(value: object) -> PUpdateProposal:
    if not isinstance(value, dict):
        raise TypeError("P10 promotion proposal invalid")
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
            raise TypeError(f"P10 promotion proposal field invalid: {key}")
        normalized[key] = tuple(str(item) for item in raw)
    return PUpdateProposal(**normalized)


def hybrid_candidate_from_trace(
    trace: dict[str, Any],
) -> CandidatePBundle:
    descriptors = trace.get("candidate_descriptors")
    if not isinstance(descriptors, list):
        raise TypeError("P10 promotion candidate descriptors invalid")
    value = next(
        (
            item
            for item in descriptors
            if isinstance(item, dict)
            and item.get("target_component") == "hybrid-P-B"
        ),
        None,
    )
    if not isinstance(value, dict):
        raise TypeError("P10 promotion hybrid candidate missing")
    return CandidatePBundle(**value)


def hybrid_regression_from_trace(
    trace: dict[str, Any],
) -> PRegressionReport:
    value = trace.get("hybrid_regression_report")
    if not isinstance(value, dict):
        raise TypeError("P10 promotion hybrid regression missing")
    normalized = dict(value)
    raw_evidence = normalized.get("evidence_refs")
    if not isinstance(raw_evidence, list):
        raise TypeError("P10 promotion regression evidence invalid")
    normalized["evidence_refs"] = tuple(str(item) for item in raw_evidence)
    return PRegressionReport(**normalized)


def promote_p10_candidate_from_trace(
    *,
    bundle_dir: Path,
    trace_path: Path,
    receipt_path: Path,
) -> dict[str, object]:
    """PROMOTE only a current, fully closed, content-addressed trace."""

    trace = _json(trace_path)
    claimed_trace_digest = trace.get("content_digest")
    trace_core = {
        key: value for key, value in trace.items() if key != "content_digest"
    }
    actual_trace_digest = "p10-p-update-workflow:" + digest_object(
        trace_core
    )
    if claimed_trace_digest != actual_trace_digest:
        raise ValueError("P10_PROMOTION_TRACE_DIGEST_MISMATCH")
    if trace.get("operation_mode") != "offline":
        raise ValueError("P10_PROMOTION_TRACE_NOT_OFFLINE")
    if trace.get("active_changed") is not False:
        raise ValueError("P10_PROMOTION_TRACE_ACTIVE_ALREADY_CHANGED")
    if trace.get("promotion_failures") != []:
        raise ValueError("P10_PROMOTION_GATES_NOT_CLOSED")
    runtime_regression = trace.get("candidate_runtime_regression")
    if not isinstance(runtime_regression, dict):
        raise ValueError("P10_PROMOTION_RUNTIME_REGRESSION_MISSING")
    if (
        runtime_regression.get("stable_non_regression") is not True
        or runtime_regression.get("target_improved") is not True
        or runtime_regression.get("reproducible") is not True
    ):
        raise ValueError("P10_PROMOTION_RUNTIME_REGRESSION_INCOMPLETE")

    proposal = p_update_proposal_from_mapping(trace.get("proposal"))
    candidate = hybrid_candidate_from_trace(trace)
    regression = hybrid_regression_from_trace(trace)
    if trace.get("proposal_digest") != proposal.digest:
        raise ValueError("P10_PROMOTION_PROPOSAL_DIGEST_MISMATCH")
    if trace.get("hybrid_regression_report_digest") != regression.digest:
        raise ValueError("P10_PROMOTION_REGRESSION_DIGEST_MISMATCH")
    if not regression.promotion_ready:
        raise ValueError(
            "P10_PROMOTION_GATES_NOT_CLOSED:"
            + ",".join(regression.promotion_failures)
        )
    before_manifest_digest = active_p10_manifest_digest(bundle_dir)
    if before_manifest_digest != proposal.source_p_digest:
        raise ValueError("P10_PROMOTION_ACTIVE_MANIFEST_CHANGED")

    authority = HDSPUpdateAuthority()
    decision = authority.decide(
        proposal,
        status="PROMOTE",
        reason_codes=(
            "all-ten-promotion-gates-pass",
            "stable-twenty-nine-level-regression-pass",
            "target-zero-to-one-level-improvement-reproduced",
        ),
        candidate_bundle=candidate,
        regression_report=regression,
    )
    directive = authority.issue_promotion_directive(
        proposal,
        candidate,
        regression,
        decision,
        expected_active_bundle_digest=before_manifest_digest,
    )
    receipt = promote_p10_candidate_manifest(
        bundle_dir=bundle_dir,
        proposal=proposal,
        candidate=candidate,
        regression_report=regression,
        decision=decision,
        directive=directive,
        authority=authority,
    )
    after_manifest_digest = active_p10_manifest_digest(bundle_dir)
    promoted_active = dataclasses.replace(
        candidate,
        lifecycle="ACTIVE",
        manifest_digest=after_manifest_digest,
    )
    core: dict[str, object] = {
        "schema_version": "arc3-p10-promotion-evidence-v1",
        "operation_mode": "offline",
        "source_trace_digest": actual_trace_digest,
        "source_trace_path": trace_path.name,
        "before_active_manifest_digest": before_manifest_digest,
        "after_active_manifest_digest": after_manifest_digest,
        "hds_decision": {
            "decision_id": decision.decision_id,
            "decision_digest": decision.digest,
            "status": decision.status,
            "reason_codes": list(decision.reason_codes),
            "allow_p_promote": decision.allow_p_promote,
            "authority": decision.authority,
        },
        "promotion_directive_digest": directive.digest,
        "promotion_receipt": promotion_receipt_mapping(receipt),
        "promoted_active_descriptor": dataclasses.asdict(promoted_active),
        "regression_report_digest": regression.digest,
        "promotion_failures": list(regression.promotion_failures),
        "active_changed": before_manifest_digest != after_manifest_digest,
    }
    evidence = {
        **core,
        "content_digest": "p10-promotion-evidence:" + digest_object(core),
    }
    _write_json(receipt_path, evidence)
    return evidence


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Revalidate a P10 candidate trace and promote only through an "
            "owner-bound HDS directive."
        )
    )
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    evidence = promote_p10_candidate_from_trace(
        bundle_dir=args.bundle_dir,
        trace_path=args.trace,
        receipt_path=args.receipt,
    )
    print(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "hybrid_candidate_from_trace",
    "hybrid_regression_from_trace",
    "main",
    "p_update_proposal_from_mapping",
    "promote_p10_candidate_from_trace",
]
