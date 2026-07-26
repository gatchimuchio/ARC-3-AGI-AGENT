"""HDS-controlled target probe for the prospective composition candidate.

The workflow consumes a COMPOSABLE development audit, compiles one isolated
hybrid candidate, proves byte-deterministic rebuild, and runs the retained
target twice.  It never promotes active P.  Failure restores the prior
candidate slot byte-for-byte.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from p10_main import run_p10_offline_samples

from .directional_force_multi_actor import COMPOSITION_EVIDENCE
from .instruction_body import (
    clear_p10_instruction_body_caches,
    instruction_body_from_mapping,
)
from .p10_instruction_compiler import (
    P10_CANDIDATE_MANIFEST_FILENAME,
    P10_COMPILER_SEED,
    P10_PROSPECTIVE_COMPOSITION_CANDIDATE_SET_VERSION,
    P10_PROSPECTIVE_COMPOSITION_COMPILER_VERSION,
    P10_PROSPECTIVE_COMPOSITION_HYBRID_FILENAME,
    active_p10_manifest_digest,
    compile_p10_prospective_composition_hybrid_candidate,
    directional_force_route_instruction_mapping,
)
from .p10_prospective_obligation_composition_audit import (
    P10_PROSPECTIVE_OBLIGATION_COMPOSITION_AUDIT_SCHEMA_VERSION,
)
from .p_update import (
    CandidatePBundle,
    HDSPUpdateAuthority,
    InstructionBodyCompileDirective,
    PUpdateDecision,
    PUpdateEvidenceSet,
    PUpdateProposal,
)
from .schema import digest_object

P10_PROSPECTIVE_COMPOSITION_CANDIDATE_WORKFLOW_SCHEMA_VERSION = (
    "arc3-p10-prospective-composition-candidate-intervention-v1"
)
_COMPOSITION_DIGEST_PREFIX = (
    "arc3_p10_prospective_obligation_composition_audit:"
)
_WORKFLOW_DIGEST_PREFIX = (
    "arc3_p10_prospective_composition_candidate_intervention:"
)
_RunFunction = Callable[..., dict[str, Any]]


def _integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    return value


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


def _atomic_write_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _content_digest_valid(
    value: Mapping[str, Any],
    prefix: str,
) -> bool:
    body = dict(value)
    claimed = str(body.pop("content_digest", ""))
    return claimed == prefix + digest_object(body)


def _composition_digest(
    composition_audit: Mapping[str, Any],
) -> str:
    checks = composition_audit.get("composable_checks")
    integrity = composition_audit.get("source_integrity_checks")
    judgment = composition_audit.get("hds_judgment")
    failures: list[str] = []
    if (
        composition_audit.get("schema_version")
        != P10_PROSPECTIVE_OBLIGATION_COMPOSITION_AUDIT_SCHEMA_VERSION
    ):
        failures.append(
            "P10_PROSPECTIVE_COMPOSITION_AUDIT_SCHEMA_INVALID"
        )
    if not _content_digest_valid(
        composition_audit,
        _COMPOSITION_DIGEST_PREFIX,
    ):
        failures.append(
            "P10_PROSPECTIVE_COMPOSITION_AUDIT_DIGEST_INVALID"
        )
    if composition_audit.get("candidate_tier") != "COMPOSABLE":
        failures.append(
            "P10_PROSPECTIVE_COMPOSITION_TIER_NOT_COMPOSABLE"
        )
    if (
        composition_audit.get("development_only") is not True
        or composition_audit.get("runtime_use") != "FORBIDDEN"
    ):
        failures.append(
            "P10_PROSPECTIVE_COMPOSITION_DEVELOPMENT_BOUNDARY_INVALID"
        )
    if not isinstance(checks, Mapping) or not checks or not all(
        value is True for value in checks.values()
    ):
        failures.append(
            "P10_PROSPECTIVE_COMPOSITION_CHECKS_NOT_PASS"
        )
    if not isinstance(integrity, Mapping) or not integrity or not all(
        value is True for value in integrity.values()
    ):
        failures.append(
            "P10_PROSPECTIVE_COMPOSITION_INTEGRITY_NOT_PASS"
        )
    if not isinstance(judgment, Mapping):
        failures.append(
            "P10_PROSPECTIVE_COMPOSITION_HDS_JUDGMENT_MISSING"
        )
    else:
        if judgment.get("composable_status") != "PASS":
            failures.append(
                "P10_PROSPECTIVE_COMPOSITION_HDS_STATUS_NOT_PASS"
            )
        if (
            judgment.get("isolated_candidate_compile_authorized")
            is not True
        ):
            failures.append(
                "P10_PROSPECTIVE_COMPOSITION_COMPILE_NOT_AUTHORIZED"
            )
        if judgment.get("active_p_compile_authorized") is not False:
            failures.append(
                "P10_PROSPECTIVE_COMPOSITION_ACTIVE_BOUNDARY_INVALID"
            )
        if judgment.get("runtime_p_promotion_authorized") is not False:
            failures.append(
                "P10_PROSPECTIVE_COMPOSITION_PROMOTION_BOUNDARY_INVALID"
            )
    if failures:
        raise ValueError(";".join(sorted(set(failures))))
    return str(composition_audit["content_digest"])


def _proposal_and_evidence(
    *,
    active_manifest: Mapping[str, Any],
    active_manifest_digest: str,
    composition_audit: Mapping[str, Any],
    composition_digest: str,
) -> tuple[PUpdateProposal, PUpdateEvidenceSet]:
    bundles = active_manifest.get("bundles")
    if not isinstance(bundles, Mapping):
        raise TypeError("active P10 manifest bundles invalid")
    hybrid = bundles.get("hybrid")
    if not isinstance(hybrid, Mapping):
        raise TypeError("active P10 hybrid entry invalid")
    source_evidence = composition_audit.get("source_evidence")
    removal_controls = composition_audit.get("removal_controls")
    x_r_mc = composition_audit.get("x_r_mc")
    if not isinstance(source_evidence, Mapping):
        raise TypeError("prospective composition source evidence invalid")
    if not isinstance(removal_controls, Mapping):
        raise TypeError("prospective composition removal controls invalid")
    if not isinstance(x_r_mc, Mapping):
        raise TypeError("prospective composition X/R/Mc invalid")
    source_refs = tuple(
        str(source_evidence[key])
        for key in sorted(source_evidence)
        if str(source_evidence[key]).strip()
    )
    removal_digest = digest_object(removal_controls)
    frame_digest = str(x_r_mc.get("frame_digest", ""))
    proposal = PUpdateProposal(
        proposal_id=(
            "proposal:prospective-obligation-capability-composition"
        ),
        source_p_version=str(hybrid.get("body_version", "")),
        source_p_digest=active_manifest_digest,
        target_component="hybrid-P-B",
        update_type="feature-mapping",
        evidence_refs=(composition_digest, *source_refs),
        expected_effect="close-joint-rendered-obligations",
        expected_affected_capabilities=(
            "prospective-rendered-relation",
            "multi-actor-directional-obligation-composition",
        ),
        expected_unaffected_capabilities=(
            "active-runtime-manifest-before-promotion",
            "symbolic-instruction-body",
            "parametric-instruction-body",
            "historical-directional-settle-control",
        ),
        falsifiers=(
            "completed-count-does-not-increase",
            "candidate-rerun-differs",
            "retained-sample-completion-decreases",
            "active-manifest-changes",
        ),
        rollback_target=str(hybrid.get("body_version", "")),
        provenance=(
            composition_digest,
            "development-memory:hds-selected-h3-composition",
        ),
    )
    evidence = PUpdateEvidenceSet(
        evidence_set_id=(
            "evidence-set:prospective-obligation-capability-composition"
        ),
        proposal_digest=proposal.digest,
        memory_snapshot_digest=(
            "development-memory-snapshot:"
            + digest_object(
                {
                    "composition": composition_digest,
                    "source_refs": source_refs,
                }
            )
        ),
        approved_memory_refs=(
            composition_digest,
            "development-frame:" + frame_digest,
        ),
        hds_memory_decision_digests=(
            "hds-development-decision:"
            + digest_object(x_r_mc.get("decision")),
        ),
        failure_refs=(
            "failure:joint-obligation-incomplete:" + removal_digest,
        ),
        contradiction_refs=(
            "contradiction:composition-gate-removed:" + removal_digest,
        ),
        positive_contrast_refs=(
            "contrast:relation-cluster:" + composition_digest,
        ),
        negative_contrast_refs=(
            "contrast:remove-composed-capability:" + removal_digest,
        ),
        holdout_refs=(
            "holdout:all-retained-samples-required",
        ),
        replay_audit_refs=(
            "audit:late-identity-subtraction:"
            + digest_object(
                composition_audit.get("identity_subtraction")
            ),
        ),
        provenance=(composition_digest,),
    )
    failures = (*proposal.validate(), *evidence.validate())
    if failures:
        raise ValueError(";".join(sorted(set(failures))))
    return proposal, evidence


def _compile_authorization(
    proposal: PUpdateProposal,
    evidence: PUpdateEvidenceSet,
) -> tuple[
    HDSPUpdateAuthority,
    PUpdateDecision,
    InstructionBodyCompileDirective,
]:
    authority = HDSPUpdateAuthority()
    decision = authority.decide(
        proposal,
        status="COMPILE",
        reason_codes=(
            "prospective-composition-composable-pass",
            "candidate-hybrid-only",
            "active-p-remains-unchanged",
        ),
        evidence_set=evidence,
    )
    directive = authority.issue_compile_directive(
        proposal,
        evidence,
        decision,
        target_body_version=(
            P10_PROSPECTIVE_COMPOSITION_CANDIDATE_SET_VERSION
        ),
        seed=P10_COMPILER_SEED,
    )
    return authority, decision, directive


def _decision_mapping(decision: PUpdateDecision) -> dict[str, object]:
    return {
        "decision_id": decision.decision_id,
        "proposal_digest": decision.proposal_digest,
        "status": decision.status,
        "reason_codes": list(decision.reason_codes),
        "evidence_set_digest": decision.evidence_set_digest,
        "candidate_bundle_digest": decision.candidate_bundle_digest,
        "regression_report_digest": decision.regression_report_digest,
        "allow_p_compile": decision.allow_p_compile,
        "allow_p_promote": decision.allow_p_promote,
        "allow_p_rollback": decision.allow_p_rollback,
        "authority": decision.authority,
    }


def _candidate_descriptor(
    *,
    active_manifest: Mapping[str, Any],
    candidate_manifest: Mapping[str, Any],
    candidate_mapping: Mapping[str, Any],
    proposal: PUpdateProposal,
    rebuild_digest: str,
) -> CandidatePBundle:
    active_bundles = active_manifest.get("bundles")
    candidate_bundles = candidate_manifest.get("bundles")
    if not isinstance(active_bundles, Mapping) or not isinstance(
        candidate_bundles,
        Mapping,
    ):
        raise TypeError("P10 manifest bundles invalid")
    active = active_bundles.get("hybrid")
    candidate = candidate_bundles.get("hybrid")
    if not isinstance(active, Mapping) or not isinstance(
        candidate,
        Mapping,
    ):
        raise TypeError("P10 hybrid manifest entry invalid")
    candidate_body = instruction_body_from_mapping(candidate_mapping)
    predecessor_mapping = directional_force_route_instruction_mapping()
    composition_mapping = directional_force_route_instruction_mapping(
        multi_actor_composition_enabled=True,
        maximum_composition_transition_observations=8,
    )
    predecessor_parameter_digest = (
        "feature-mapping:" + digest_object(predecessor_mapping)
    )
    parameter_digest = (
        "feature-mapping:" + digest_object(composition_mapping)
    )
    descriptor = CandidatePBundle(
        candidate_id=(
            "candidate:p10-prospective-obligation-composition-hybrid"
        ),
        proposal_digest=proposal.digest,
        compile_directive_digest=str(
            candidate_manifest.get("compile_directive_digest", "")
        ),
        target_component="hybrid-P-B",
        body_version=str(candidate.get("body_version", "")),
        body_digest=str(candidate.get("content_digest", "")),
        source_body_version=str(active.get("body_version", "")),
        source_body_digest=str(active.get("content_digest", "")),
        provenance_digest=candidate_body.provenance_digest,
        manifest_digest=digest_object(candidate_manifest),
        deterministic_rebuild_digest=rebuild_digest,
        rollback_target=str(active.get("body_version", "")),
        parameter_digest=parameter_digest,
        predecessor_parameter_digest=predecessor_parameter_digest,
        same_input_predecessor_output_digest=digest_object(
            predecessor_mapping
        ),
        same_input_candidate_output_digest=digest_object(
            composition_mapping
        ),
        parameter_change_attribution=(
            "hds-authorized-existing-capability-composition-gate"
        ),
    )
    failures = descriptor.validate()
    if failures:
        raise ValueError(";".join(failures))
    return descriptor


def _compact_run(result: Mapping[str, Any]) -> dict[str, object]:
    reports = result.get("reports")
    errors = result.get("errors")
    if not isinstance(reports, list) or not isinstance(errors, list):
        raise TypeError("prospective candidate result shape invalid")
    report = reports[0] if len(reports) == 1 else {}
    if not isinstance(report, Mapping):
        raise TypeError("prospective candidate report invalid")
    raw_provenance_rows = report.get("emitted_provenance", ())
    if not isinstance(raw_provenance_rows, Sequence) or isinstance(
        raw_provenance_rows,
        (str, bytes, bytearray),
    ):
        raise TypeError("prospective candidate provenance invalid")
    provenance_rows = list(raw_provenance_rows)
    composition_action_count = sum(
        isinstance(row, Sequence)
        and not isinstance(row, (str, bytes, bytearray))
        and COMPOSITION_EVIDENCE in row
        for row in provenance_rows
    )
    core: dict[str, object] = {
        "selector_digest": digest_object(report.get("game_id")),
        "operation_mode": result.get("operation_mode"),
        "instruction_lifecycle": result.get("instruction_lifecycle"),
        "instruction_variant": result.get("instruction_variant"),
        "max_actions": result.get("max_actions"),
        "completed_levels": int(result.get("completed_levels", 0)),
        "total_levels": int(result.get("total_levels", 0)),
        "complete_game_count": int(result.get("complete_game_count", 0)),
        "all_complete": bool(result.get("all_complete", False)),
        "error_count": int(result.get("error_count", 0)),
        "actions": int(report.get("actions", 0)),
        "recoveries": int(report.get("recoveries", 0)),
        "search_resets": int(report.get("search_resets", 0)),
        "final_status": str(report.get("final_status", "ERROR")),
        "max_action_exhausted": bool(
            report.get("max_action_exhausted", False)
        ),
        "composition_action_count": composition_action_count,
        "instruction_body_versions": sorted(
            {str(item) for item in report.get(
                "instruction_body_versions",
                [],
            )}
        ),
        "instruction_body_digests": sorted(
            {str(item) for item in report.get(
                "instruction_body_digests",
                [],
            )}
        ),
        "instruction_query_digests_digest": digest_object(
            report.get("instruction_query_digests", [])
        ),
        "emitted_steps_digest": digest_object(
            report.get("emitted_steps", [])
        ),
        "emitted_provenance_digest": digest_object(provenance_rows),
        "trace_digests_digest": digest_object(
            report.get("trace_digests", [])
        ),
        "prospective_relation_probe_digest": digest_object(
            report.get("development_prospective_relation_probe", {})
        ),
        "errors_digest": digest_object(errors),
    }
    return {
        **core,
        "run_digest": (
            "p10-prospective-composition-target-run:"
            + digest_object(core)
        ),
    }


def _execute_candidate(
    *,
    environments_dir: Path,
    environment_selector: str,
    max_actions: int,
    runner: _RunFunction,
    authority: HDSPUpdateAuthority,
    decision: PUpdateDecision,
    candidate: CandidatePBundle,
) -> dict[str, object]:
    result = runner(
        environments_dir=environments_dir,
        requested_games=[environment_selector],
        max_actions=max_actions,
        instruction_variant="hybrid",
        instruction_lifecycle="candidate",
        p_update_authority=authority,
        p_update_decision=decision,
        candidate_bundle=candidate,
    )
    return _compact_run(result)


def _restore_candidate_slot(
    *,
    candidate_manifest_path: Path,
    candidate_body_path: Path,
    prior_manifest: bytes | None,
    prior_body: bytes | None,
) -> None:
    if prior_manifest is None:
        candidate_manifest_path.unlink(missing_ok=True)
    else:
        _atomic_write_bytes(candidate_manifest_path, prior_manifest)
    if prior_body is None:
        candidate_body_path.unlink(missing_ok=True)
    else:
        _atomic_write_bytes(candidate_body_path, prior_body)
    clear_p10_instruction_body_caches()


def execute_p10_prospective_composition_candidate_workflow(
    *,
    environments_dir: Path,
    bundle_dir: Path,
    composition_audit_path: Path,
    output_path: Path,
    environment_selector: str,
    max_actions: int = 450,
    runner: _RunFunction = run_p10_offline_samples,
) -> dict[str, object]:
    """Compile and run the H3 target twice; never promote active P."""

    if not environment_selector.strip():
        raise ValueError(
            "P10_PROSPECTIVE_COMPOSITION_SELECTOR_MISSING"
        )
    if max_actions != 450:
        raise ValueError(
            "P10_PROSPECTIVE_COMPOSITION_STANDARD_BUDGET_REQUIRED"
        )
    environments_dir = environments_dir.resolve()
    bundle_dir = bundle_dir.resolve()
    if not environments_dir.is_dir():
        raise FileNotFoundError(
            f"sample environment directory not found: {environments_dir}"
        )
    if not bundle_dir.is_dir():
        raise FileNotFoundError(
            f"P10 bundle directory not found: {bundle_dir}"
        )

    composition_audit = _json(composition_audit_path)
    composition_digest = _composition_digest(composition_audit)
    removal_controls = composition_audit.get("removal_controls")
    if not isinstance(removal_controls, Mapping):
        raise TypeError("prospective removal controls invalid")
    baseline_completed = int(
        removal_controls.get(
            "without_composition_gate_completed_levels",
            -1,
        )
    )
    baseline_total = int(
        removal_controls.get(
            "without_composition_gate_total_levels",
            -1,
        )
    )
    active_manifest_path = bundle_dir / "p10_manifest.json"
    candidate_manifest_path = (
        bundle_dir / P10_CANDIDATE_MANIFEST_FILENAME
    )
    candidate_body_path = (
        bundle_dir / P10_PROSPECTIVE_COMPOSITION_HYBRID_FILENAME
    )
    active_manifest_bytes = active_manifest_path.read_bytes()
    active_manifest = _json(active_manifest_path)
    active_manifest_digest = active_p10_manifest_digest(bundle_dir)
    active_bundles = active_manifest.get("bundles")
    if not isinstance(active_bundles, Mapping):
        raise TypeError("active P10 manifest bundles invalid")
    active_file_bytes: dict[str, bytes] = {}
    for entry in active_bundles.values():
        if not isinstance(entry, Mapping):
            raise TypeError("active P10 manifest entry invalid")
        filename = entry.get("filename")
        if not isinstance(filename, str):
            raise TypeError("active P10 manifest filename invalid")
        active_file_bytes[filename] = (bundle_dir / filename).read_bytes()

    prior_candidate_manifest = (
        candidate_manifest_path.read_bytes()
        if candidate_manifest_path.is_file()
        else None
    )
    prior_candidate_body = (
        candidate_body_path.read_bytes()
        if candidate_body_path.is_file()
        else None
    )
    proposal, evidence = _proposal_and_evidence(
        active_manifest=active_manifest,
        active_manifest_digest=active_manifest_digest,
        composition_audit=composition_audit,
        composition_digest=composition_digest,
    )
    archive_dir = output_path.parent / "candidate_archive"
    candidate_slot_retained = False
    try:
        authority, compile_decision, compile_directive = (
            _compile_authorization(proposal, evidence)
        )
        candidate_manifest = (
            compile_p10_prospective_composition_hybrid_candidate(
                base_bundle_dir=bundle_dir,
                output_dir=bundle_dir,
                compile_directive=compile_directive,
                compile_decision=compile_decision,
                hds_authority=authority,
                composition_audit_digest=composition_digest,
            )
        )
        with tempfile.TemporaryDirectory() as temporary:
            rebuild_dir = Path(temporary)
            (
                rebuild_authority,
                rebuild_decision,
                rebuild_directive,
            ) = _compile_authorization(proposal, evidence)
            rebuilt_manifest = (
                compile_p10_prospective_composition_hybrid_candidate(
                    base_bundle_dir=bundle_dir,
                    output_dir=rebuild_dir,
                    compile_directive=rebuild_directive,
                    compile_decision=rebuild_decision,
                    hds_authority=rebuild_authority,
                    composition_audit_digest=composition_digest,
                )
            )
            if rebuilt_manifest != candidate_manifest:
                raise RuntimeError(
                    "P10_PROSPECTIVE_CANDIDATE_MANIFEST_REBUILD_MISMATCH"
                )
            candidate_bundles = candidate_manifest.get("bundles")
            if not isinstance(candidate_bundles, Mapping):
                raise TypeError("candidate P10 manifest bundles invalid")
            filenames = {
                P10_CANDIDATE_MANIFEST_FILENAME,
                *(
                    str(entry["filename"])
                    for entry in candidate_bundles.values()
                    if isinstance(entry, Mapping)
                    and isinstance(entry.get("filename"), str)
                ),
            }
            rebuild_hashes: dict[str, str] = {}
            for filename in sorted(filenames):
                committed = bundle_dir / filename
                rebuilt = rebuild_dir / filename
                if committed.read_bytes() != rebuilt.read_bytes():
                    raise RuntimeError(
                        "P10_PROSPECTIVE_CANDIDATE_BYTE_REBUILD_MISMATCH:"
                        + filename
                    )
                rebuild_hashes[filename] = _file_digest(committed)
        rebuild_digest = digest_object(rebuild_hashes)
        candidate_mapping = _json(candidate_body_path)
        candidate = _candidate_descriptor(
            active_manifest=active_manifest,
            candidate_manifest=candidate_manifest,
            candidate_mapping=candidate_mapping,
            proposal=proposal,
            rebuild_digest=rebuild_digest,
        )
        clear_p10_instruction_body_caches()
        probe_decision = authority.decide(
            proposal,
            status="PROBE",
            reason_codes=(
                "candidate-isolated-from-active-manifest",
                "standard-budget-target-double-run",
                "active-removal-control-content-bound",
            ),
            candidate_bundle=candidate,
        )
        candidate_first = _execute_candidate(
            environments_dir=environments_dir,
            environment_selector=environment_selector,
            max_actions=max_actions,
            runner=runner,
            authority=authority,
            decision=probe_decision,
            candidate=candidate,
        )
        candidate_second = _execute_candidate(
            environments_dir=environments_dir,
            environment_selector=environment_selector,
            max_actions=max_actions,
            runner=runner,
            authority=authority,
            decision=probe_decision,
            candidate=candidate,
        )
        active_manifest_unchanged = (
            active_manifest_path.read_bytes() == active_manifest_bytes
            and all(
                (bundle_dir / filename).read_bytes() == content
                for filename, content in active_file_bytes.items()
            )
        )
        candidate_reproducible = candidate_first == candidate_second
        candidate_completed = _integer(
            candidate_first["completed_levels"],
            "candidate completed levels",
        )
        candidate_total = _integer(
            candidate_first["total_levels"],
            "candidate total levels",
        )
        evaluation = {
            "baseline_completed_levels": baseline_completed,
            "baseline_total_levels": baseline_total,
            "candidate_completed_levels": candidate_completed,
            "candidate_total_levels": candidate_total,
            "completion_delta": (
                candidate_completed - baseline_completed
            ),
            "target_improved": (
                candidate_completed > baseline_completed
            ),
            "target_all_complete": (
                candidate_first["all_complete"] is True
                and candidate_completed == candidate_total
                and candidate_total == baseline_total
            ),
            "candidate_errors_zero": (
                candidate_first["error_count"] == 0
                and candidate_second["error_count"] == 0
            ),
            "candidate_within_standard_budget": (
                _integer(
                    candidate_first["actions"],
                    "candidate actions",
                )
                <= max_actions
                and candidate_first["max_action_exhausted"] is False
            ),
            "composition_executed": (
                _integer(
                    candidate_first["composition_action_count"],
                    "composition action count",
                )
                > 0
            ),
            "candidate_reproducible": candidate_reproducible,
            "active_manifest_unchanged": active_manifest_unchanged,
            "deterministic_rebuild_pass": True,
        }
        bounded_positive = all(
            value is True
            for key, value in evaluation.items()
            if key
            not in {
                "baseline_completed_levels",
                "baseline_total_levels",
                "candidate_completed_levels",
                "candidate_total_levels",
                "completion_delta",
            }
        )
        evaluation["bounded_positive"] = bounded_positive
        final_status = "HOLD" if bounded_positive else "REJECT"
        final_reasons = (
            (
                "target-completion-improved-reproducibly",
                "all-retained-sample-regression-required-before-promotion",
                "active-p-remains-unchanged",
            )
            if bounded_positive
            else (
                "target-candidate-gate-failed",
                *(
                    key
                    for key, passed in evaluation.items()
                    if isinstance(passed, bool) and not passed
                ),
                "active-p-remains-unchanged",
            )
        )
        final_decision = authority.decide(
            proposal,
            status=final_status,
            reason_codes=tuple(str(item) for item in final_reasons),
            candidate_bundle=candidate,
        )

        archive_dir.mkdir(parents=True, exist_ok=True)
        archived_body_path = (
            archive_dir / P10_PROSPECTIVE_COMPOSITION_HYBRID_FILENAME
        )
        archived_manifest_path = (
            archive_dir
            / "p10_candidate_manifest_prospective_composition_v1.json"
        )
        shutil.copyfile(candidate_body_path, archived_body_path)
        _write_json(archived_manifest_path, candidate_manifest)
        if final_status == "REJECT":
            _restore_candidate_slot(
                candidate_manifest_path=candidate_manifest_path,
                candidate_body_path=candidate_body_path,
                prior_manifest=prior_candidate_manifest,
                prior_body=prior_candidate_body,
            )
        else:
            candidate_slot_retained = True

        body: dict[str, object] = {
            "schema_version": (
                P10_PROSPECTIVE_COMPOSITION_CANDIDATE_WORKFLOW_SCHEMA_VERSION
            ),
            "artifact_type": (
                "arc3_p10_prospective_composition_candidate_intervention"
            ),
            "phase": "P10_COMPLETE_ARC3_SAMPLE_SOLVING",
            "development_only": True,
            "runtime_use": "FORBIDDEN",
            "operation_mode": "offline",
            "instruction_variant": "hybrid",
            "active_manifest_digest": active_manifest_digest,
            "composition_audit_digest": composition_digest,
            "proposal": dataclasses.asdict(proposal),
            "proposal_digest": proposal.digest,
            "evidence_set": dataclasses.asdict(evidence),
            "evidence_set_digest": evidence.digest,
            "compile_decision": _decision_mapping(compile_decision),
            "compile_decision_digest": compile_decision.digest,
            "compile_directive_digest": compile_directive.digest,
            "compiler_version": (
                P10_PROSPECTIVE_COMPOSITION_COMPILER_VERSION
            ),
            "candidate_manifest": candidate_manifest,
            "candidate_manifest_digest": digest_object(
                candidate_manifest
            ),
            "candidate_descriptor": dataclasses.asdict(candidate),
            "candidate_descriptor_digest": candidate.digest,
            "deterministic_rebuild_digest": rebuild_digest,
            "probe_decision": _decision_mapping(probe_decision),
            "probe_decision_digest": probe_decision.digest,
            "target_selector_digest": digest_object(
                environment_selector
            ),
            "target_max_actions": max_actions,
            "runs": {
                "candidate_first": candidate_first,
                "candidate_second": candidate_second,
            },
            "evaluation": evaluation,
            "hds_judgment": {
                **_decision_mapping(final_decision),
                "all_sample_regression_authorized": bounded_positive,
                "runtime_p_promotion_authorized": False,
                "score_progress_claim_authorized": False,
                "candidate_slot_retained": candidate_slot_retained,
            },
            "candidate_archive": {
                "body_filename": archived_body_path.name,
                "body_sha256": _file_digest(archived_body_path),
                "manifest_filename": archived_manifest_path.name,
                "manifest_sha256": _file_digest(
                    archived_manifest_path
                ),
            },
            "active_manifest_changed": not active_manifest_unchanged,
        }
        result = {
            **body,
            "content_digest": _WORKFLOW_DIGEST_PREFIX
            + digest_object(body),
        }
        _write_json(output_path, result)
        return result
    except Exception:
        _restore_candidate_slot(
            candidate_manifest_path=candidate_manifest_path,
            candidate_body_path=candidate_body_path,
            prior_manifest=prior_candidate_manifest,
            prior_body=prior_candidate_body,
        )
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compile and double-run the prospective composition target "
            "without promotion."
        )
    )
    parser.add_argument("--environments-dir", type=Path, required=True)
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--composition-audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--max-actions", type=int, default=450)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    output = execute_p10_prospective_composition_candidate_workflow(
        environments_dir=args.environments_dir,
        bundle_dir=args.bundle_dir,
        composition_audit_path=args.composition_audit,
        output_path=args.output,
        environment_selector=args.target,
        max_actions=args.max_actions,
    )
    print(output["content_digest"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "P10_PROSPECTIVE_COMPOSITION_CANDIDATE_WORKFLOW_SCHEMA_VERSION",
    "execute_p10_prospective_composition_candidate_workflow",
    "main",
]
