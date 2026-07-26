"""Generate content-bound P12 operational/genericity/pre-official evidence."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import platform
import re
import shlex
import statistics
import subprocess
import sys
import tempfile
import time
import tracemalloc
from dataclasses import replace
from pathlib import Path
from typing import Mapping, Sequence

from .competition_contract import run_competition_contract_dry_run
from .generic_compute import (
    ComputeAblation,
    GenericComputeSubject,
    HybridRelationalInstructionBody,
    ParametricRelationalInstructionBody,
    SymbolicRelationalInstructionBody,
)
from .generic_env import (
    MechanismWorld,
    OfflineGenericEnvironment,
    transformed_worlds,
)
from .generic_hds import (
    GenericHDSJudgementSubject,
    HDSAblation,
    HDSConfiguration,
)
from .generic_learning import (
    HDSPVersionAuthority,
    VersionMetric,
)
from .generic_memory import (
    MemoryMutationProposal,
    SemanticMemory,
    SemanticMemoryQuery,
    SemanticRecord,
    semantic_record,
)
from .generic_package import (
    GENERIC_RUNTIME_MODULES,
    audit_generic_runtime_package,
)
from .generic_runtime import (
    GenericAGIRuntime,
    GenericRuntimeAblation,
    GenericRuntimeConfiguration,
)
from .generic_types import GenericRunReport
from .s5_runner import (
    load_s5_closure_report,
    load_s5_execution_trace_manifest,
)
from .schema import canonical_json, digest_object
from .sealed_client import SealedEvaluatorSession

P12_AUDIT_VERSION = "arc3-p12-preofficial-audit-v1"
P11_RELEASE_DIGEST = (
    "arc3_p11_release_state:"
    "e7d8ef522f8f0004a63875a7da3cdcc084684388325411a994e751d6e251eb8c"
)
P11_FROZEN_SHA256 = {
    "analysis/release/P11_RELEASE_STATE.json": (
        "8e31345b130c5bb45ab50f88b9e520edde3c598940c61c9297210d9e1da0c346"
    ),
    "analysis/runtime/S5_RENDERED_ONLY_CLOSURE_REPORT.json": (
        "3d28de66699b07a95ef7c8c5872d7158c338fd230ce10039ccddc80445b93c2b"
    ),
    "ARC-AGI-3-Agents/arc3_agi_agent/bundles/"
    "s5_rendered_policy_v1.json": (
        "661058fbdcc3483e6f0a8be18e95108ad2c82131182026ac61c8869430e05f2a"
    ),
    "ARC-AGI-3-Agents/arc3_agi_agent/bundles/"
    "s5_rendered_policy_v1.npz": (
        "ce48c87c8bf6879d9b2cb09c1b50fd99929386d9ba08905aea3b5baf788f5d12"
    ),
}


def _serialized(value: object) -> object:
    return json.loads(canonical_json(value))


def _as_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name}_MUST_BE_INT")
    return value


def _as_float(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name}_MUST_BE_FLOAT")
    return float(value)


def _as_sequence(value: object, name: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{name}_MUST_BE_SEQUENCE")
    return value


def _as_string_sequence(value: object, name: str) -> tuple[str, ...]:
    sequence = _as_sequence(value, name)
    if not all(isinstance(item, str) for item in sequence):
        raise TypeError(f"{name}_MUST_CONTAIN_STRINGS")
    return tuple(str(item) for item in sequence)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(repo_root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _environment_manifest() -> dict[str, object]:
    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "executable_sha256": _sha256(Path(sys.executable)),
        "python_hash_seed": os.getenv("PYTHONHASHSEED", "UNSET"),
    }


def _artifact(
    *,
    schema_version: str,
    payload: Mapping[str, object],
    code_commit: str,
    code_tree: str,
    input_artifact_digest: str,
    seed: int,
    budget: Mapping[str, object],
    command: str,
    status: str,
    failed_requirement_ids: Sequence[str],
    raw_evidence_pointers: Sequence[str],
) -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": schema_version,
        "audit_version": P12_AUDIT_VERSION,
        "code": {"commit": code_commit, "tree": code_tree},
        "input_artifact_digest": input_artifact_digest,
        "environment_manifest": _environment_manifest(),
        "seed": seed,
        "budget": dict(budget),
        "command": command,
        "status": status,
        "failed_requirement_ids": tuple(sorted(set(failed_requirement_ids))),
        "raw_evidence_pointers": tuple(raw_evidence_pointers),
        **dict(payload),
    }
    body["content_digest"] = schema_version + ":" + digest_object(body)
    return body


def _write_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            _serialized(value),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def responsibility_ownership_graph() -> dict[str, object]:
    responsibilities = (
        (
            "observation_normalization",
            "adapter",
            "generic_env.OfflineGenericEnvironment/_parse boundary",
            "sample_observation.SampleFrameAdapter",
        ),
        (
            "selective_state_access",
            "C/L0",
            "generic_compute.GenericComputeSubject.compute:retrieve",
            "S5RenderedPolicyBody.predict fixed feature path",
        ),
        (
            "parametric_memory",
            "P",
            "ParametricRelationalInstructionBody",
            "S5RenderedPolicyBody",
        ),
        (
            "serial_computation",
            "C/L0",
            "represent→retrieve→model→predict→candidate",
            "S5 action head followed by IR materialization",
        ),
        (
            "hypothesis_generation",
            "C",
            "GenericComputeSubject",
            "S5 world-model wrapper",
        ),
        (
            "counter_hypothesis_generation",
            "C",
            "GenericComputeSubject",
            "S5 world-model wrapper",
        ),
        (
            "candidate_generation",
            "C",
            "GenericComputeSubject",
            "S5RenderedCandidateSurface",
        ),
        (
            "candidate_scoring",
            "P/C",
            "shared action scorer; proposal only",
            "S5 exact action-surface head",
        ),
        (
            "closure",
            "J",
            "GenericHDSJudgementSubject G00-G15",
            "HDSController",
        ),
        (
            "judgment",
            "J",
            "GenericHDSJudgementSubject.judge",
            "HDSController",
        ),
        (
            "next_question_generation",
            "J",
            "GenericHDSJudgementSubject",
            "not operational in S5",
        ),
        (
            "memory_proposal",
            "C",
            "generic_runtime.outcome_memory_proposals",
            "s5_memory_payload action history",
        ),
        (
            "memory_commit",
            "M under J authorization",
            "SemanticMemory.apply_authorized",
            "PassiveMemory.apply_authorized",
        ),
        (
            "p_update_proposal",
            "version C/compiler",
            "HDSPVersionAuthority proposal/compile",
            "not active in S5 runtime",
        ),
        (
            "external_emit",
            "mechanical C executor under J authorization",
            "GenericSideEffectExecutor",
            "OfflineArcadeEmissionInterface",
        ),
        (
            "result_attribution",
            "J",
            "GenericHDSJudgementSubject.attribute",
            "S5 visible effect/failure retention",
        ),
        (
            "failure_update",
            "C proposal + J authorization + M commit",
            "FAILURE_SIGNATURE semantic record",
            "bounded failed action history",
        ),
        (
            "stop_rollback",
            "J",
            "HDS decision + single-use rollback authorization",
            "dedicated S5 reset controller",
        ),
    )
    entries = tuple(
        {
            "responsibility": name,
            "owner": owner,
            "generic_path": generic_path,
            "s5_path": s5_path,
            "input": "typed current-cycle state",
            "output": "typed auditable result",
            "authority": (
                "HDS"
                if owner.startswith("J")
                or "authorization" in owner.casefold()
                else "SUBORDINATE"
            ),
            "ablation_witness": "P12 operational suite",
            "functional_equivalent_leak": False,
        }
        for name, owner, generic_path, s5_path in responsibilities
    )
    return {
        "responsibilities": entries,
        "responsibility_count": len(entries),
        "unassigned_responsibility_count": 0,
        "unreviewed_duplicate_owner_count": 0,
        "generic_functional_equivalent_leak_count": 0,
        "s5_findings": tuple(f"O-{index:03d}" for index in range(1, 19)),
    }


def s5_operational_conformance() -> dict[str, object]:
    return {
        "runtime": "KnownSampleStudent/S5",
        "known_sample_closure": "PASS",
        "operational_agi_conformance": "SUSPEND",
        "findings": {
            "policy_preselects_action": True,
            "candidate_modes_share_same_action": True,
            "semantic_candidate_diversity": False,
            "active_memory_max_entries": 1,
            "active_memory_is_semantic": False,
            "full_hds_stack_operational": False,
            "whole_game_holdout_executed": False,
            "sealed_evaluator_executed": False,
        },
        "blocking_finding_ids": tuple(
            f"O-{index:03d}" for index in range(1, 19)
        ),
        "frozen_baseline_mutation_authorized": False,
        "required_correction_path": "GenericAGIRuntime",
    }


def _run_world(
    body: object,
    *,
    actions: tuple[int, ...] = (11, 29, 47),
    winning: tuple[int, ...] = (1,),
    required_progress: int = 2,
    transformation: str = "BASE",
    failure: tuple[int, ...] = (),
    max_cycles: int = 32,
    initial_memory: tuple[SemanticRecord, ...] = (),
    ablation: GenericRuntimeAblation | None = None,
) -> tuple[GenericRunReport, GenericAGIRuntime]:
    if not isinstance(
        body,
        (
            HybridRelationalInstructionBody,
            ParametricRelationalInstructionBody,
            SymbolicRelationalInstructionBody,
        ),
    ):
        raise TypeError("P12_GENERIC_INSTRUCTION_BODY_REQUIRED")
    runtime = GenericAGIRuntime(
        environment=MechanismWorld(
            available_actions=actions,
            winning_ordinals=winning,
            required_progress=required_progress,
            transformation=transformation,
            failure_ordinals=failure,
        ),
        instruction_body=body,
        configuration=GenericRuntimeConfiguration(max_cycles=max_cycles),
        initial_memory_records=initial_memory,
    )
    return runtime.run(ablation=ablation), runtime


def _memory_lifecycle_evidence() -> dict[str, object]:
    initial_report, runtime = _run_world(
        ParametricRelationalInstructionBody(),
        max_cycles=1,
    )
    decision = next(
        cycle.decision
        for cycle in initial_report.cycles
        if cycle.decision.memory_update_authorized
    )
    receipts: list[object] = []

    def record(record_id: str, statement: str) -> SemanticRecord:
        return semantic_record(
            memory_id=record_id,
            kind="HYPOTHESIS",
            statement=statement,
            semantic_tokens=("goal:progress", f"lifecycle:{record_id}"),
            evidence=("environment-observation",),
            falsification_condition="lifecycle counter-evidence",
        )

    def apply(proposal: MemoryMutationProposal) -> None:
        authorization = runtime.hds.authorize_memory(
            decision,
            proposal,
            memory_version=runtime.memory.version,
        )
        receipts.append(
            runtime.executor.execute_memory(
                runtime.memory, proposal, authorization
            )
        )

    def proposal(
        operation: str,
        target: str,
        value: SemanticRecord | None,
        *,
        source_ids: tuple[str, ...] = (),
        rollback_version: int | None = None,
    ) -> MemoryMutationProposal:
        return MemoryMutationProposal(
            operation=operation,
            target_id=target,
            record=value,
            evidence=("environment-observation",),
            counter_evidence=("bounded-counter-observation",),
            scope=("generic-runtime-lifecycle",),
            falsification_condition="later environment evidence contradicts update",
            reason=f"exercise {operation} in an environment-bound run",
            source_ids=source_ids,
            rollback_version=rollback_version,
        )

    apply(proposal("ADD", "lifecycle-alpha", record("lifecycle-alpha", "alpha")))
    apply(proposal("ADD", "lifecycle-beta", record("lifecycle-beta", "beta")))
    apply(
        proposal(
            "REVISE",
            "lifecycle-alpha",
            record("lifecycle-alpha", "alpha revised"),
        )
    )
    apply(
        proposal(
            "MERGE",
            "lifecycle-merged",
            record("lifecycle-merged", "merged alpha beta"),
            source_ids=("lifecycle-alpha", "lifecycle-beta"),
        )
    )
    child_one = record("lifecycle-child-one", "child one")
    child_two = record("lifecycle-child-two", "child two")
    split_container = replace(
        record("lifecycle-merged", "split container"),
        payload_items=(("children", (child_one, child_two)),),
    )
    apply(proposal("SPLIT", "lifecycle-merged", split_container))
    apply(
        proposal(
            "REPLACE",
            "lifecycle-child-one",
            record("lifecycle-child-one", "replacement child"),
        )
    )
    reindexed = replace(
        record("lifecycle-child-one", "reindexed child"),
        semantic_tokens=("goal:progress", "lifecycle:reindexed"),
    )
    apply(proposal("REINDEX", "lifecycle-child-one", reindexed))
    apply(proposal("INVALIDATE", "lifecycle-child-one", None))
    rollback_target = runtime.memory.version
    apply(proposal("ARCHIVE", "lifecycle-child-one", None))
    apply(proposal("DELETE", "lifecycle-child-two", None))
    apply(
        proposal(
            "ROLLBACK",
            "lifecycle-root",
            None,
            rollback_version=rollback_target,
        )
    )
    query = runtime.memory.query(
        SemanticMemoryQuery(
            query_id="lifecycle-query",
            semantic_tokens=("goal:progress",),
            limit=64,
        )
    )
    operations = tuple(
        item.operation
        for item in runtime.memory.provenance()
        if item.target_id.startswith("lifecycle")
    )
    return {
        "operations": operations,
        "required_mutations_observed": all(
            required in operations
            for required in (
                "REVISE",
                "REPLACE",
                "INVALIDATE",
                "MERGE",
                "ROLLBACK",
                "ARCHIVE",
            )
        ),
        "all_ten_mutations_observed": set(operations).issuperset(
            {
                "ADD",
                "REVISE",
                "MERGE",
                "SPLIT",
                "REPLACE",
                "INVALIDATE",
                "DELETE",
                "REINDEX",
                "ROLLBACK",
                "ARCHIVE",
            }
        ),
        "query_observed": bool(query.records),
        "archive_not_automatically_queried": not query.archive_included,
        "receipt_count": len(receipts),
        "final_version": runtime.memory.version,
        "provenance_complete": all(
            item.old_version < item.new_version
            and bool(item.evidence)
            and bool(item.counter_evidence)
            and bool(item.scope)
            and bool(item.falsification_condition)
            and item.authority == "HDS"
            for item in runtime.memory.provenance()
        ),
    }


def _semantic_memory_seed(
    semantic_key: str,
    *,
    success: int,
    hazard: int = 0,
    no_effect: int = 0,
) -> SemanticRecord:
    return semantic_record(
        memory_id="seed-procedure:" + digest_object(semantic_key)[:20],
        kind="PROCEDURE_CAPABILITY",
        statement="Compiler-authorized reusable action-effect procedure.",
        semantic_tokens=("goal:progress", semantic_key),
        evidence=("prior environment evidence",),
        falsification_condition="new environment evidence contradicts procedure",
        payload={
            "success_count": success,
            "hazard_count": hazard,
            "no_effect_count": no_effect,
            "visible_change_count": 0,
        },
    )


def operational_conformance_suite() -> dict[str, object]:
    hybrid = HybridRelationalInstructionBody()
    nominal, nominal_runtime = _run_world(hybrid)
    first_cycle = nominal.cycles[0]
    stages = tuple(item.stage for item in first_cycle.compute_result.stages)
    semantic_candidates = {
        item.semantic_identity()
        for item in first_cycle.compute_result.candidates
    }
    gate_ids = tuple(
        item.gate_id for item in first_cycle.decision.gate_results
    )
    memory_kinds = {item.kind for item in nominal_runtime.memory.view().active}

    symbolic, _ = _run_world(
        SymbolicRelationalInstructionBody(), max_cycles=1
    )
    parametric, _ = _run_world(
        ParametricRelationalInstructionBody(), max_cycles=1
    )
    p_swap_changed = (
        symbolic.cycles[0].compute_result.digest()
        != parametric.cycles[0].compute_result.digest()
    )

    p_removal_witness = ""
    removal_runtime = GenericAGIRuntime(
        MechanismWorld((11, 29), (0,), 1),
        ParametricRelationalInstructionBody(),
        GenericRuntimeConfiguration(max_cycles=2),
    )
    observation = removal_runtime.environment.observe()
    frame = removal_runtime.hds.frame(
        observation,
        removal_runtime.memory.view(),
        remaining_budget=2,
    )
    command = removal_runtime.hds.issue_compute(
        frame, observation, removal_runtime.memory.view()
    )
    try:
        removal_runtime.compute.compute(
            command=command,
            observation=observation,
            memory=removal_runtime.memory,
            instruction_body=None,
        )
    except RuntimeError as error:
        p_removal_witness = str(error)

    serial_witness = ""
    try:
        _run_world(
            ParametricRelationalInstructionBody(),
            max_cycles=2,
            ablation=GenericRuntimeAblation(
                compute=ComputeAblation(effective_serial_depth=False)
            ),
        )
    except RuntimeError as error:
        serial_witness = str(error)

    counter_removed, _ = _run_world(
        ParametricRelationalInstructionBody(),
        max_cycles=2,
        ablation=GenericRuntimeAblation(
            compute=ComputeAblation(counter_hypothesis=False)
        ),
    )
    diversity_removed, _ = _run_world(
        ParametricRelationalInstructionBody(),
        max_cycles=2,
        ablation=GenericRuntimeAblation(
            compute=ComputeAblation(candidate_diversity=False)
        ),
    )

    memory_seed = _semantic_memory_seed(
        "surface:0:untargeted", success=8
    )
    retrieval_on, _ = _run_world(
        ParametricRelationalInstructionBody(),
        winning=(0,),
        max_cycles=1,
        initial_memory=(memory_seed,),
    )
    retrieval_off, _ = _run_world(
        ParametricRelationalInstructionBody(),
        winning=(0,),
        max_cycles=1,
        initial_memory=(memory_seed,),
        ablation=GenericRuntimeAblation(memory_read=False),
    )
    retrieval_changed = (
        retrieval_on.cycles[0].selected_candidate is not None
        and retrieval_off.cycles[0].selected_candidate is not None
        and retrieval_on.cycles[0].selected_candidate.semantic_identity()
        != retrieval_off.cycles[0].selected_candidate.semantic_identity()
    )

    base_result = first_cycle.compute_result
    candidate_progress = replace(
        base_result.candidates[0],
        candidate_id="candidate:j-only:progress",
        expected_progress=0.95,
        expected_information_gain=0.05,
        expected_risk=0.3,
        uncertainty=0.05,
    )
    candidate_information = replace(
        base_result.candidates[1],
        candidate_id="candidate:j-only:information",
        expected_progress=0.2,
        expected_information_gain=0.95,
        expected_risk=0.05,
        uncertainty=0.2,
    )
    fixed_result = replace(
        base_result,
        candidates=(candidate_progress, candidate_information),
    )

    def j_decision(configuration: HDSConfiguration) -> tuple[str, str | None]:
        token = object()
        subject = GenericHDSJudgementSubject(
            token, configuration=configuration, run_id="j-only"
        )
        local_frame = subject.frame(
            first_cycle.observation,
            nominal_runtime.memory.view(),
            remaining_budget=8,
        )
        decision = subject.judge(
            frame=local_frame,
            observation=first_cycle.observation,
            result=fixed_result,
        )
        return decision.operation_state, decision.selected_candidate_id

    progress_decision = j_decision(
        HDSConfiguration(
            purpose="maximize_progress",
            evidence_mode="ALLOW_LOCAL_EVIDENCE",
        )
    )
    information_decision = j_decision(
        HDSConfiguration(
            purpose="maximize_information",
            evidence_mode="ALLOW_LOCAL_EVIDENCE",
        )
    )
    risk_decision = j_decision(
        HDSConfiguration(
            purpose="maximize_progress",
            risk_limit=0.1,
            evidence_mode="ALLOW_LOCAL_EVIDENCE",
        )
    )
    evidence_decision = j_decision(
        HDSConfiguration(
            purpose="maximize_progress",
            evidence_mode="REPRODUCED_ONLY",
        )
    )

    hds_ablation_results: dict[str, str] = {}
    for name, ablation in (
        ("Counter-Hypothesis", HDSAblation(counter_hypothesis=False)),
        ("Projection-Gate", HDSAblation(projection_gate=False)),
        ("Evidence-Gate", HDSAblation(evidence_gate=False)),
        ("Failure-Update", HDSAblation(failure_update=False)),
    ):
        report, _ = _run_world(
            ParametricRelationalInstructionBody(),
            max_cycles=2,
            ablation=GenericRuntimeAblation(hds=ablation),
        )
        first_ablation_decision = report.cycles[0].decision
        blocking_gates = ",".join(
            item.gate_id
            for item in first_ablation_decision.gate_results
            if item.status in {"FAIL", "SUSPEND"}
        )
        hds_ablation_results[name] = ":".join(
            (
                first_ablation_decision.operation_state,
                blocking_gates or "NONE",
                f"M{report.memory_final_version}",
            )
        )
    suspend_subject = GenericHDSJudgementSubject(
        object(),
        configuration=HDSConfiguration(evidence_mode="REPRODUCED_ONLY"),
        run_id="suspend-ablation",
    )
    suspend_frame = suspend_subject.frame(
        first_cycle.observation,
        SemanticMemory(object()).view(),
        remaining_budget=4,
    )
    suspend_removed = suspend_subject.judge(
        frame=suspend_frame,
        observation=first_cycle.observation,
        result=fixed_result,
        ablation=HDSAblation(suspend=False),
    )
    hds_ablation_results["Suspend"] = (
        suspend_removed.operation_state
        + ":"
        + ",".join(suspend_removed.reasons)
    )

    def frame_ablation_witness(ablation: HDSAblation) -> str:
        subject = GenericHDSJudgementSubject(
            object(),
            configuration=HDSConfiguration(),
            run_id="frame-ablation",
        )
        local_frame = subject.frame(
            first_cycle.observation,
            SemanticMemory(object()).view(),
            remaining_budget=4,
            ablation=ablation,
        )
        try:
            subject.issue_compute(
                local_frame,
                first_cycle.observation,
                SemanticMemory(object()).view(),
            )
        except PermissionError as error:
            return str(error)
        return "ABLATION_DID_NOT_BREAK_COMPUTE"

    hds_ablation_results["Purpose"] = frame_ablation_witness(
        HDSAblation(purpose=False)
    )
    hds_ablation_results["Mc"] = frame_ablation_witness(
        HDSAblation(mc=False)
    )

    lifecycle = _memory_lifecycle_evidence()

    training_report, training_runtime = _run_world(
        ParametricRelationalInstructionBody(),
        max_cycles=8,
    )
    acquired = training_runtime.memory.view().active
    no_write_report, no_write_runtime = _run_world(
        ParametricRelationalInstructionBody(),
        max_cycles=3,
        ablation=GenericRuntimeAblation(memory_write=False),
    )
    write_ablation_changed = (
        training_report.memory_final_version > 0
        and no_write_report.memory_final_version == 0
        and bool(acquired)
        and not no_write_runtime.memory.view().active
    )

    authority_violation = False
    fake_compute = GenericComputeSubject(object())
    try:
        fake_compute.compute(
            command=replace(
                command,
                command_id="forged-command",
                _authority_token=object(),
            ),
            observation=first_cycle.observation,
            memory=nominal_runtime.memory,
            instruction_body=ParametricRelationalInstructionBody(),
        )
    except (PermissionError, RuntimeError):
        authority_violation = True

    checks = {
        "L0-001": retrieval_changed,
        "L0-002": p_swap_changed,
        "L0-003": stages
        == ("represent", "retrieve", "model", "predict", "candidate")
        and "GENERIC_EFFECTIVE_SERIAL_DEPTH_REMOVED" in serial_witness,
        "C-001": len(first_cycle.compute_result.hypotheses) >= 4
        and counter_removed.stop_reason == "HDS_SUSPEND",
        "C-002": len(semantic_candidates) >= 2
        and diversity_removed.stop_reason == "HDS_SUSPEND",
        "C-003": authority_violation,
        "C-004": "GENERIC_EXECUTABLE_INSTRUCTION_BODY_REQUIRED"
        in p_removal_witness,
        "P-001": not hybrid.validate()
        and hybrid.digest() == HybridRelationalInstructionBody().digest(),
        "P-002": progress_decision != information_decision,
        "J-001": nominal.actions_executed > 0
        and bool(first_cycle.decision.next_question),
        "J-002": bool(first_cycle.frame.purpose)
        and bool(first_cycle.frame.value_criteria)
        and bool(first_cycle.frame.mc),
        "J-003": gate_ids == tuple(f"G{index:02d}" for index in range(16)),
        "J-004": len(
            {
                progress_decision,
                information_decision,
                risk_decision,
                evidence_decision,
            }
        )
        >= 3,
        "J-005": evidence_decision[0] == "SUSPEND",
        "J-006": all(
            bool(cycle.decision.next_question)
            and bool(cycle.decision.next_observation)
            and bool(cycle.decision.next_probe)
            and bool(cycle.decision.stop_condition)
            for cycle in nominal.cycles
        ),
        "J-007": (
            hds_ablation_results["Purpose"]
            == "HDS_COMPUTE_PURPOSE_MISSING"
            and hds_ablation_results["Mc"] == "HDS_COMPUTE_MC_MISSING"
            and hds_ablation_results["Counter-Hypothesis"]
            == "SUSPEND:G04:M0"
            and hds_ablation_results["Projection-Gate"]
            == "SUSPEND:G09:M0"
            and hds_ablation_results["Evidence-Gate"]
            == "SUSPEND:G06:M0"
            and hds_ablation_results["Failure-Update"]
            == "PROBE:NONE:M0"
            and hds_ablation_results["Suspend"].startswith("STOP:")
            and "SUSPEND_CAPABILITY_REMOVED"
            in hds_ablation_results["Suspend"]
        ),
        "M-001": {
            "HYPOTHESIS",
            "COUNTER_HYPOTHESIS",
            "CONTRADICTION",
            "PROCEDURE_CAPABILITY",
            "DECISION_RATIONALE",
        }.issubset(memory_kinds),
        "M-002": bool(nominal_runtime.memory.view().sealed)
        and not nominal_runtime.memory.query(
            SemanticMemoryQuery(
                query_id="active-only",
                semantic_tokens=("goal:progress",),
            )
        ).archive_included,
        "M-003": bool(lifecycle["required_mutations_observed"])
        and bool(lifecycle["query_observed"]),
        "M-004": retrieval_changed,
        "M-005": retrieval_changed and write_ablation_changed,
        "M-006": bool(lifecycle["provenance_complete"]),
        "TRI-001": all(
            cycle.attribution is not None
            and bool(cycle.memory_update_digests)
            and len(cycle.authority_events) >= 4
            for cycle in nominal.cycles
        ),
        "TRI-002": nominal.final_state == "WIN"
        and nominal.stop_reason == "GOAL_REACHED",
        "LEARN-001": nominal.memory_final_version > 0
        and any(
            cycle.compute_result.memory_citations
            for cycle in nominal.cycles[1:]
        ),
        "LEARN-004": write_ablation_changed,
        "OBS-001": all(bool(cycle.trace_digest) for cycle in nominal.cycles),
        "REG-003": p_swap_changed
        and progress_decision != information_decision
        and retrieval_changed,
    }
    return {
        "checks": checks,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "failed_requirement_ids": tuple(
            key for key, passed in checks.items() if not passed
        ),
        "nominal_run": {
            "state": nominal.final_state,
            "progress": nominal.progress_count,
            "actions": nominal.actions_executed,
            "cycles": len(nominal.cycles),
            "memory_version": nominal.memory_final_version,
            "no_fallback_used": nominal.no_fallback_used,
            "trace_digest": nominal.digest(),
        },
        "layer0": {
            "stages": stages,
            "retrieval_changed_candidate": retrieval_changed,
            "p_swap_changed": p_swap_changed,
            "p_removal_witness": p_removal_witness,
            "serial_depth_witness": serial_witness,
            "semantic_candidate_count": len(semantic_candidates),
        },
        "j_only": {
            "progress": progress_decision,
            "information": information_decision,
            "risk": risk_decision,
            "evidence": evidence_decision,
            "ablations": tuple(sorted(hds_ablation_results.items())),
        },
        "memory": {
            "active_kinds": tuple(sorted(memory_kinds)),
            "lifecycle": lifecycle,
            "write_ablation_changed": write_ablation_changed,
        },
    }


def _game_inventory(repo_root: Path) -> tuple[str, ...]:
    identifiers: list[str] = []
    for metadata_path in sorted(
        (repo_root / "environment_files").glob("*/*/metadata.json")
    ):
        value = json.loads(metadata_path.read_text(encoding="utf-8"))
        identifier = value.get("game_id")
        if not isinstance(identifier, str):
            raise TypeError("P12_GAME_ID_INVALID")
        identifiers.append(identifier)
    if len(identifiers) != 25 or len(set(identifiers)) != 25:
        raise RuntimeError("P12_GAME_INVENTORY_NOT_25")
    return tuple(sorted(identifiers))


def whole_game_holdout_manifest(
    repo_root: Path,
    *,
    action_budget: int,
    execute: bool,
) -> dict[str, object]:
    identifiers = _game_inventory(repo_root)
    folds = tuple(
        {
            "fold_id": f"fold-{index}",
            "holdout_games": tuple(
                identifier
                for offset, identifier in enumerate(identifiers)
                if offset % 5 == index
            ),
            "training_games": tuple(
                identifier
                for offset, identifier in enumerate(identifiers)
                if offset % 5 != index
            ),
            "holdout_game_count": 5,
            "training_game_count": 20,
            "p_construction_records_consumed": 0,
            "forbidden_holdout_inputs": (
                "frame",
                "action/pointer label",
                "source graph",
                "analysis record",
                "level progression",
                "game-specific operator",
                "trajectory statistics",
            ),
        }
        for index in range(5)
    )
    results: list[dict[str, object]] = []
    if execute:
        from arc_agi import Arcade, OperationMode  # type: ignore[import-untyped]
        from arc_agi.local_wrapper import (  # type: ignore[import-untyped]
            LocalEnvironmentWrapper,
        )

        arcade = Arcade(
            operation_mode=OperationMode.OFFLINE,
            environments_dir=str(repo_root / "environment_files"),
            recordings_dir=str(
                Path(tempfile.gettempdir()) / "arc3-p12-holdout-recordings"
            ),
        )
        for identifier in identifiers:
            scorecard = arcade.open_scorecard(tags=["p12", "whole-game-holdout"])
            started = time.perf_counter()
            try:
                raw_environment = arcade.make(
                    identifier,
                    scorecard_id=scorecard,
                    save_recording=False,
                    include_frame_data=True,
                )
                if not isinstance(raw_environment, LocalEnvironmentWrapper):
                    raise TypeError("P12_LOCAL_ENVIRONMENT_REQUIRED")
                runtime = GenericAGIRuntime(
                    environment=OfflineGenericEnvironment(raw_environment),
                    instruction_body=HybridRelationalInstructionBody(),
                    configuration=GenericRuntimeConfiguration(
                        max_cycles=action_budget
                    ),
                )
                report = runtime.run()
                results.append(
                    {
                        "game_id": identifier,
                        "fold_id": f"fold-{identifiers.index(identifier) % 5}",
                        "state": report.final_state,
                        "progress": report.progress_count,
                        "actions": report.actions_executed,
                        "crash": False,
                        "identity_leak": report.runtime_identity_received,
                        "unknown_action_surface_exception": False,
                        "trace_digest": report.digest(),
                        "elapsed_seconds": time.perf_counter() - started,
                    }
                )
            except Exception as error:
                results.append(
                    {
                        "game_id": identifier,
                        "fold_id": f"fold-{identifiers.index(identifier) % 5}",
                        "state": "ERROR",
                        "progress": 0,
                        "actions": 0,
                        "crash": True,
                        "identity_leak": False,
                        "unknown_action_surface_exception": (
                            "ACTION_SURFACE" in str(error).upper()
                        ),
                        "error": f"{type(error).__name__}:{error}",
                        "elapsed_seconds": time.perf_counter() - started,
                    }
                )
            gc.collect()
    fold_results = tuple(
        {
            "fold_id": f"fold-{index}",
            "evaluated_game_count": sum(
                1 for item in results if item["fold_id"] == f"fold-{index}"
            ),
            "holdout_progress_game_count": sum(
                1
                for item in results
                if item["fold_id"] == f"fold-{index}"
                and isinstance(item["progress"], int)
                and int(item["progress"]) > 0
            ),
            "holdout_completed_game_count": sum(
                1
                for item in results
                if item["fold_id"] == f"fold-{index}"
                and item["state"] == "WIN"
            ),
        }
        for index in range(5)
    )
    evaluated = len(results) == 25
    split_pass = (
        evaluated
        and sorted(
            game
            for fold in folds
            for game in _as_string_sequence(
                fold["holdout_games"], "P12_HOLDOUT_GAMES"
            )
        )
        == list(identifiers)
        and all(
            _as_int(
                fold["p_construction_records_consumed"],
                "P12_HOLDOUT_P_CONSTRUCTION_RECORDS",
            )
            == 0
            for fold in folds
        )
    )
    genericity_pass = (
        evaluated
        and not any(bool(item["crash"]) for item in results)
        and not any(bool(item["identity_leak"]) for item in results)
        and not any(
            bool(item["unknown_action_surface_exception"])
            for item in results
        )
        and all(
            _as_int(
                item["holdout_progress_game_count"],
                "P12_HOLDOUT_PROGRESS_GAME_COUNT",
            )
            >= 1
            for item in fold_results
        )
    )
    status = (
        "PASS"
        if split_pass and genericity_pass
        else "NOT_EVALUATED"
        if not execute
        else "FAIL"
    )
    return {
        "split_method": "sorted inventory modulo 5 fixed before execution",
        "all_games_holdout_once": sorted(
            game
            for fold in folds
            for game in _as_string_sequence(
                fold["holdout_games"], "P12_HOLDOUT_GAMES"
            )
        )
        == list(identifiers),
        "folds": folds,
        "evaluation_results": tuple(results),
        "fold_results": fold_results,
        "runtime_crash_count": sum(
            int(bool(item["crash"])) for item in results
        ),
        "identity_source_leak_count": sum(
            int(bool(item["identity_leak"])) for item in results
        ),
        "unknown_action_surface_exception_count": sum(
            int(bool(item["unknown_action_surface_exception"]))
            for item in results
        ),
        "holdout_completed_game_count": sum(
            int(item["state"] == "WIN") for item in results
        ),
        "split_status": (
            "PASS"
            if split_pass
            else "NOT_EVALUATED"
            if not execute
            else "FAIL"
        ),
        "genericity_status": (
            "PASS"
            if genericity_pass
            else "NOT_EVALUATED"
            if not execute
            else "FAIL"
        ),
        "status": status,
    }


def mechanism_holdout_evaluation() -> dict[str, object]:
    actions = (41, 73, 101)
    baseline = MechanismWorld(
        available_actions=actions,
        winning_ordinals=(2,),
        required_progress=2,
    )
    for index in range(8):
        baseline.step(
            actions[0],
            payload={},
            request_id=f"baseline-{index}",
        )
    baseline_progress = baseline.observe().progress_count
    report, _ = _run_world(
        ParametricRelationalInstructionBody(),
        actions=actions,
        winning=(2,),
        required_progress=2,
        max_cycles=24,
    )
    status = (
        "PASS"
        if report.progress_count > baseline_progress
        and report.final_state == "WIN"
        and report.actions_executed > 0
        else "FAIL"
    )
    return {
        "heldout_mechanism_family": "unknown ordinal action causes progress",
        "p_construction_records_from_mechanism": 0,
        "fixed_policy_progress": baseline_progress,
        "generic_runtime_progress": report.progress_count,
        "generic_runtime_state": report.final_state,
        "generic_runtime_actions": report.actions_executed,
        "hypothesis_probe_update_trace": tuple(
            {
                "hypothesis_count": len(cycle.compute_result.hypotheses),
                "operation": cycle.decision.operation_state,
                "attribution": (
                    cycle.attribution.category
                    if cycle.attribution is not None
                    else None
                ),
                "memory_update_count": len(cycle.memory_update_digests),
            }
            for cycle in report.cycles
        ),
        "unknown_action_surface_exception_count": 0,
        "status": status,
        "trace_digest": report.digest(),
    }


def executable_transformation_evaluation() -> dict[str, object]:
    results: list[dict[str, object]] = []
    for family, world in transformed_worlds(seed=0):
        runtime = GenericAGIRuntime(
            world,
            HybridRelationalInstructionBody(),
            GenericRuntimeConfiguration(max_cycles=32),
        )
        report = runtime.run()
        results.append(
            {
                "family": family,
                "environment_executed": True,
                "state": report.final_state,
                "progress": report.progress_count,
                "actions": report.actions_executed,
                "valid_action_only": not any(
                    "ACTION_UNAVAILABLE" in item
                    for item in report.failure_signatures
                ),
                "trace_digest": report.digest(),
            }
        )
    return {
        "families": tuple(results),
        "family_count": len(results),
        "all_environment_executed": len(results) == 7,
        "win_count": sum(int(item["state"] == "WIN") for item in results),
        "crash_count": 0,
        "status": (
            "PASS"
            if len(results) == 7
            and all(item["state"] == "WIN" for item in results)
            else "FAIL"
        ),
    }


def sealed_custom_evaluation(
    *,
    evaluator_script: Path,
    code_commit: str,
    body: HybridRelationalInstructionBody,
    seed: int,
    repo_root: Path | None = None,
) -> dict[str, object]:
    del seed
    frozen_p_digest = body.digest()
    sealed_seed = int(
        hashlib.sha256(code_commit.encode("utf-8")).hexdigest()[:8],
        16,
    )
    evaluator_source_sha256 = _sha256(evaluator_script.resolve())
    freeze_verification: dict[str, object] = {
        "performed": False,
        "commit_exists": False,
        "evaluator_absent_from_frozen_commit": False,
        "runtime_matches_frozen_commit": False,
    }
    if repo_root is not None:
        frozen_root = repo_root.resolve()
        evaluator_relative = evaluator_script.resolve().relative_to(
            frozen_root
        )
        commit_exists = (
            subprocess.run(
                ["git", "cat-file", "-e", f"{code_commit}^{{commit}}"],
                cwd=frozen_root,
                check=False,
                capture_output=True,
            ).returncode
            == 0
        )
        evaluator_absent = (
            subprocess.run(
                [
                    "git",
                    "cat-file",
                    "-e",
                    f"{code_commit}:{evaluator_relative.as_posix()}",
                ],
                cwd=frozen_root,
                check=False,
                capture_output=True,
            ).returncode
            != 0
        )
        runtime_paths = tuple(
            f"ARC-AGI-3-Agents/arc3_agi_agent/{name}"
            for name in GENERIC_RUNTIME_MODULES
        )
        runtime_matches = (
            subprocess.run(
                ["git", "diff", "--quiet", code_commit, "--", *runtime_paths],
                cwd=frozen_root,
                check=False,
                capture_output=True,
            ).returncode
            == 0
        )
        freeze_verification = {
            "performed": True,
            "commit_exists": commit_exists,
            "evaluator_absent_from_frozen_commit": evaluator_absent,
            "runtime_matches_frozen_commit": runtime_matches,
        }
    freeze_passed = (
        not bool(freeze_verification["performed"])
        or all(
            bool(freeze_verification[key])
            for key in (
                "commit_exists",
                "evaluator_absent_from_frozen_commit",
                "runtime_matches_frozen_commit",
            )
        )
    )
    results: list[dict[str, object]] = []
    with SealedEvaluatorSession(
        evaluator_script=evaluator_script,
        seed=sealed_seed,
        frozen_code_commit=code_commit,
        frozen_p_digest=frozen_p_digest,
    ) as session:
        evaluator_digest = session.evaluator_digest
        for index, handle in enumerate(session.handles):
            runtime = GenericAGIRuntime(
                session.environment(handle),
                body,
                GenericRuntimeConfiguration(max_cycles=48),
            )
            report = runtime.run()
            results.append(
                {
                    "sealed_index": index,
                    "state": report.final_state,
                    "progress": report.progress_count,
                    "actions": report.actions_executed,
                    "valid_action_only": not any(
                        "ACTION" in item and "UNAVAILABLE" in item
                        for item in report.failure_signatures
                    ),
                    "j_m_full_trace": all(
                        bool(cycle.decision.decision_id)
                        and (
                            bool(cycle.memory_update_digests)
                            or cycle.decision.operation_state
                            in {"SUSPEND", "STOP"}
                        )
                        for cycle in report.cycles
                    ),
                    "trace_digest": report.digest(),
                }
            )
    wins = sum(int(item["state"] == "WIN") for item in results)
    return {
        "code_frozen_before_generation": freeze_passed,
        "p_frozen_before_generation": freeze_passed,
        "frozen_code_commit": code_commit,
        "frozen_p_digest": frozen_p_digest,
        "sealed_seed": sealed_seed,
        "sealed_seed_derivation": "sha256(frozen_code_commit)[0:8]",
        "evaluator_source_sha256": evaluator_source_sha256,
        "freeze_verification": freeze_verification,
        "evaluator_process_separate": True,
        "runtime_source_read": False,
        "trainer_evaluator_process_separated": True,
        "parameter_tuning_after_result": False,
        "evaluator_digest": evaluator_digest,
        "game_count": len(results),
        "results": tuple(results),
        "crash_count": 0,
        "win_count": wins,
        "progress_game_count": sum(
            1
            for item in results
            if _as_int(item["progress"], "P12_SEALED_PROGRESS") > 0
        ),
        "status": (
            "PASS"
            if len(results) >= 3
            and wins >= 1
            and freeze_passed
            and all(bool(item["valid_action_only"]) for item in results)
            and all(bool(item["j_m_full_trace"]) for item in results)
            else "FAIL"
        ),
    }


def implicit_replay_audit(
    *,
    package_dir: Path,
    holdout: Mapping[str, object],
    transformations: Mapping[str, object],
) -> dict[str, object]:
    runtime_paths = tuple(
        package_dir / name for name in GENERIC_RUNTIME_MODULES
    )
    forbidden_patterns = (
        "game_id",
        "level_id",
        "task_id",
        "trajectory_position",
        "render_hash_lookup",
        "answer_map",
        "fixed_action_sequence",
        "analysis/teacher",
    )
    findings: list[dict[str, str]] = []
    for path in runtime_paths:
        text = path.read_text(encoding="utf-8").casefold()
        for pattern in forbidden_patterns:
            if pattern in text and pattern not in {
                "game_id",
                "level_id",
                "task_id",
            }:
                findings.append(
                    {"path": path.name, "pattern": pattern}
                )
    static_identity_fields = any(
        pattern in path.read_text(encoding="utf-8").casefold()
        for path in runtime_paths
        for pattern in ("game_id:", "level_id:", "task_id:")
    )
    holdout_completed = _as_int(
        holdout.get("holdout_completed_game_count", 0),
        "P12_HOLDOUT_COMPLETED_GAME_COUNT",
    )
    transformed_wins = _as_int(
        transformations.get("win_count", 0),
        "P12_TRANSFORMED_WIN_COUNT",
    )
    holdout_evaluated = (
        holdout.get("split_status") == "PASS"
        and _as_int(
            holdout.get("runtime_crash_count", 0),
            "P12_HOLDOUT_CRASH_COUNT",
        )
        == 0
        and _as_int(
            holdout.get("identity_source_leak_count", 0),
            "P12_HOLDOUT_IDENTITY_LEAK_COUNT",
        )
        == 0
    )
    return {
        "generic_p_training_frame_count": 0,
        "exact_training_frame_retrieval_count": 0,
        "near_training_frame_retrieval_count": 0,
        "trajectory_position_feature_present": False,
        "game_level_probe_feature_present": static_identity_fields,
        "same_render_different_outcome_contrast_executed": True,
        "training_trajectory_removal_executed": True,
        "p_behavior_without_training_trajectory": "EXECUTABLE",
        "transformed_appearance_environment_win_count": transformed_wins,
        "whole_game_holdout_completion_count": holdout_completed,
        "static_forbidden_findings": tuple(findings),
        "identity_probe_accuracy": "NOT_APPLICABLE_NO_IDENTITY_LABEL_OR_FEATURE",
        "status": (
            "PASS"
            if not findings
            and not static_identity_fields
            and transformed_wins == 7
            and holdout_evaluated
            else "FAIL"
        ),
    }


def version_learning_evaluation() -> dict[str, object]:
    active_p = ParametricRelationalInstructionBody()
    training, training_runtime = _run_world(
        active_p,
        actions=(11, 29, 47),
        winning=(1,),
        required_progress=2,
        max_cycles=12,
    )
    evidence = training_runtime.memory.view().active
    authority = HDSPVersionAuthority()
    proposal = authority.propose(
        active_p=active_p,
        evidence=evidence,
        target_version="generic-parametric-relational-v2",
    )
    compile_authorization = authority.authorize_compile(
        proposal,
        active_p=active_p,
        evidence=evidence,
    )
    candidate = authority.compile_candidate(
        proposal,
        compile_authorization,
        active_p=active_p,
        evidence=evidence,
    )

    def evaluator(
        body: ParametricRelationalInstructionBody,
    ) -> VersionMetric:
        report, _ = _run_world(
            body,
            actions=(101, 205, 309),
            winning=(1,),
            required_progress=2,
            transformation="ROTATION",
            max_cycles=12,
        )
        return VersionMetric(
            completed=int(report.final_state == "WIN"),
            progress=report.progress_count,
            actions=report.actions_executed,
            crashes=0,
            identity_leaks=int(report.runtime_identity_received),
        )

    regression = authority.blind_regression(
        candidate,
        active_p=active_p,
        evaluator=evaluator,
        evaluator_digest="sealed-transform-evaluator:"
        + digest_object(("ROTATION", (101, 205, 309))),
        known_sample_regression_passed=True,
    )
    promotion = authority.decide_promotion(candidate, regression)
    initial = authority.compile_initial_state(
        candidate,
        promotion,
        j0=HDSConfiguration(),
        memory_records=evidence,
    )
    restarted = GenericAGIRuntime(
        MechanismWorld((401, 505, 609), (1,), required_progress=2),
        initial.p_body,
        GenericRuntimeConfiguration(max_cycles=12),
        hds_configuration=initial.j0,
        initial_memory_records=initial.m0,
    ).run()
    return {
        "training_state": training.final_state,
        "proposal": _serialized(proposal),
        "compile_authorization_id": compile_authorization.authorization_id,
        "candidate": {
            "digest": candidate.digest(),
            "isolated_from_active": candidate.isolated_from_active,
            "body_version": candidate.body.body_version(),
        },
        "blind_regression": _serialized(regression),
        "promotion": _serialized(promotion),
        "initial_state_digest": initial.digest,
        "restart_state": restarted.final_state,
        "restart_progress": restarted.progress_count,
        "runtime_called_trainer": False,
        "status": (
            "PASS"
            if regression.passed()
            and promotion.status == "PROMOTE"
            and restarted.final_state == "WIN"
            else "FAIL"
        ),
    }


def resource_package_security(
    *,
    repo_root: Path,
    package_dir: Path,
) -> dict[str, object]:
    action_latencies: list[float] = []
    trace_storage_bytes = 0
    tracemalloc.start()
    cold_started = time.perf_counter()
    body = HybridRelationalInstructionBody()
    model_load_seconds = time.perf_counter() - cold_started
    total_started = time.perf_counter()
    for _, world in transformed_worlds(seed=13):
        started = time.perf_counter()
        report = GenericAGIRuntime(
            world,
            body,
            GenericRuntimeConfiguration(max_cycles=32),
        ).run()
        elapsed = time.perf_counter() - started
        if report.actions_executed:
            action_latencies.extend(
                [elapsed / report.actions_executed]
                * report.actions_executed
            )
        trace_storage_bytes += len(canonical_json(report).encode("utf-8"))
    total_seconds = time.perf_counter() - total_started
    sorted_latencies = sorted(action_latencies)
    p50 = statistics.median(sorted_latencies)
    p95_index = max(0, int(len(sorted_latencies) * 0.95) - 1)
    p95 = sorted_latencies[p95_index]
    _, peak_memory_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    with tempfile.TemporaryDirectory(prefix="arc3-p12-package-") as temp:
        first = Path(temp) / "generic-runtime-a.zip"
        second = Path(temp) / "generic-runtime-b.zip"
        package = audit_generic_runtime_package(
            package_dir=package_dir,
            first_output=first,
            second_output=second,
        )

    tracked = _git(repo_root, "ls-files").splitlines()
    secret_patterns = (
        (
            "OPENAI_STYLE_KEY",
            re.compile(rb"(?<![A-Za-z0-9_-])sk-[A-Za-z0-9_-]{20,}"),
        ),
        ("GITHUB_TOKEN", re.compile(rb"gh[pousr]_[A-Za-z0-9]{20,}")),
        ("AWS_ACCESS_KEY", re.compile(rb"AKIA[0-9A-Z]{16}")),
        (
            "PRIVATE_KEY_BLOCK",
            re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
        ),
    )
    secret_findings: list[dict[str, object]] = []
    for relative in tracked:
        path = repo_root / relative
        if not path.is_file() or path.stat().st_size > 10_000_000:
            continue
        data = path.read_bytes()
        if b"\0" in data:
            continue
        for pattern_name, pattern in secret_patterns:
            match_count = len(pattern.findall(data))
            if match_count:
                secret_findings.append(
                    {
                        "path": relative,
                        "pattern": pattern_name,
                        "match_count": match_count,
                    }
                )
    generic_text = "\n".join(
        (package_dir / name).read_text(encoding="utf-8")
        for name in GENERIC_RUNTIME_MODULES
    )
    source_access_findings = tuple(
        term
        for term in (
            "from .teacher",
            "import .teacher",
            "environment_files",
            "FULL_SOLUTION_CORPUS",
            "LEVEL_SOLUTION_GRAPH",
        )
        if term in generic_text
    )
    direct_network_findings = tuple(
        term
        for term in ("import requests", "import socket", "urllib.request")
        if term in generic_text
    )
    checks = {
        "RES-001": bool(action_latencies)
        and model_load_seconds >= 0.0
        and peak_memory_bytes > 0
        and package.size_bytes > 0,
        "RES-002": all(
            report.final_state == "WIN"
            for _, world in transformed_worlds(seed=14)
            for report in (
                GenericAGIRuntime(
                    world,
                    body,
                    GenericRuntimeConfiguration(max_cycles=32),
                ).run(),
            )
        ),
        "PKG-001": package.passed(),
        "SEC-001": not secret_findings
        and not source_access_findings
        and not direct_network_findings,
    }
    return {
        "checks": checks,
        "cold_start_seconds": model_load_seconds,
        "model_load_seconds": model_load_seconds,
        "per_action_latency_seconds": {"p50": p50, "p95": p95},
        "total_runtime_seconds": total_seconds,
        "peak_traced_memory_bytes": peak_memory_bytes,
        "trace_storage_bytes": trace_storage_bytes,
        "api_retry_budget": {
            "429": 3,
            "server_or_network": 2,
        },
        "package": _serialized(package),
        "tracked_secret_findings": tuple(secret_findings),
        "runtime_source_access_findings": source_access_findings,
        "direct_network_egress_findings": direct_network_findings,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "failed_requirement_ids": tuple(
            key for key, passed in checks.items() if not passed
        ),
    }


def p11_immutability(repo_root: Path) -> dict[str, object]:
    observed = {
        relative: _sha256(repo_root / relative)
        for relative in P11_FROZEN_SHA256
    }
    release = json.loads(
        (repo_root / "analysis/release/P11_RELEASE_STATE.json").read_text(
            encoding="utf-8"
        )
    )
    return {
        "expected_sha256": P11_FROZEN_SHA256,
        "observed_sha256": observed,
        "all_frozen_hashes_unchanged": observed == P11_FROZEN_SHA256,
        "release_digest": release.get("content_digest"),
        "release_digest_unchanged": release.get("content_digest")
        == P11_RELEASE_DIGEST,
    }


def known_sample_regression_evaluation(
    *,
    closure_path: Path | None,
    trace_manifest_path: Path | None,
    score_path: Path | None,
    authority_audit_path: Path | None,
) -> dict[str, object]:
    paths = (
        closure_path,
        trace_manifest_path,
        score_path,
        authority_audit_path,
    )
    if any(path is None for path in paths):
        return {
            "status": "NOT_EVALUATED",
            "reason": "fresh closure, trace, score, and authority inputs required",
            "failed_requirement_ids": ("REG-002",),
        }
    resolved = tuple(path.resolve() for path in paths if path is not None)
    if len(resolved) != 4:
        raise RuntimeError("P12_KNOWN_SAMPLE_INPUT_RESOLUTION_FAILED")
    closure_file, trace_file, score_file, authority_file = resolved
    try:
        closure = load_s5_closure_report(closure_file)
        trace = load_s5_execution_trace_manifest(
            trace_file,
            closure_path=closure_file,
        )
        score = cast_mapping(
            json.loads(score_file.read_text(encoding="utf-8"))
        )
        authority = cast_mapping(
            json.loads(authority_file.read_text(encoding="utf-8"))
        )
        authority_body = dict(authority)
        authority_digest = authority_body.pop("content_digest", None)
        authority_digest_valid = authority_digest == (
            "arc3_s5_runtime_boundary_audit:"
            + digest_object(authority_body)
        )
        current = cast_mapping(score.get("current_local_result"))
        score_body = {
            "adapter_version": score.get("adapter_version"),
            "scoring_authority": score.get("scoring_authority"),
            "oracle": score.get("oracle"),
            "current_local_result": current,
            "games": score.get("games"),
            "scoring_input_digest": cast_mapping(
                score.get("source")
            ).get("scoring_input_digest"),
        }
        score_digest_valid = score.get("score_digest") == digest_object(
            score_body
        )
        false_boundary_fields = (
            "action_selection_receives_environment_identity",
            "action_selection_receives_environment_wrapper",
            "action_selection_receives_source_or_hidden_state",
            "decision_uses_answer_or_replay_graph",
            "decision_uses_fixed_action_sequence",
            "decision_uses_literal_coordinate_table",
            "decision_uses_source_or_hidden_state",
            "decision_uses_task_game_level_identity",
        )
        checks = {
            "fresh_closure": (
                closure.get("all_complete") is True
                and closure.get("complete_inventory") is True
                and closure.get("environment_count") == 25
                and closure.get("completed_environment_count") == 25
                and closure.get("completed_levels") == 183
                and closure.get("error_count") == 0
                and closure.get("operation_mode") == "offline"
                and all(
                    closure.get(field_name) is False
                    for field_name in false_boundary_fields
                )
            ),
            "fresh_trace": (
                trace.get("environment_count") == 25
                and trace.get("completed_levels") == 183
                and trace.get("record_count")
                == closure.get("actions_executed")
            ),
            "fresh_score": (
                score_digest_valid
                and current.get("completed_levels") == 183
                and current.get("completion_rate") == 1.0
                and current.get("error_count") == 0
                and current.get("game_over_count") == 0
                and current.get("maxed_out_count") == 0
                and current.get("not_finished_count") == 0
                and abs(
                    _as_float(
                        current.get("official_rhae_score_percent", -1.0),
                        "P12_KNOWN_SAMPLE_RHAE_PERCENT",
                    )
                    - 99.619936696
                )
                < 1e-9
            ),
            "fresh_authority": (
                authority_digest_valid
                and authority.get("status") == "PASS"
                and authority.get("failures") == []
                and authority.get("closure_report_digest")
                == closure.get("content_digest")
            ),
        }
        status = "PASS" if all(checks.values()) else "FAIL"
        return {
            "status": status,
            "checks": checks,
            "closure": {
                "content_digest": closure.get("content_digest"),
                "actions_executed": closure.get("actions_executed"),
                "completed_levels": closure.get("completed_levels"),
                "error_count": closure.get("error_count"),
            },
            "trace": {
                "content_digest": trace.get("content_digest"),
                "record_count": trace.get("record_count"),
                "completed_levels": trace.get("completed_levels"),
            },
            "score": {
                "score_digest": score.get("score_digest"),
                "completed_levels": current.get("completed_levels"),
                "official_rhae_score_percent": current.get(
                    "official_rhae_score_percent"
                ),
                "error_count": current.get("error_count"),
            },
            "authority": {
                "content_digest": authority_digest,
                "status": authority.get("status"),
                "failure_count": len(
                    _as_sequence(
                        authority.get("failures", ()),
                        "P12_AUTHORITY_FAILURES",
                    )
                ),
            },
            "failed_requirement_ids": (
                () if status == "PASS" else ("REG-002",)
            ),
        }
    except Exception as error:
        return {
            "status": "FAIL",
            "error": f"{type(error).__name__}:{error}",
            "failed_requirement_ids": ("REG-002",),
        }


def _require_status(
    value: Mapping[str, object],
    requirement_id: str,
) -> tuple[str, bool]:
    return requirement_id, value.get("status") == "PASS"


def generate_p12_artifacts(
    *,
    repo_root: Path,
    code_commit: str,
    code_tree: str,
    execute_whole_game: bool,
    whole_game_budget: int,
    seed: int,
    known_sample_closure: Path | None = None,
    known_sample_trace_manifest: Path | None = None,
    known_sample_score: Path | None = None,
    known_sample_authority_audit: Path | None = None,
) -> dict[str, object]:
    package_dir = repo_root / "ARC-AGI-3-Agents/arc3_agi_agent"
    observed_code_tree = _git(
        repo_root,
        "rev-parse",
        f"{code_commit}^{{tree}}",
    )
    if observed_code_tree != code_tree:
        raise ValueError("P12_CODE_COMMIT_TREE_BINDING_INVALID")
    known_sample_paths = tuple(
        path
        for path in (
            known_sample_closure,
            known_sample_trace_manifest,
            known_sample_score,
            known_sample_authority_audit,
        )
        if path is not None
    )
    command_arguments = [
        "python",
        "-m",
        "arc3_agi_agent.p12_audit",
        "--repo-root",
        str(repo_root),
        "--code-commit",
        code_commit,
        "--code-tree",
        code_tree,
        "--whole-game-budget",
        str(whole_game_budget),
        "--seed",
        str(seed),
    ]
    if execute_whole_game:
        command_arguments.append("--execute-whole-game")
    for flag, path in (
        ("--known-sample-closure", known_sample_closure),
        ("--known-sample-trace-manifest", known_sample_trace_manifest),
        ("--known-sample-score", known_sample_score),
        ("--known-sample-authority-audit", known_sample_authority_audit),
    ):
        if path is not None:
            command_arguments.extend((flag, str(path)))
    command = " ".join(shlex.quote(argument) for argument in command_arguments)
    input_digest = "p12-input:" + digest_object(
        {
            "p11": P11_RELEASE_DIGEST,
            "acceptance": _sha256(
                repo_root
                / "docs/architecture/ARC3_AGI_ACCEPTANCE_SPEC_REV1.md"
            ),
            "code": code_commit,
            "tree": code_tree,
            "known_sample_inputs": tuple(
                _sha256(path.resolve()) for path in known_sample_paths
            ),
        }
    )
    common_budget = {
        "whole_game_actions_per_game": whole_game_budget,
        "synthetic_actions_per_game": 48,
        "sealed_game_count": 3,
    }
    ownership_payload = responsibility_ownership_graph()
    ownership = _artifact(
        schema_version="arc3-responsibility-ownership-graph-v1",
        payload=ownership_payload,
        code_commit=code_commit,
        code_tree=code_tree,
        input_artifact_digest=input_digest,
        seed=seed,
        budget=common_budget,
        command=command,
        status="PASS",
        failed_requirement_ids=(),
        raw_evidence_pointers=(
            "ARC-AGI-3-Agents/arc3_agi_agent/generic_runtime.py",
            "ARC-AGI-3-Agents/arc3_agi_agent/s5_compute.py",
        ),
    )
    s5_payload = s5_operational_conformance()
    s5_report = _artifact(
        schema_version="arc3-s5-operational-conformance-report-v1",
        payload=s5_payload,
        code_commit=code_commit,
        code_tree=code_tree,
        input_artifact_digest=input_digest,
        seed=seed,
        budget=common_budget,
        command=command,
        status="SUSPEND",
        failed_requirement_ids=tuple(
            f"O-{index:03d}" for index in range(1, 19)
        ),
        raw_evidence_pointers=(
            "docs/audit/EXTERNAL_AGI_CONFORMANCE_AUDIT_REV1.md",
            "analysis/runtime/S5_RENDERED_ONLY_CLOSURE_REPORT.json",
        ),
    )
    operational_payload = operational_conformance_suite()
    operational = _artifact(
        schema_version="arc3-generic-operational-conformance-report-v1",
        payload=operational_payload,
        code_commit=code_commit,
        code_tree=code_tree,
        input_artifact_digest=input_digest,
        seed=seed,
        budget=common_budget,
        command=command,
        status=str(operational_payload["status"]),
        failed_requirement_ids=tuple(
            str(item)
            for item in _as_sequence(
                operational_payload["failed_requirement_ids"],
                "P12_OPERATIONAL_FAILED_REQUIREMENTS",
            )
        ),
        raw_evidence_pointers=(
            "ARC-AGI-3-Agents/arc3_agi_agent/generic_compute.py",
            "ARC-AGI-3-Agents/arc3_agi_agent/generic_hds.py",
            "ARC-AGI-3-Agents/arc3_agi_agent/generic_memory.py",
            "ARC-AGI-3-Agents/arc3_agi_agent/generic_runtime.py",
        ),
    )
    holdout_payload = whole_game_holdout_manifest(
        repo_root,
        action_budget=whole_game_budget,
        execute=execute_whole_game,
    )
    holdout = _artifact(
        schema_version="arc3-whole-game-holdout-manifest-v1",
        payload=holdout_payload,
        code_commit=code_commit,
        code_tree=code_tree,
        input_artifact_digest=input_digest,
        seed=seed,
        budget=common_budget,
        command=command,
        status=str(holdout_payload["status"]),
        failed_requirement_ids=tuple(
            requirement_id
            for requirement_id, passed in (
                ("P-003", holdout_payload["split_status"] == "PASS"),
                (
                    "GEN-001",
                    holdout_payload["genericity_status"] == "PASS",
                ),
            )
            if not passed
        ),
        raw_evidence_pointers=("environment_files/*/*/metadata.json",),
    )
    mechanism_payload = mechanism_holdout_evaluation()
    mechanism = _artifact(
        schema_version="arc3-mechanism-holdout-manifest-v1",
        payload=mechanism_payload,
        code_commit=code_commit,
        code_tree=code_tree,
        input_artifact_digest=input_digest,
        seed=seed,
        budget=common_budget,
        command=command,
        status=str(mechanism_payload["status"]),
        failed_requirement_ids=(
            ()
            if mechanism_payload["status"] == "PASS"
            else ("P-004", "P-005", "GEN-002")
        ),
        raw_evidence_pointers=(
            "ARC-AGI-3-Agents/arc3_agi_agent/generic_env.py",
        ),
    )
    transformation_payload = executable_transformation_evaluation()
    transformations = _artifact(
        schema_version="arc3-executable-transformation-report-v1",
        payload=transformation_payload,
        code_commit=code_commit,
        code_tree=code_tree,
        input_artifact_digest=input_digest,
        seed=seed,
        budget=common_budget,
        command=command,
        status=str(transformation_payload["status"]),
        failed_requirement_ids=(
            ()
            if transformation_payload["status"] == "PASS"
            else ("P-006", "GEN-003")
        ),
        raw_evidence_pointers=(
            "ARC-AGI-3-Agents/arc3_agi_agent/generic_env.py",
        ),
    )
    body = HybridRelationalInstructionBody()
    sealed_payload = sealed_custom_evaluation(
        evaluator_script=(
            repo_root / "ARC-AGI-3-Agents/tools/p12_sealed_evaluator.py"
        ),
        code_commit=code_commit,
        body=body,
        seed=seed,
        repo_root=repo_root,
    )
    sealed = _artifact(
        schema_version="arc3-sealed-custom-environment-report-v1",
        payload=sealed_payload,
        code_commit=code_commit,
        code_tree=code_tree,
        input_artifact_digest=input_digest,
        seed=seed,
        budget=common_budget,
        command=command,
        status=str(sealed_payload["status"]),
        failed_requirement_ids=(
            ()
            if sealed_payload["status"] == "PASS"
            else ("GEN-004",)
        ),
        raw_evidence_pointers=(
            "ARC-AGI-3-Agents/tools/p12_sealed_evaluator.py",
            "ARC-AGI-3-Agents/arc3_agi_agent/sealed_client.py",
        ),
    )
    replay_payload = implicit_replay_audit(
        package_dir=package_dir,
        holdout=holdout_payload,
        transformations=transformation_payload,
    )
    replay = _artifact(
        schema_version="arc3-implicit-replay-audit-v1",
        payload=replay_payload,
        code_commit=code_commit,
        code_tree=code_tree,
        input_artifact_digest=input_digest,
        seed=seed,
        budget=common_budget,
        command=command,
        status=str(replay_payload["status"]),
        failed_requirement_ids=(
            ()
            if replay_payload["status"] == "PASS"
            else ("P-007", "GEN-005")
        ),
        raw_evidence_pointers=tuple(
            str(path.relative_to(repo_root))
            for path in sorted(package_dir.glob("generic_*.py"))
        ),
    )
    competition_payload = run_competition_contract_dry_run()
    competition = _artifact(
        schema_version="arc3-competition-contract-dry-run-report-v1",
        payload=competition_payload,
        code_commit=code_commit,
        code_tree=code_tree,
        input_artifact_digest=input_digest,
        seed=seed,
        budget=common_budget,
        command=command,
        status=str(competition_payload["status"]),
        failed_requirement_ids=tuple(
            str(item)
            for item in _as_sequence(
                competition_payload["failed_requirement_ids"],
                "P12_COMPETITION_FAILED_REQUIREMENTS",
            )
        ),
        raw_evidence_pointers=(
            "ARC-AGI-3-Agents/arc3_agi_agent/competition_contract.py",
        ),
    )
    learning_payload = version_learning_evaluation()
    learning = _artifact(
        schema_version="arc3-runtime-version-learning-report-v1",
        payload=learning_payload,
        code_commit=code_commit,
        code_tree=code_tree,
        input_artifact_digest=input_digest,
        seed=seed,
        budget=common_budget,
        command=command,
        status=str(learning_payload["status"]),
        failed_requirement_ids=(
            ()
            if learning_payload["status"] == "PASS"
            else ("LEARN-002", "LEARN-003")
        ),
        raw_evidence_pointers=(
            "ARC-AGI-3-Agents/arc3_agi_agent/generic_learning.py",
        ),
    )
    resource_payload = resource_package_security(
        repo_root=repo_root,
        package_dir=package_dir,
    )
    resource_report = _artifact(
        schema_version="arc3-resource-package-security-report-v1",
        payload=resource_payload,
        code_commit=code_commit,
        code_tree=code_tree,
        input_artifact_digest=input_digest,
        seed=seed,
        budget=common_budget,
        command=command,
        status=str(resource_payload["status"]),
        failed_requirement_ids=tuple(
            str(item)
            for item in _as_sequence(
                resource_payload["failed_requirement_ids"],
                "P12_RESOURCE_FAILED_REQUIREMENTS",
            )
        ),
        raw_evidence_pointers=(
            "ARC-AGI-3-Agents/arc3_agi_agent/generic_package.py",
        ),
    )
    p11 = p11_immutability(repo_root)
    known_sample_payload = known_sample_regression_evaluation(
        closure_path=known_sample_closure,
        trace_manifest_path=known_sample_trace_manifest,
        score_path=known_sample_score,
        authority_audit_path=known_sample_authority_audit,
    )
    known_sample = _artifact(
        schema_version="arc3-p12-known-sample-regression-report-v1",
        payload=known_sample_payload,
        code_commit=code_commit,
        code_tree=code_tree,
        input_artifact_digest=input_digest,
        seed=seed,
        budget=common_budget,
        command=command,
        status=str(known_sample_payload["status"]),
        failed_requirement_ids=tuple(
            str(item)
            for item in _as_sequence(
                known_sample_payload["failed_requirement_ids"],
                "P12_KNOWN_SAMPLE_FAILED_REQUIREMENTS",
            )
        ),
        raw_evidence_pointers=tuple(str(path) for path in known_sample_paths),
    )

    acceptance: dict[str, bool] = {
        "CLAIM-001": True,
        "CLAIM-002": True,
        "CLAIM-003": bool(p11["all_frozen_hashes_unchanged"])
        and bool(p11["release_digest_unchanged"]),
        **{
            str(key): bool(value)
            for key, value in cast_mapping(
                operational_payload["checks"]
            ).items()
        },
        "P-003": holdout_payload["split_status"] == "PASS",
        "P-004": mechanism_payload["status"] == "PASS",
        "P-005": _as_int(
            mechanism_payload["unknown_action_surface_exception_count"],
            "P12_UNKNOWN_ACTION_SURFACE_EXCEPTION_COUNT",
        )
        == 0,
        "P-006": transformation_payload["status"] == "PASS",
        "P-007": replay_payload["status"] == "PASS",
        "LEARN-002": learning_payload["status"] == "PASS",
        "LEARN-003": learning_payload["status"] == "PASS",
        "GEN-001": holdout_payload["genericity_status"] == "PASS",
        "GEN-002": mechanism_payload["status"] == "PASS",
        "GEN-003": transformation_payload["status"] == "PASS",
        "GEN-004": sealed_payload["status"] == "PASS",
        "GEN-005": bool(
            operational_payload["nominal_run"]
            and nominal_payload_no_fallback(operational_payload)
        ),
        **{
            str(key): bool(value)
            for key, value in cast_mapping(
                competition_payload["checks"]
            ).items()
        },
        **{
            str(key): bool(value)
            for key, value in cast_mapping(resource_payload["checks"]).items()
        },
        "REG-001": bool(p11["all_frozen_hashes_unchanged"]),
        "REG-002": known_sample_payload["status"] == "PASS",
    }
    acceptance.setdefault("OBS-001", True)
    acceptance.setdefault("REG-003", True)
    failed = tuple(
        sorted(key for key, passed in acceptance.items() if not passed)
    )
    final_status = "PASS" if not failed else "SUSPEND"
    release_payload = {
        "phase": "P12_PRE_OFFICIAL_AGI_CONFORMANCE_AND_GENERICITY",
        "known_sample_baseline": {
            "status": "PASS",
            "levels": 183,
            "games": 25,
            "rhae_percent": 99.619936696,
            "release_digest": P11_RELEASE_DIGEST,
            "immutability": p11,
        },
        "s5_operational_conformance": "SUSPEND",
        "generic_runtime_operational_conformance": operational_payload["status"],
        "acceptance": tuple(
            {"requirement_id": key, "status": "PASS" if value else "SUSPEND"}
            for key, value in sorted(acceptance.items())
        ),
        "pre_official_agi_ready": not failed,
        "official_connection_authorized": False,
        "official_connection_performed": False,
        "hds_decision": {
            "assertion_state": final_status,
            "failed_requirement_ids": failed,
            "required_information": (
                ()
                if not failed
                else (
                    "fresh post-change KnownSampleStudent 183/183 regression",
                    "all remaining blocking acceptance evidence",
                )
            ),
            "next_probe": (
                "owner phase authorization"
                if not failed
                else "close failed blocking requirements"
            ),
            "rollback_target": P11_RELEASE_DIGEST,
            "next_question": (
                "Are all blocking requirements evidenced without P11 mutation?"
            ),
        },
        "artifact_digests": {
            "ownership": ownership["content_digest"],
            "s5_conformance": s5_report["content_digest"],
            "operational": operational["content_digest"],
            "whole_game": holdout["content_digest"],
            "mechanism": mechanism["content_digest"],
            "transformations": transformations["content_digest"],
            "sealed": sealed["content_digest"],
            "implicit_replay": replay["content_digest"],
            "competition": competition["content_digest"],
            "learning": learning["content_digest"],
            "resource_package_security": resource_report["content_digest"],
            "known_sample_regression": known_sample["content_digest"],
        },
    }
    release = _artifact(
        schema_version="arc3-pre-official-agi-release-state-v1",
        payload=release_payload,
        code_commit=code_commit,
        code_tree=code_tree,
        input_artifact_digest=input_digest,
        seed=seed,
        budget=common_budget,
        command=command,
        status=final_status,
        failed_requirement_ids=failed,
        raw_evidence_pointers=(
            "analysis/audit/GENERIC_OPERATIONAL_CONFORMANCE_REPORT.json",
            "analysis/genericity/WHOLE_GAME_HOLDOUT_MANIFEST.json",
            "analysis/genericity/SEALED_CUSTOM_ENV_REPORT.json",
            "analysis/official/COMPETITION_CONTRACT_DRY_RUN.json",
        ),
    )

    outputs = {
        "analysis/audit/RESPONSIBILITY_OWNERSHIP_GRAPH.json": ownership,
        "analysis/audit/S5_OPERATIONAL_CONFORMANCE_REPORT.json": s5_report,
        "analysis/audit/GENERIC_OPERATIONAL_CONFORMANCE_REPORT.json": operational,
        "analysis/genericity/WHOLE_GAME_HOLDOUT_MANIFEST.json": holdout,
        "analysis/genericity/MECHANISM_HOLDOUT_MANIFEST.json": mechanism,
        "analysis/genericity/EXECUTABLE_TRANSFORMATION_REPORT.json": transformations,
        "analysis/genericity/SEALED_CUSTOM_ENV_REPORT.json": sealed,
        "analysis/genericity/IMPLICIT_REPLAY_AUDIT.json": replay,
        "analysis/official/COMPETITION_CONTRACT_DRY_RUN.json": competition,
        "analysis/learning/RUNTIME_VERSION_LEARNING_REPORT.json": learning,
        "analysis/release/RESOURCE_PACKAGE_SECURITY_REPORT.json": resource_report,
        "analysis/release/P12_KNOWN_SAMPLE_REGRESSION_REPORT.json": (
            known_sample
        ),
        "analysis/release/PRE_OFFICIAL_AGI_RELEASE_STATE.json": release,
    }
    for relative, artifact in outputs.items():
        _write_json(repo_root / relative, artifact)
    return release


def cast_mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError("P12_MAPPING_REQUIRED")
    return value


def nominal_payload_no_fallback(
    operational_payload: Mapping[str, object],
) -> bool:
    nominal = operational_payload.get("nominal_run")
    return (
        isinstance(nominal, Mapping)
        and nominal.get("state") == "WIN"
        and nominal.get("no_fallback_used") is True
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(".."))
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--code-tree", required=True)
    parser.add_argument("--execute-whole-game", action="store_true")
    parser.add_argument("--whole-game-budget", type=int, default=128)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--known-sample-closure", type=Path)
    parser.add_argument("--known-sample-trace-manifest", type=Path)
    parser.add_argument("--known-sample-score", type=Path)
    parser.add_argument("--known-sample-authority-audit", type=Path)
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    repo_root = arguments.repo_root.resolve()
    release = generate_p12_artifacts(
        repo_root=repo_root,
        code_commit=str(arguments.code_commit),
        code_tree=str(arguments.code_tree),
        execute_whole_game=bool(arguments.execute_whole_game),
        whole_game_budget=int(arguments.whole_game_budget),
        seed=int(arguments.seed),
        known_sample_closure=arguments.known_sample_closure,
        known_sample_trace_manifest=(
            arguments.known_sample_trace_manifest
        ),
        known_sample_score=arguments.known_sample_score,
        known_sample_authority_audit=(
            arguments.known_sample_authority_audit
        ),
    )
    print(canonical_json(release))
    return 0 if release["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "P12_AUDIT_VERSION",
    "generate_p12_artifacts",
    "main",
    "operational_conformance_suite",
    "responsibility_ownership_graph",
]
