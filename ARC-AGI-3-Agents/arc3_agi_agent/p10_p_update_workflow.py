"""OFFLINE evidence-to-candidate workflow for the P10 P update lifecycle."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from arc_agi import Arcade, OperationMode  # type: ignore[import-untyped]

from agents.templates.p10_sample_agent import P10SampleAgent
from p10_main import run_p10_offline_samples

from .context import ContextSnapshot
from .instruction_body import (
    ParametricInstructionBody,
    instruction_body_from_mapping,
    load_p10_parametric_instruction_body,
)
from .ir import ObservationIR
from .memory import MemorySnapshot
from .p10_instruction_compiler import (
    P10_CANDIDATE_MANIFEST_FILENAME,
    P10_CANDIDATE_SET_VERSION,
    P10_COMPILER_SEED,
    active_p10_manifest_digest,
    compile_p10_instruction_bodies,
)
from .p_b_learning import (
    P_B_LEARNING_MEMORY_KEY,
    PBLearningDataset,
    PBLearningResult,
    build_p_b_learning_dataset,
    merge_p_b_learning_memory_snapshots,
    p_b_learning_memory_evidence_mapping,
    p_b_learning_memory_from_mapping,
    train_p_b_from_memory,
)
from .p_update import (
    CandidatePBundle,
    HDSPUpdateAuthority,
    InstructionBodyCompileDirective,
    PRegressionReport,
    PUpdateDecision,
    PUpdateEvidenceSet,
    PUpdateProposal,
)
from .protocol import AuthorityViolation, ComputeRequest
from .schema import digest_object

P10_P_UPDATE_WORKFLOW_SCHEMA_VERSION = "arc3-p10-p-update-workflow-v1"


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


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected object: {path}")
    return value


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True, slots=True)
class P10LearningProbe:
    environment_selector: str
    max_actions: int

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not self.environment_selector.strip():
            failures.append("P10_LEARNING_PROBE_SELECTOR_MISSING")
        if self.max_actions < 2:
            failures.append("P10_LEARNING_PROBE_ACTION_BUDGET_INVALID")
        return tuple(failures)


def _learning_kind_counts(snapshot: MemorySnapshot) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for entry in snapshot.entries:
        payload = entry.payload
        learning = payload.get(P_B_LEARNING_MEMORY_KEY)
        if not isinstance(learning, dict):
            continue
        examples = learning.get("examples")
        if not isinstance(examples, list):
            continue
        for example in examples:
            if not isinstance(example, dict):
                continue
            kinds = example.get("evidence_kinds")
            if isinstance(kinds, list):
                counts.update(str(item) for item in kinds)
    return dict(sorted(counts.items()))


def collect_p10_learning_memory(
    *,
    environments_dir: Path,
    probes: tuple[P10LearningProbe, ...],
) -> tuple[MemorySnapshot, tuple[dict[str, object], ...]]:
    """Run bounded active-P probes and return a merged identity-free M view."""

    if len(probes) < 2:
        raise ValueError("P10_P_UPDATE_REQUIRES_MULTIPLE_PROBES")
    failures = [
        failure
        for probe in probes
        for failure in probe.validate()
    ]
    if failures:
        raise ValueError(";".join(failures))
    if os.getenv("OPERATION_MODE", "").strip().casefold() == "competition":
        raise AuthorityViolation("COMPETITION_MODE_ENV_FORBIDDEN_DURING_P10")
    resolved_environment_dir = environments_dir.resolve()
    if not resolved_environment_dir.is_dir():
        raise FileNotFoundError(
            f"sample environment directory not found: {resolved_environment_dir}"
        )
    arcade = Arcade(
        operation_mode=OperationMode.OFFLINE,
        environments_dir=str(resolved_environment_dir),
    )
    if arcade.operation_mode is not OperationMode.OFFLINE:
        raise AuthorityViolation("OFFLINE_SAMPLE_MODE_NOT_EFFECTIVE")
    scorecard_id = arcade.open_scorecard(
        tags=["p10", "p-update-learning-memory"]
    )
    snapshots: list[MemorySnapshot] = []
    summaries: list[dict[str, object]] = []
    try:
        for index, probe in enumerate(probes):
            environment = arcade.make(
                probe.environment_selector,
                scorecard_id=scorecard_id,
                save_recording=False,
                include_frame_data=True,
            )
            if environment is None:
                raise RuntimeError("OFFLINE_SAMPLE_ENVIRONMENT_LOAD_FAILED")
            agent = P10SampleAgent(
                card_id=scorecard_id,
                game_id=probe.environment_selector,
                agent_name="p10-p-update-memory",
                ROOT_URL="",
                record=False,
                arc_env=environment,
                tags=["p10", "p-update-learning-memory"],
                operation_mode=OperationMode.OFFLINE,
                max_actions=probe.max_actions,
                instruction_variant="hybrid",
            )
            agent.main()
            report = agent.report()
            memory = agent.runtime.components.memory
            if memory is None:
                raise RuntimeError("P10_MEMORY_SUBJECT_REQUIRED")
            snapshot = memory.view()
            snapshots.append(snapshot)
            summary_core: dict[str, object] = {
                "probe_index": index,
                "operation_mode": "offline",
                "active_instruction_versions": sorted(
                    set(report.instruction_body_versions)
                ),
                "actions": report.actions,
                "completed_levels": report.levels_completed,
                "complete": report.complete,
                "max_action_exhausted": report.max_action_exhausted,
                "recoveries": report.recoveries,
                "memory_snapshot_digest": snapshot.digest,
                "learning_kind_counts": _learning_kind_counts(snapshot),
            }
            summaries.append(
                {
                    **summary_core,
                    "probe_digest": "p10-learning-probe:"
                    + digest_object(summary_core),
                }
            )
    finally:
        arcade.close_scorecard(scorecard_id)
    merged = merge_p_b_learning_memory_snapshots(tuple(snapshots))
    return merged, tuple(summaries)


def _proposal(bundle_dir: Path) -> PUpdateProposal:
    return PUpdateProposal(
        proposal_id=(
            "proposal:p10-multi-actor-shape-instruction-body-set"
        ),
        source_p_version="p10-active-instruction-body-set",
        source_p_digest=active_p10_manifest_digest(bundle_dir),
        target_component="instruction-body-set",
        update_type="symbolic-parametric-composition",
        evidence_refs=(
            "memory:approved-multi-episode-learning",
            "failure:remaining-level-multi-actor-selection-push-gap",
            (
                "contrast:single-actor-shape-model-versus-"
                "multi-actor-selection-closure"
            ),
        ),
        expected_effect=(
            "change-P-B-same-input-compute-and-compile-isolated-"
            "multi-actor-shape-candidate"
        ),
        expected_affected_capabilities=(
            "failure-conditioned-parametric-ranking",
            "multiple-marker-actor-selection",
            "actor-mediated-recursive-shape-push",
        ),
        expected_unaffected_capabilities=(
            "stable-rendered-relation-control",
            "stable-object-target-control",
            "stable-symbolic-rewrite",
            "stable-goal-aware-merge",
            "stable-selectable-object-target-push",
            "stable-selectable-multi-object-route",
            "stable-single-actor-shape-target-route",
        ),
        falsifiers=(
            "parameter-digest-unchanged",
            "same-input-output-unchanged",
            "holdout-degrades",
            "stable-capability-regresses",
        ),
        rollback_target="p10-active-instruction-body-set",
        provenance=(
            "HDS-authorized-runtime-memory",
            (
                "identity-free-rendered-multi-actor-shape-"
                "positive-negative-contrast"
            ),
        ),
    )


def _evidence_set(
    proposal: PUpdateProposal,
    memory: MemorySnapshot,
) -> PUpdateEvidenceSet:
    approved_refs = tuple(entry.target for entry in memory.entries)
    hds_refs = tuple(
        sorted(
            {
                value
                for entry in memory.entries
                for value in entry.provenance
                if value.startswith("hds-decision:")
            }
        )
    )
    return PUpdateEvidenceSet(
        evidence_set_id=(
            "evidence-set:p10-multi-actor-shape-p-update"
        ),
        proposal_digest=proposal.digest,
        memory_snapshot_digest=memory.digest,
        approved_memory_refs=approved_refs,
        hds_memory_decision_digests=hds_refs,
        failure_refs=(
            "failure:remaining-level-multi-actor-selection-push-gap",
        ),
        contradiction_refs=(
            "contradiction:single-actor-shape-model-incomplete",
        ),
        positive_contrast_refs=(
            "contrast:multi-actor-selection-shape-role-closure",
        ),
        negative_contrast_refs=(
            "contrast:single-actor-shape-operator-unavailable",
        ),
        holdout_refs=(
            "holdout:translated-layout-and-dynamic-footer",
        ),
        replay_audit_refs=("audit:no-id-no-replay-no-fixed-sequence",),
        provenance=(
            "runtime-memory:authorized",
            "multi-episode-content-addressed-merge",
        ),
    )


def _compile_authorization(
    proposal: PUpdateProposal,
    evidence_set: PUpdateEvidenceSet,
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
            "approved-memory-contains-multi-actor-contrasts",
            "identity-free-and-structural-holdout-partitioned",
        ),
        evidence_set=evidence_set,
    )
    directive = authority.issue_compile_directive(
        proposal,
        evidence_set,
        decision,
        target_body_version=P10_CANDIDATE_SET_VERSION,
        seed=P10_COMPILER_SEED,
    )
    return authority, decision, directive


def _candidate_files(manifest: dict[str, object]) -> tuple[str, ...]:
    bundles = manifest.get("bundles")
    if not isinstance(bundles, dict):
        raise TypeError("candidate manifest bundles invalid")
    filenames = []
    for entry in bundles.values():
        if not isinstance(entry, dict):
            raise TypeError("candidate manifest entry invalid")
        filename = entry.get("filename")
        if not isinstance(filename, str):
            raise TypeError("candidate manifest filename invalid")
        filenames.append(filename)
    return tuple(sorted((*filenames, P10_CANDIDATE_MANIFEST_FILENAME)))


def _same_input_c_probe(
    bundle_dir: Path,
    manifest: dict[str, object],
) -> dict[str, object]:
    """Run source and candidate P-B through the same compute-query input."""

    bundles = manifest.get("bundles")
    if not isinstance(bundles, dict):
        raise TypeError("candidate manifest bundles invalid")
    p_b_entry = bundles.get("P-B")
    if not isinstance(p_b_entry, dict):
        raise TypeError("candidate P-B manifest entry invalid")
    filename = p_b_entry.get("filename")
    if not isinstance(filename, str):
        raise TypeError("candidate P-B filename invalid")
    source = load_p10_parametric_instruction_body()
    candidate = instruction_body_from_mapping(_json(bundle_dir / filename))
    if not isinstance(candidate, ParametricInstructionBody):
        raise TypeError("candidate P-B body is not parametric")
    previous = ObservationIR(
        frame_signature="observation:p-b-same-input-previous",
        structural_signature="structure:p-b-same-input",
        mechanic_signature="mechanic:p-b-same-input",
        dimensions=(2, 2),
        available_actions=(1, 6),
        visible_effects=("VISIBLE_STATE_CHANGE",),
        terminal_state="NOT_FINISHED",
    )
    observation = ObservationIR(
        frame_signature="observation:p-b-same-input-current",
        structural_signature="structure:p-b-same-input",
        mechanic_signature="mechanic:p-b-same-input",
        dimensions=(2, 2),
        available_actions=(1, 6),
        visible_effects=("NO_VISIBLE_CHANGE",),
        terminal_state="NOT_FINISHED",
    )
    context = ContextSnapshot(
        current_observation=observation,
        previous_observation=previous,
        action_history=(1, 6),
        effect_history=(
            ("VISIBLE_STATE_CHANGE",),
            ("NO_VISIBLE_CHANGE",),
        ),
        hypotheses=(),
        failures=("bounded-observed-contradiction",),
        action_budget=16,
        actions_used=2,
        open_items=("effect-relation-unresolved",),
        version=3,
    )
    memory = MemorySnapshot(version=0, entries=())
    request = ComputeRequest(
        command_id="command:p-b-same-input",
        operation="LLM_COMPUTE",
        observation_signature=observation.frame_signature,
        context_signature=context.digest,
        memory_signature=memory.digest,
    )
    source_result = source.query(request, observation, context, memory)
    candidate_result = candidate.query(request, observation, context, memory)
    source_predictions = digest_object(source_result.predictions)
    candidate_predictions = digest_object(candidate_result.predictions)
    if source_predictions == candidate_predictions:
        raise RuntimeError("P10_P_B_SAME_INPUT_C_OUTPUT_UNCHANGED")
    return {
        "observation_digest": digest_object(observation),
        "context_digest": context.digest,
        "memory_digest": memory.digest,
        "source_body_digest": source.digest(),
        "candidate_body_digest": candidate.digest(),
        "source_prediction_digest": source_predictions,
        "candidate_prediction_digest": candidate_predictions,
        "changed": True,
        "attribution": (
            "same ParametricInstructionBody query input; P-B weights differ"
        ),
    }


def _candidate_descriptors(
    *,
    bundle_dir: Path,
    manifest: dict[str, object],
    proposal: PUpdateProposal,
    learning_result: PBLearningResult,
    rebuild_digest: str,
    same_input_c_probe: dict[str, object],
) -> tuple[CandidatePBundle, ...]:
    active_manifest = _json(bundle_dir / "p10_manifest.json")
    active_bundles = active_manifest.get("bundles")
    candidate_bundles = manifest.get("bundles")
    if not isinstance(active_bundles, dict) or not isinstance(
        candidate_bundles,
        dict,
    ):
        raise TypeError("P10 manifest bundles invalid")
    manifest_digest = digest_object(manifest)
    descriptors: list[CandidatePBundle] = []
    for variant in ("P-A", "P-B", "hybrid"):
        active = active_bundles.get(variant)
        candidate = candidate_bundles.get(variant)
        if not isinstance(active, dict) or not isinstance(candidate, dict):
            raise TypeError(f"P10 candidate variant invalid: {variant}")
        filename = candidate.get("filename")
        if not isinstance(filename, str):
            raise TypeError(f"P10 candidate filename invalid: {variant}")
        candidate_mapping = _json(bundle_dir / filename)
        candidate_body = instruction_body_from_mapping(candidate_mapping)
        is_parametric = variant in {"P-B", "hybrid"}
        descriptor = CandidatePBundle(
            candidate_id=f"candidate:p10-{variant.casefold()}",
            proposal_digest=proposal.digest,
            compile_directive_digest=str(
                manifest.get("compile_directive_digest", "")
            ),
            target_component=(
                "P-B" if variant == "P-B" else "hybrid-P-B"
                if variant == "hybrid"
                else "P-A"
            ),
            body_version=str(candidate.get("body_version", "")),
            body_digest=str(candidate.get("content_digest", "")),
            source_body_version=str(active.get("body_version", "")),
            source_body_digest=str(active.get("content_digest", "")),
            provenance_digest=candidate_body.provenance_digest,
            manifest_digest=manifest_digest,
            deterministic_rebuild_digest=rebuild_digest,
            rollback_target=str(active.get("body_version", "")),
            parameter_digest=(
                learning_result.candidate_parameter_digest
                if is_parametric
                else None
            ),
            predecessor_parameter_digest=(
                learning_result.source_parameter_digest
                if is_parametric
                else None
            ),
            same_input_predecessor_output_digest=(
                str(same_input_c_probe["source_prediction_digest"])
                if is_parametric
                else None
            ),
            same_input_candidate_output_digest=(
                str(same_input_c_probe["candidate_prediction_digest"])
                if is_parametric
                else None
            ),
            parameter_change_attribution=(
                learning_result.attribution if is_parametric else None
            ),
        )
        failures = descriptor.validate()
        if failures:
            raise ValueError(";".join(failures))
        descriptors.append(descriptor)
    return tuple(descriptors)


def _dataset_mapping(dataset: PBLearningDataset) -> dict[str, object]:
    core: dict[str, object] = {
        "schema_version": dataset.schema_version,
        "runtime_identity_free": dataset.runtime_identity_free,
        "dataset_id": dataset.dataset_id,
        "dataset_digest": dataset.digest,
        "memory_snapshot_digest": dataset.memory_snapshot_digest,
        "evidence_set_digest": dataset.evidence_set_digest,
        "replay_audit_digest": dataset.replay_audit_digest,
        "train_count": len(dataset.train),
        "holdout_count": len(dataset.holdout),
        "examples": [dataclasses.asdict(item) for item in dataset.examples],
    }
    return {
        **core,
        "content_digest": "p-b-learning-dataset-evidence:"
        + digest_object(core),
    }


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


def _required_int(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    return value


def _required_float(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"{field_name} must be numeric")
    return float(value)


def _compact_regression_run(
    result: dict[str, Any],
    *,
    probe_index: int,
    probe: P10LearningProbe,
    instruction_lifecycle: str,
) -> dict[str, object]:
    reports = result.get("reports")
    errors = result.get("errors")
    if not isinstance(reports, list) or not isinstance(errors, list):
        raise TypeError("P10 regression result shape invalid")
    report = reports[0] if len(reports) == 1 else {}
    if not isinstance(report, dict):
        raise TypeError("P10 regression report invalid")
    core: dict[str, object] = {
        "probe_index": probe_index,
        "probe_selector_digest": digest_object(probe.environment_selector),
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
        "emitted_steps_digest": digest_object(
            report.get("emitted_steps", [])
        ),
        "trace_digests_digest": digest_object(
            report.get("trace_digests", [])
        ),
        "errors_digest": digest_object(errors),
    }
    return {
        **core,
        "run_digest": "p10-regression-run:" + digest_object(core),
    }


def _execute_regression_run(
    *,
    environments_dir: Path,
    probe_index: int,
    probe: P10LearningProbe,
    instruction_lifecycle: str,
    authority: HDSPUpdateAuthority | None = None,
    decision: PUpdateDecision | None = None,
    candidate: CandidatePBundle | None = None,
) -> dict[str, object]:
    result = run_p10_offline_samples(
        environments_dir=environments_dir,
        requested_games=[probe.environment_selector],
        max_actions=probe.max_actions,
        instruction_variant="hybrid",
        instruction_lifecycle=(
            "candidate" if instruction_lifecycle == "candidate" else "active"
        ),
        p_update_authority=authority,
        p_update_decision=decision,
        candidate_bundle=candidate,
    )
    return _compact_regression_run(
        result,
        probe_index=probe_index,
        probe=probe,
        instruction_lifecycle=instruction_lifecycle,
    )


def _candidate_runtime_regression(
    *,
    environments_dir: Path,
    proposal: PUpdateProposal,
    candidate: CandidatePBundle,
    stable_probes: tuple[P10LearningProbe, ...],
    target_probes: tuple[P10LearningProbe, ...],
) -> dict[str, object]:
    if not stable_probes or not target_probes:
        raise ValueError(
            "P10_CANDIDATE_REGRESSION_REQUIRES_STABLE_AND_TARGET_PROBES"
        )
    for probe in (*stable_probes, *target_probes):
        failures = probe.validate()
        if failures:
            raise ValueError(";".join(failures))
    authority = HDSPUpdateAuthority()
    decision = authority.decide(
        proposal,
        status="PROBE",
        reason_codes=(
            "candidate-isolated-from-active-manifest",
            "same-condition-stable-and-target-regression",
        ),
        candidate_bundle=candidate,
    )

    def run_set(
        regression_probes: tuple[P10LearningProbe, ...],
        lifecycle: str,
    ) -> list[dict[str, object]]:
        return [
            _execute_regression_run(
                environments_dir=environments_dir,
                probe_index=index,
                probe=probe,
                instruction_lifecycle=lifecycle,
                authority=authority if lifecycle == "candidate" else None,
                decision=decision if lifecycle == "candidate" else None,
                candidate=candidate if lifecycle == "candidate" else None,
            )
            for index, probe in enumerate(regression_probes)
        ]

    stable_active = run_set(stable_probes, "active")
    stable_candidate_first = run_set(stable_probes, "candidate")
    stable_candidate_second = run_set(stable_probes, "candidate")
    target_active = run_set(target_probes, "active")
    target_candidate_first = run_set(target_probes, "candidate")
    target_candidate_second = run_set(target_probes, "candidate")

    stable_non_regression = all(
        _required_int(
            candidate_run["completed_levels"],
            "candidate completed levels",
        )
        >= _required_int(
            active_run["completed_levels"],
            "active completed levels",
        )
        and _required_int(candidate_run["error_count"], "candidate errors")
        == 0
        and not bool(candidate_run["max_action_exhausted"])
        and (
            not bool(active_run["all_complete"])
            or bool(candidate_run["all_complete"])
        )
        for active_run, candidate_run in zip(
            stable_active,
            stable_candidate_first,
            strict=True,
        )
    )
    reproducible = (
        stable_candidate_first == stable_candidate_second
        and target_candidate_first == target_candidate_second
    )
    baseline_target_value = float(
        sum(
            _required_int(run["completed_levels"], "target active levels")
            for run in target_active
        )
    )
    candidate_target_value = float(
        sum(
            _required_int(
                run["completed_levels"],
                "target candidate levels",
            )
            for run in target_candidate_first
        )
    )
    stable_active_value = sum(
        _required_int(run["completed_levels"], "stable active levels")
        for run in stable_active
    )
    stable_candidate_value = sum(
        _required_int(run["completed_levels"], "stable candidate levels")
        for run in stable_candidate_first
    )
    core: dict[str, object] = {
        "schema_version": "arc3-p10-candidate-runtime-regression-v1",
        "operation_mode": "offline",
        "probe_decision": _decision_mapping(decision),
        "probe_decision_digest": decision.digest,
        "stable_active": stable_active,
        "stable_candidate_first": stable_candidate_first,
        "stable_candidate_second": stable_candidate_second,
        "target_active": target_active,
        "target_candidate_first": target_candidate_first,
        "target_candidate_second": target_candidate_second,
        "baseline_target_value": baseline_target_value,
        "candidate_target_value": candidate_target_value,
        "target_improved": (
            candidate_target_value > baseline_target_value
        ),
        "stable_active_value": stable_active_value,
        "stable_candidate_value": stable_candidate_value,
        "stable_non_regression": stable_non_regression,
        "reproducible": reproducible,
    }
    return {
        **core,
        "content_digest": "p10-candidate-runtime-regression:"
        + digest_object(core),
    }


def execute_p10_p_update_workflow(
    *,
    environments_dir: Path,
    probes: tuple[P10LearningProbe, ...],
    bundle_dir: Path,
    evidence_dir: Path,
    prior_memory_paths: tuple[Path, ...] = (),
    stable_regression_probes: tuple[P10LearningProbe, ...] = (),
    target_regression_probes: tuple[P10LearningProbe, ...] = (),
) -> dict[str, object]:
    """Close M -> train -> HDS compile -> isolated candidate, but not promote."""

    merged_memory, probe_summaries = collect_p10_learning_memory(
        environments_dir=environments_dir,
        probes=probes,
    )
    prior_memories = tuple(
        p_b_learning_memory_from_mapping(_json(path))
        for path in prior_memory_paths
    )
    if prior_memories:
        merged_memory = merge_p_b_learning_memory_snapshots(
            (merged_memory, *prior_memories)
        )
    proposal = _proposal(bundle_dir)
    evidence_set = _evidence_set(proposal, merged_memory)
    evidence_failures = evidence_set.validate()
    if evidence_failures:
        raise ValueError(";".join(evidence_failures))
    dataset = build_p_b_learning_dataset(merged_memory, evidence_set)
    learning_result = train_p_b_from_memory(
        load_p10_parametric_instruction_body(),
        dataset,
    )
    first_authority, first_decision, first_directive = (
        _compile_authorization(proposal, evidence_set)
    )
    manifest = compile_p10_instruction_bodies(
        base_bundle_dir=bundle_dir,
        output_dir=bundle_dir,
        compile_directive=first_directive,
        compile_decision=first_decision,
        hds_authority=first_authority,
        learning_result=learning_result,
    )
    with tempfile.TemporaryDirectory() as temporary:
        rebuild_dir = Path(temporary)
        second_authority, second_decision, second_directive = (
            _compile_authorization(proposal, evidence_set)
        )
        rebuilt = compile_p10_instruction_bodies(
            base_bundle_dir=bundle_dir,
            output_dir=rebuild_dir,
            compile_directive=second_directive,
            compile_decision=second_decision,
            hds_authority=second_authority,
            learning_result=learning_result,
        )
        if rebuilt != manifest:
            raise RuntimeError("P10_CANDIDATE_MANIFEST_REBUILD_MISMATCH")
        file_hashes: dict[str, str] = {}
        for filename in _candidate_files(manifest):
            committed_path = bundle_dir / filename
            rebuilt_path = rebuild_dir / filename
            if committed_path.read_bytes() != rebuilt_path.read_bytes():
                raise RuntimeError(
                    f"P10_CANDIDATE_BYTE_REBUILD_MISMATCH:{filename}"
                )
            file_hashes[filename] = _file_digest(committed_path)
    rebuild_digest = digest_object(file_hashes)
    same_input_c_probe = _same_input_c_probe(bundle_dir, manifest)
    descriptors = _candidate_descriptors(
        bundle_dir=bundle_dir,
        manifest=manifest,
        proposal=proposal,
        learning_result=learning_result,
        rebuild_digest=rebuild_digest,
        same_input_c_probe=same_input_c_probe,
    )
    p_b_descriptor = next(
        item for item in descriptors if item.target_component == "P-B"
    )
    p_b_regression = PRegressionReport(
        report_id="regression:p10-p-b-learning-probe",
        candidate_bundle_digest=p_b_descriptor.digest,
        baseline_bundle_digest=p_b_descriptor.source_body_digest,
        target_metric="negative-log-loss-improvement",
        baseline_target_value=-learning_result.source_train_loss,
        candidate_target_value=-learning_result.candidate_train_loss,
        stable_regression_delta=0.0,
        holdout_delta=max(
            0.0,
            learning_result.source_holdout_loss
            - learning_result.candidate_holdout_loss,
        ),
        forgetting_measure=0.0,
        maximum_forgetting=0.0,
        schema_digest_provenance_pass=True,
        identity_free_pass=True,
        deterministic_rebuild_pass=True,
        target_improved=learning_result.target_improved,
        stable_non_regression=False,
        holdout_non_degradation=(
            learning_result.holdout_non_degradation
        ),
        catastrophic_forgetting_within_bound=True,
        hds_boundary_pass=True,
        reproducible_pass=True,
        rollback_pass=True,
        evidence_refs=(
            dataset.digest,
            learning_result.digest,
            rebuild_digest,
        ),
    )
    regression_failures = p_b_regression.validate()
    if regression_failures:
        raise ValueError(";".join(regression_failures))
    candidate_runtime_regression: dict[str, object] | None = None
    hybrid_regression: PRegressionReport | None = None
    decision_candidate = p_b_descriptor
    if stable_regression_probes or target_regression_probes:
        hybrid_descriptor = next(
            item
            for item in descriptors
            if item.target_component == "hybrid-P-B"
        )
        candidate_runtime_regression = _candidate_runtime_regression(
            environments_dir=environments_dir,
            proposal=proposal,
            candidate=hybrid_descriptor,
            stable_probes=stable_regression_probes,
            target_probes=target_regression_probes,
        )
        stable_active_value = _required_float(
            candidate_runtime_regression["stable_active_value"],
            "stable active value",
        )
        stable_candidate_value = _required_float(
            candidate_runtime_regression["stable_candidate_value"],
            "stable candidate value",
        )
        hybrid_regression = PRegressionReport(
            report_id="regression:p10-hybrid-runtime-candidate",
            candidate_bundle_digest=hybrid_descriptor.digest,
            baseline_bundle_digest=hybrid_descriptor.source_body_digest,
            target_metric="completed-level-count",
            baseline_target_value=_required_float(
                candidate_runtime_regression["baseline_target_value"],
                "baseline target value",
            ),
            candidate_target_value=_required_float(
                candidate_runtime_regression["candidate_target_value"],
                "candidate target value",
            ),
            stable_regression_delta=(
                stable_candidate_value - stable_active_value
            ),
            holdout_delta=max(
                0.0,
                learning_result.source_holdout_loss
                - learning_result.candidate_holdout_loss,
            ),
            forgetting_measure=max(
                0.0,
                stable_active_value - stable_candidate_value,
            ),
            maximum_forgetting=0.0,
            schema_digest_provenance_pass=True,
            identity_free_pass=True,
            deterministic_rebuild_pass=True,
            target_improved=bool(
                candidate_runtime_regression["target_improved"]
            ),
            stable_non_regression=bool(
                candidate_runtime_regression["stable_non_regression"]
            ),
            holdout_non_degradation=(
                learning_result.holdout_non_degradation
            ),
            catastrophic_forgetting_within_bound=(
                stable_candidate_value >= stable_active_value
            ),
            hds_boundary_pass=True,
            reproducible_pass=bool(
                candidate_runtime_regression["reproducible"]
            ),
            rollback_pass=(
                active_p10_manifest_digest(bundle_dir)
                == proposal.source_p_digest
            ),
            evidence_refs=(
                dataset.digest,
                learning_result.digest,
                rebuild_digest,
                str(candidate_runtime_regression["content_digest"]),
            ),
        )
        hybrid_failures = hybrid_regression.validate()
        if hybrid_failures:
            raise ValueError(";".join(hybrid_failures))
        decision_candidate = hybrid_descriptor
    decision_regression = hybrid_regression or p_b_regression
    hold_authority = HDSPUpdateAuthority()
    hold_decision = hold_authority.decide(
        proposal,
        status="HOLD",
        reason_codes=(
            (
                "candidate-runtime-regression-complete"
                if hybrid_regression is not None
                else "P-B-model-target-and-holdout-gates-pass"
            ),
            "active-P-promotion-not-executed-by-this-command",
        ),
        candidate_bundle=decision_candidate,
        regression_report=decision_regression,
    )
    memory_mapping = p_b_learning_memory_evidence_mapping(merged_memory)
    dataset_mapping = _dataset_mapping(dataset)
    learning_mapping = {
        "schema_version": "arc3-p-b-learning-result-evidence-v1",
        "runtime_identity_free": True,
        **dataclasses.asdict(learning_result),
        "learning_result_digest": learning_result.digest,
    }
    trace_core: dict[str, object] = {
        "schema_version": P10_P_UPDATE_WORKFLOW_SCHEMA_VERSION,
        "operation_mode": "offline",
        "active_manifest_digest": proposal.source_p_digest,
        "proposal": dataclasses.asdict(proposal),
        "proposal_digest": proposal.digest,
        "evidence_set": dataclasses.asdict(evidence_set),
        "evidence_set_digest": evidence_set.digest,
        "probe_summaries": list(probe_summaries),
        "prior_memory_evidence": [
            {
                "filename": path.name,
                "sha256": _file_digest(path),
                "memory_snapshot_digest": memory.digest,
            }
            for path, memory in zip(
                prior_memory_paths,
                prior_memories,
                strict=True,
            )
        ],
        "memory_snapshot_digest": merged_memory.digest,
        "dataset_digest": dataset.digest,
        "learning_result_digest": learning_result.digest,
        "compile_decision_digest": first_decision.digest,
        "compile_directive_digest": first_directive.digest,
        "candidate_manifest_digest": digest_object(manifest),
        "candidate_descriptors": [
            dataclasses.asdict(item) for item in descriptors
        ],
        "deterministic_rebuild_digest": rebuild_digest,
        "same_input_c_probe": same_input_c_probe,
        "p_b_regression_report": dataclasses.asdict(p_b_regression),
        "p_b_regression_report_digest": p_b_regression.digest,
        "candidate_runtime_regression": candidate_runtime_regression,
        "hybrid_regression_report": (
            dataclasses.asdict(hybrid_regression)
            if hybrid_regression is not None
            else None
        ),
        "hybrid_regression_report_digest": (
            hybrid_regression.digest
            if hybrid_regression is not None
            else None
        ),
        "promotion_failures": list(
            decision_regression.promotion_failures
        ),
        "hds_decision": _decision_mapping(hold_decision),
        "hds_decision_digest": hold_decision.digest,
        "active_changed": False,
        "candidate_lifecycle": "HOLD",
    }
    trace = {
        **trace_core,
        "content_digest": "p10-p-update-workflow:" + digest_object(trace_core),
    }
    _write_json(
        evidence_dir / "p_b_learning_memory_v1.json",
        memory_mapping,
    )
    _write_json(
        evidence_dir / "p_b_learning_dataset_v1.json",
        dataset_mapping,
    )
    _write_json(
        evidence_dir / "p_b_learning_result_v1.json",
        learning_mapping,
    )
    _write_json(
        evidence_dir / "p10_candidate_compile_trace_v1.json",
        trace,
    )
    return trace


def _parse_probe(value: str) -> P10LearningProbe:
    selector, separator, raw_budget = value.rpartition(":")
    if not separator:
        raise argparse.ArgumentTypeError(
            "probe must be ENVIRONMENT_SELECTOR:MAX_ACTIONS"
        )
    try:
        budget = int(raw_budget)
    except ValueError as error:
        raise argparse.ArgumentTypeError("probe action budget invalid") from error
    return P10LearningProbe(selector, budget)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Collect HDS-authorized OFFLINE M evidence and compile an isolated "
            "P10 candidate. This command never promotes active P."
        )
    )
    parser.add_argument(
        "--environments-dir",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--probe",
        action="append",
        type=_parse_probe,
        required=True,
    )
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument(
        "--prior-memory",
        action="append",
        type=Path,
        default=[],
    )
    parser.add_argument(
        "--stable-regression",
        action="append",
        type=_parse_probe,
        default=[],
    )
    parser.add_argument(
        "--target-regression",
        action="append",
        type=_parse_probe,
        default=[],
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    trace = execute_p10_p_update_workflow(
        environments_dir=args.environments_dir,
        probes=tuple(args.probe),
        bundle_dir=args.bundle_dir,
        evidence_dir=args.evidence_dir,
        prior_memory_paths=tuple(args.prior_memory),
        stable_regression_probes=tuple(args.stable_regression),
        target_regression_probes=tuple(args.target_regression),
    )
    print(json.dumps(trace, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "P10_P_UPDATE_WORKFLOW_SCHEMA_VERSION",
    "P10LearningProbe",
    "collect_p10_learning_memory",
    "execute_p10_p_update_workflow",
    "main",
]
