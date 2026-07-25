"""HDS-controlled C2+C10 candidate compile and OFFLINE intervention audit.

The workflow compiles only candidate P-A, compares it with unchanged active
P-A under identical retained-sample conditions, and never promotes. A failed
or rejected probe restores the previous candidate slot byte-for-byte.
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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from p10_main import run_p10_offline_samples

from .instruction_body import (
    clear_p10_instruction_body_caches,
    instruction_body_from_mapping,
)
from .p10_c2_c10_composition_audit import (
    C2_C10_COMPOSITION_AUDIT_SCHEMA_VERSION,
)
from .p10_instruction_compiler import (
    P10_C2_C10_CANDIDATE_SET_VERSION,
    P10_C2_C10_COMPILER_VERSION,
    P10_C2_C10_SYMBOLIC_FILENAME,
    P10_CANDIDATE_MANIFEST_FILENAME,
    P10_COMPILER_SEED,
    active_p10_manifest_digest,
    compile_p10_c2_c10_symbolic_candidate,
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

P10_C2_C10_CANDIDATE_WORKFLOW_SCHEMA_VERSION = (
    "arc3-p10-c2-c10-candidate-intervention-v1"
)
_COMPOSITION_DIGEST_PREFIX = "arc3_p10_c2_c10_composition_audit:"
_WORKFLOW_DIGEST_PREFIX = "arc3_p10_c2_c10_candidate_intervention:"
_ProbeCohort = Literal["stable", "discovery", "held-out"]
_RunFunction = Callable[..., dict[str, Any]]


@dataclass(frozen=True, slots=True)
class P10C2C10Probe:
    """One development-only retained-sample intervention condition."""

    environment_selector: str
    cohort: _ProbeCohort
    max_actions: int = 450

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not self.environment_selector.strip():
            failures.append("C2_C10_PROBE_SELECTOR_MISSING")
        if self.cohort not in {"stable", "discovery", "held-out"}:
            failures.append("C2_C10_PROBE_COHORT_INVALID")
        if self.max_actions < 2:
            failures.append("C2_C10_PROBE_ACTION_BUDGET_INVALID")
        return tuple(failures)


def _json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
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
    judgment = composition_audit.get("hds_judgment")
    integrity = composition_audit.get("integrity_checks")
    composable = composition_audit.get("composable_checks")
    failures: list[str] = []
    if (
        composition_audit.get("schema_version")
        != C2_C10_COMPOSITION_AUDIT_SCHEMA_VERSION
    ):
        failures.append("C2_C10_COMPOSITION_SCHEMA_INVALID")
    if not _content_digest_valid(
        composition_audit,
        _COMPOSITION_DIGEST_PREFIX,
    ):
        failures.append("C2_C10_COMPOSITION_DIGEST_INVALID")
    if composition_audit.get("candidate_tier") != "COMPOSABLE":
        failures.append("C2_C10_COMPOSITION_TIER_NOT_COMPOSABLE")
    if composition_audit.get("development_only") is not True:
        failures.append("C2_C10_COMPOSITION_DEVELOPMENT_BOUNDARY_INVALID")
    if composition_audit.get("runtime_use") != "FORBIDDEN":
        failures.append("C2_C10_COMPOSITION_RUNTIME_BOUNDARY_INVALID")
    if not isinstance(integrity, Mapping) or not integrity or not all(
        value is True for value in integrity.values()
    ):
        failures.append("C2_C10_COMPOSITION_INTEGRITY_NOT_PASS")
    if not isinstance(composable, Mapping) or not composable or not all(
        value is True for value in composable.values()
    ):
        failures.append("C2_C10_COMPOSITION_REMOVAL_GATE_NOT_PASS")
    if not isinstance(judgment, Mapping):
        failures.append("C2_C10_COMPOSITION_HDS_JUDGMENT_MISSING")
    else:
        if judgment.get("composable_status") != "PASS":
            failures.append("C2_C10_COMPOSITION_HDS_STATUS_NOT_PASS")
        if (
            judgment.get("runtime_p_candidate_compile_authorized")
            is not True
        ):
            failures.append("C2_C10_CANDIDATE_COMPILE_NOT_AUTHORIZED")
        if judgment.get("runtime_p_active_compile_authorized") is not False:
            failures.append("C2_C10_ACTIVE_COMPILE_BOUNDARY_INVALID")
        if judgment.get("runtime_p_promotion_authorized") is not False:
            failures.append("C2_C10_PROMOTION_BOUNDARY_INVALID")
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
    p_a = bundles.get("P-A")
    if not isinstance(p_a, Mapping):
        raise TypeError("active P10 P-A entry invalid")
    source_evidence = composition_audit.get("source_evidence")
    judgment = composition_audit.get("hds_judgment")
    removal = composition_audit.get("removal_evaluation")
    if not isinstance(source_evidence, Mapping):
        raise TypeError("C2+C10 source evidence invalid")
    if not isinstance(judgment, Mapping):
        raise TypeError("C2+C10 HDS judgment invalid")
    if not isinstance(removal, Mapping):
        raise TypeError("C2+C10 removal evaluation invalid")

    source_refs = tuple(
        str(source_evidence[key])
        for key in sorted(source_evidence)
        if str(source_evidence[key]).strip()
    )
    proposal = PUpdateProposal(
        proposal_id="proposal:c2-c10-symbolic-context",
        source_p_version=str(p_a.get("body_version", "")),
        source_p_digest=active_manifest_digest,
        target_component="P-A",
        update_type="symbolic-capability-composition",
        evidence_refs=(composition_digest, *source_refs),
        expected_effect=(
            "bounded-visible-context-reopens-nonhazard-action"
        ),
        expected_affected_capabilities=(
            "visible-effect-context-exploration",
        ),
        expected_unaffected_capabilities=(
            "active-runtime-manifest",
            "parametric-instruction-body",
            "hybrid-instruction-body",
            "global-hazard-block",
        ),
        falsifiers=(
            "target-completion-does-not-increase",
            "stable-completion-decreases",
            "candidate-rerun-differs",
            "active-manifest-changes",
        ),
        rollback_target=str(p_a.get("body_version", "")),
        provenance=(
            composition_digest,
            "development-memory:hds-accepted-composition",
        ),
    )
    removal_digest = digest_object(removal)
    evidence = PUpdateEvidenceSet(
        evidence_set_id="evidence-set:c2-c10-symbolic-context",
        proposal_digest=proposal.digest,
        memory_snapshot_digest=(
            "development-memory-snapshot:"
            + digest_object(
                {
                    "composition": composition_digest,
                    "source_evidence": source_refs,
                }
            )
        ),
        approved_memory_refs=(composition_digest, *source_refs),
        hds_memory_decision_digests=(
            "hds-memory-decision:" + digest_object(judgment),
        ),
        failure_refs=(
            "failure:visible-context-ambiguity:" + removal_digest,
        ),
        contradiction_refs=(
            "contradiction:action-only-context-removal:"
            + removal_digest,
        ),
        positive_contrast_refs=(
            "contrast:c2-c10-full:" + removal_digest,
        ),
        negative_contrast_refs=(
            "contrast:remove-c2:" + removal_digest,
            "contrast:remove-c10:" + removal_digest,
        ),
        holdout_refs=(
            "holdout:mechanism-transfer:" + removal_digest,
        ),
        replay_audit_refs=(
            "audit:runtime-identity-free-boundary:"
            + digest_object(
                composition_audit.get("candidate_contract")
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
            "c2-c10-composable-removal-gate-pass",
            "candidate-p-a-only",
            "active-p-remains-unchanged",
        ),
        evidence_set=evidence,
    )
    directive = authority.issue_compile_directive(
        proposal,
        evidence,
        decision,
        target_body_version=P10_C2_C10_CANDIDATE_SET_VERSION,
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
    active = active_bundles.get("P-A")
    candidate = candidate_bundles.get("P-A")
    if not isinstance(active, Mapping) or not isinstance(
        candidate,
        Mapping,
    ):
        raise TypeError("P10 P-A manifest entry invalid")
    candidate_body = instruction_body_from_mapping(candidate_mapping)
    descriptor = CandidatePBundle(
        candidate_id="candidate:p10-c2-c10-symbolic-context",
        proposal_digest=proposal.digest,
        compile_directive_digest=str(
            candidate_manifest.get("compile_directive_digest", "")
        ),
        target_component="P-A",
        body_version=str(candidate.get("body_version", "")),
        body_digest=str(candidate.get("content_digest", "")),
        source_body_version=str(active.get("body_version", "")),
        source_body_digest=str(active.get("content_digest", "")),
        provenance_digest=candidate_body.provenance_digest,
        manifest_digest=digest_object(candidate_manifest),
        deterministic_rebuild_digest=rebuild_digest,
        rollback_target=str(active.get("body_version", "")),
    )
    failures = descriptor.validate()
    if failures:
        raise ValueError(";".join(failures))
    return descriptor


def _compact_run(
    result: Mapping[str, Any],
    *,
    probe: P10C2C10Probe,
    instruction_lifecycle: str,
) -> dict[str, object]:
    reports = result.get("reports")
    errors = result.get("errors")
    if not isinstance(reports, list) or not isinstance(errors, list):
        raise TypeError("C2+C10 intervention result shape invalid")
    report = reports[0] if len(reports) == 1 else {}
    if not isinstance(report, Mapping):
        raise TypeError("C2+C10 intervention report invalid")
    core: dict[str, object] = {
        "selector_digest": digest_object(probe.environment_selector),
        "cohort": probe.cohort,
        "operation_mode": result.get("operation_mode"),
        "instruction_lifecycle": instruction_lifecycle,
        "instruction_variant": result.get("instruction_variant"),
        "max_actions": probe.max_actions,
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
        "instruction_body_versions": sorted(
            {
                str(item)
                for item in report.get("instruction_body_versions", [])
            }
        ),
        "instruction_body_digests": sorted(
            {
                str(item)
                for item in report.get("instruction_body_digests", [])
            }
        ),
        "instruction_query_digests_digest": digest_object(
            report.get("instruction_query_digests", [])
        ),
        "emitted_steps_digest": digest_object(
            report.get("emitted_steps", [])
        ),
        "trace_digests_digest": digest_object(
            report.get("trace_digests", [])
        ),
        "transition_probe_digest": digest_object(
            report.get("development_transition_probe", {})
        ),
        "errors_digest": digest_object(errors),
    }
    return {
        **core,
        "run_digest": "p10-c2-c10-intervention-run:"
        + digest_object(core),
    }


def _execute_probe(
    *,
    environments_dir: Path,
    probe: P10C2C10Probe,
    instruction_lifecycle: Literal["active", "candidate"],
    runner: _RunFunction,
    authority: HDSPUpdateAuthority | None = None,
    decision: PUpdateDecision | None = None,
    candidate: CandidatePBundle | None = None,
) -> dict[str, object]:
    result = runner(
        environments_dir=environments_dir,
        requested_games=[probe.environment_selector],
        max_actions=probe.max_actions,
        instruction_variant="P-A",
        instruction_lifecycle=instruction_lifecycle,
        p_update_authority=authority,
        p_update_decision=decision,
        candidate_bundle=candidate,
    )
    return _compact_run(
        result,
        probe=probe,
        instruction_lifecycle=instruction_lifecycle,
    )


def _run_twice(
    *,
    environments_dir: Path,
    probes: tuple[P10C2C10Probe, ...],
    instruction_lifecycle: Literal["active", "candidate"],
    runner: _RunFunction,
    authority: HDSPUpdateAuthority | None = None,
    decision: PUpdateDecision | None = None,
    candidate: CandidatePBundle | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    def run_once() -> list[dict[str, object]]:
        return [
            _execute_probe(
                environments_dir=environments_dir,
                probe=probe,
                instruction_lifecycle=instruction_lifecycle,
                runner=runner,
                authority=authority,
                decision=decision,
                candidate=candidate,
            )
            for probe in probes
        ]

    return run_once(), run_once()


def _integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    return value


def _evaluate_runs(
    *,
    probes: tuple[P10C2C10Probe, ...],
    active_first: list[dict[str, object]],
    active_second: list[dict[str, object]],
    candidate_first: list[dict[str, object]],
    candidate_second: list[dict[str, object]],
    active_manifest_unchanged: bool,
) -> dict[str, object]:
    if not (
        len(probes)
        == len(active_first)
        == len(active_second)
        == len(candidate_first)
        == len(candidate_second)
    ):
        raise ValueError("C2_C10_INTERVENTION_RUN_COUNT_MISMATCH")

    stable_indices = tuple(
        index
        for index, probe in enumerate(probes)
        if probe.cohort == "stable"
    )
    target_indices = tuple(
        index
        for index, probe in enumerate(probes)
        if probe.cohort != "stable"
    )
    held_out_indices = tuple(
        index
        for index, probe in enumerate(probes)
        if probe.cohort == "held-out"
    )

    def completed(run: Mapping[str, object]) -> int:
        return _integer(run.get("completed_levels"), "completed levels")

    def errors(run: Mapping[str, object]) -> int:
        return _integer(run.get("error_count"), "error count")

    active_reproducible = active_first == active_second
    candidate_reproducible = candidate_first == candidate_second
    candidate_errors_zero = all(errors(run) == 0 for run in candidate_first)
    active_errors_zero = all(errors(run) == 0 for run in active_first)
    stable_non_regression = all(
        completed(candidate_first[index]) >= completed(active_first[index])
        and errors(candidate_first[index]) == 0
        and (
            not bool(active_first[index]["all_complete"])
            or bool(candidate_first[index]["all_complete"])
        )
        for index in stable_indices
    )
    held_out_non_degradation = all(
        completed(candidate_first[index]) >= completed(active_first[index])
        and errors(candidate_first[index]) == 0
        for index in held_out_indices
    )
    baseline_target_value = sum(
        completed(active_first[index]) for index in target_indices
    )
    candidate_target_value = sum(
        completed(candidate_first[index]) for index in target_indices
    )
    baseline_stable_value = sum(
        completed(active_first[index]) for index in stable_indices
    )
    candidate_stable_value = sum(
        completed(candidate_first[index]) for index in stable_indices
    )
    baseline_held_out_value = sum(
        completed(active_first[index]) for index in held_out_indices
    )
    candidate_held_out_value = sum(
        completed(candidate_first[index]) for index in held_out_indices
    )
    target_improved = candidate_target_value > baseline_target_value
    bounded_positive = all(
        (
            active_reproducible,
            candidate_reproducible,
            active_errors_zero,
            candidate_errors_zero,
            stable_non_regression,
            held_out_non_degradation,
            target_improved,
            active_manifest_unchanged,
        )
    )
    return {
        "baseline_target_completed": baseline_target_value,
        "candidate_target_completed": candidate_target_value,
        "target_completion_delta": (
            candidate_target_value - baseline_target_value
        ),
        "target_improved": target_improved,
        "baseline_stable_completed": baseline_stable_value,
        "candidate_stable_completed": candidate_stable_value,
        "stable_completion_delta": (
            candidate_stable_value - baseline_stable_value
        ),
        "stable_non_regression": stable_non_regression,
        "baseline_held_out_completed": baseline_held_out_value,
        "candidate_held_out_completed": candidate_held_out_value,
        "held_out_completion_delta": (
            candidate_held_out_value - baseline_held_out_value
        ),
        "held_out_non_degradation": held_out_non_degradation,
        "active_reproducible": active_reproducible,
        "candidate_reproducible": candidate_reproducible,
        "active_errors_zero": active_errors_zero,
        "candidate_errors_zero": candidate_errors_zero,
        "active_manifest_unchanged": active_manifest_unchanged,
        "bounded_positive": bounded_positive,
    }


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


def execute_p10_c2_c10_candidate_workflow(
    *,
    environments_dir: Path,
    bundle_dir: Path,
    composition_audit_path: Path,
    output_path: Path,
    probes: tuple[P10C2C10Probe, ...],
    runner: _RunFunction = run_p10_offline_samples,
) -> dict[str, object]:
    """Compile and probe candidate P-A; never mutate or promote active P."""

    failures = [
        failure
        for probe in probes
        for failure in probe.validate()
    ]
    selectors = tuple(probe.environment_selector for probe in probes)
    cohorts = {probe.cohort for probe in probes}
    if len(set(selectors)) != len(selectors):
        failures.append("C2_C10_PROBE_SELECTOR_DUPLICATED")
    if not {"stable", "discovery", "held-out"}.issubset(cohorts):
        failures.append("C2_C10_PROBE_COHORT_COVERAGE_INCOMPLETE")
    if sum(probe.cohort == "held-out" for probe in probes) < 2:
        failures.append("C2_C10_HELD_OUT_PROBE_COUNT_INSUFFICIENT")
    if failures:
        raise ValueError(";".join(sorted(set(failures))))

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

    composition_audit = _json_object(composition_audit_path)
    composition_digest = _composition_digest(composition_audit)
    active_manifest_path = bundle_dir / "p10_manifest.json"
    candidate_manifest_path = (
        bundle_dir / P10_CANDIDATE_MANIFEST_FILENAME
    )
    candidate_body_path = bundle_dir / P10_C2_C10_SYMBOLIC_FILENAME
    active_manifest_bytes = active_manifest_path.read_bytes()
    active_manifest = _json_object(active_manifest_path)
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
    archive_dir = output_path.parent / "c2_c10_candidate_archive"
    candidate_slot_retained = False
    try:
        authority, compile_decision, compile_directive = (
            _compile_authorization(proposal, evidence)
        )
        candidate_manifest = compile_p10_c2_c10_symbolic_candidate(
            base_bundle_dir=bundle_dir,
            output_dir=bundle_dir,
            compile_directive=compile_directive,
            compile_decision=compile_decision,
            hds_authority=authority,
            composition_audit_digest=composition_digest,
        )
        with tempfile.TemporaryDirectory() as temporary:
            rebuild_dir = Path(temporary)
            (
                rebuild_authority,
                rebuild_decision,
                rebuild_directive,
            ) = _compile_authorization(proposal, evidence)
            rebuilt_manifest = compile_p10_c2_c10_symbolic_candidate(
                base_bundle_dir=bundle_dir,
                output_dir=rebuild_dir,
                compile_directive=rebuild_directive,
                compile_decision=rebuild_decision,
                hds_authority=rebuild_authority,
                composition_audit_digest=composition_digest,
            )
            if rebuilt_manifest != candidate_manifest:
                raise RuntimeError(
                    "C2_C10_CANDIDATE_MANIFEST_REBUILD_MISMATCH"
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
                        "C2_C10_CANDIDATE_BYTE_REBUILD_MISMATCH:"
                        + filename
                    )
                rebuild_hashes[filename] = _file_digest(committed)
        rebuild_digest = digest_object(rebuild_hashes)
        candidate_mapping = _json_object(candidate_body_path)
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
                "same-condition-active-removal-control",
                "stable-discovery-held-out-double-run",
            ),
            candidate_bundle=candidate,
        )
        active_first, active_second = _run_twice(
            environments_dir=environments_dir,
            probes=probes,
            instruction_lifecycle="active",
            runner=runner,
        )
        candidate_first, candidate_second = _run_twice(
            environments_dir=environments_dir,
            probes=probes,
            instruction_lifecycle="candidate",
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
        evaluation = _evaluate_runs(
            probes=probes,
            active_first=active_first,
            active_second=active_second,
            candidate_first=candidate_first,
            candidate_second=candidate_second,
            active_manifest_unchanged=active_manifest_unchanged,
        )
        bounded_positive = evaluation["bounded_positive"] is True
        final_status = "HOLD" if bounded_positive else "REJECT"
        final_reasons = (
            (
                "bounded-intervention-positive",
                "all-sample-regression-required-before-promotion",
                "active-p-remains-unchanged",
            )
            if bounded_positive
            else (
                "bounded-intervention-promotion-gate-failed",
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
        archived_body_path = archive_dir / P10_C2_C10_SYMBOLIC_FILENAME
        archived_manifest_path = (
            archive_dir / "p10_candidate_manifest_c2_c10_v1.json"
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
                P10_C2_C10_CANDIDATE_WORKFLOW_SCHEMA_VERSION
            ),
            "artifact_type": (
                "arc3_p10_c2_c10_candidate_intervention"
            ),
            "phase": "P10_COMPLETE_ARC3_SAMPLE_SOLVING",
            "development_only": True,
            "runtime_use": "FORBIDDEN",
            "operation_mode": "offline",
            "instruction_variant": "P-A",
            "active_manifest_digest": active_manifest_digest,
            "composition_audit_digest": composition_digest,
            "proposal": dataclasses.asdict(proposal),
            "proposal_digest": proposal.digest,
            "evidence_set": dataclasses.asdict(evidence),
            "evidence_set_digest": evidence.digest,
            "compile_decision": _decision_mapping(compile_decision),
            "compile_decision_digest": compile_decision.digest,
            "compile_directive_digest": compile_directive.digest,
            "compiler_version": P10_C2_C10_COMPILER_VERSION,
            "candidate_manifest": candidate_manifest,
            "candidate_manifest_digest": digest_object(
                candidate_manifest
            ),
            "candidate_descriptor": dataclasses.asdict(candidate),
            "candidate_descriptor_digest": candidate.digest,
            "deterministic_rebuild_digest": rebuild_digest,
            "probe_decision": _decision_mapping(probe_decision),
            "probe_decision_digest": probe_decision.digest,
            "probe_specs": [
                dataclasses.asdict(probe) for probe in probes
            ],
            "removal_controls": {
                "active_p_a_without_c10": True,
                "remove_c2_predictive_evidence_digest": (
                    digest_object(
                        composition_audit.get("removal_evaluation")
                    )
                ),
                "timer_or_path_selector_used": False,
                "fixed_result_label_transfer_used": False,
            },
            "runs": {
                "active_first": active_first,
                "active_second": active_second,
                "candidate_first": candidate_first,
                "candidate_second": candidate_second,
            },
            "evaluation": evaluation,
            "hds_judgment": {
                **_decision_mapping(final_decision),
                "bounded_all_sample_regression_authorized": (
                    bounded_positive
                ),
                "runtime_p_promotion_authorized": False,
                "score_progress_claim_authorized": False,
                "candidate_slot_retained": candidate_slot_retained,
            },
            "candidate_archive": {
                "body_filename": archived_body_path.name,
                "body_sha256": _file_digest(archived_body_path),
                "manifest_filename": archived_manifest_path.name,
                "manifest_sha256": _file_digest(archived_manifest_path),
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
            "Compile and probe the bounded C2+C10 candidate P-A without "
            "promotion."
        )
    )
    parser.add_argument("--environments-dir", type=Path, required=True)
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--composition-audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stable", action="append", default=[])
    parser.add_argument("--discovery", action="append", default=[])
    parser.add_argument("--held-out", action="append", default=[])
    parser.add_argument("--max-actions", type=int, default=450)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    probes = tuple(
        (
            P10C2C10Probe(selector, "stable", args.max_actions)
            for selector in args.stable
        )
    ) + tuple(
        P10C2C10Probe(selector, "discovery", args.max_actions)
        for selector in args.discovery
    ) + tuple(
        P10C2C10Probe(selector, "held-out", args.max_actions)
        for selector in args.held_out
    )
    output = execute_p10_c2_c10_candidate_workflow(
        environments_dir=args.environments_dir,
        bundle_dir=args.bundle_dir,
        composition_audit_path=args.composition_audit,
        output_path=args.output,
        probes=probes,
    )
    print(output["content_digest"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "P10C2C10Probe",
    "P10_C2_C10_CANDIDATE_WORKFLOW_SCHEMA_VERSION",
    "execute_p10_c2_c10_candidate_workflow",
]
