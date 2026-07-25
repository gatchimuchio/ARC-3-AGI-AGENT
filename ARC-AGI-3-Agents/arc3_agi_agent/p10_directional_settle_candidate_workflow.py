"""HDS-isolated directional-settle candidate compile and OFFLINE probe."""

from __future__ import annotations

import argparse
import base64
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
from .p10_directional_settle_composition_audit import (
    P10_DIRECTIONAL_SETTLE_COMPOSITION_AUDIT_SCHEMA_VERSION,
)
from .p10_instruction_compiler import (
    P10_CANDIDATE_MANIFEST_FILENAME,
    P10_COMPILER_SEED,
    P10_DIRECTIONAL_SETTLE_CANDIDATE_SET_VERSION,
    P10_DIRECTIONAL_SETTLE_COMPILER_VERSION,
    P10_DIRECTIONAL_SETTLE_HYBRID_FILENAME,
    active_p10_manifest_digest,
    compile_p10_directional_settle_hybrid_candidate,
    directional_force_route_instruction_mapping,
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

P10_DIRECTIONAL_SETTLE_CANDIDATE_WORKFLOW_SCHEMA_VERSION = (
    "arc3-p10-directional-settle-candidate-intervention-v1"
)
_AUDIT_DIGEST_PREFIX = (
    "arc3_p10_directional_settle_composition_audit:"
)
_WORKFLOW_DIGEST_PREFIX = (
    "arc3_p10_directional_settle_candidate_intervention:"
)
_RUN_CHECKPOINT_SCHEMA_VERSION = (
    "arc3-p10-directional-settle-run-checkpoint-v1"
)
_RUN_CHECKPOINT_DIGEST_PREFIX = (
    "arc3_p10_directional_settle_run_checkpoint:"
)
_SLOT_TRANSACTION_SCHEMA_VERSION = (
    "arc3-p10-directional-settle-slot-transaction-v1"
)
_SLOT_TRANSACTION_DIGEST_PREFIX = (
    "arc3_p10_directional_settle_slot_transaction:"
)
_SLOT_TRANSACTION_FILENAME = (
    "directional_settle_candidate_slot_transaction.json"
)
_ProbeCohort = Literal["stable", "target"]
_RunFunction = Callable[..., dict[str, Any]]


@dataclass(frozen=True, slots=True)
class P10DirectionalSettleProbe:
    """One retained-sample condition for the isolated hybrid candidate."""

    environment_selector: str
    cohort: _ProbeCohort
    max_actions: int

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not self.environment_selector.strip():
            failures.append("DIRECTIONAL_SETTLE_PROBE_SELECTOR_MISSING")
        if self.cohort not in {"stable", "target"}:
            failures.append("DIRECTIONAL_SETTLE_PROBE_COHORT_INVALID")
        if self.max_actions < 2:
            failures.append(
                "DIRECTIONAL_SETTLE_PROBE_ACTION_BUDGET_INVALID"
            )
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


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _content_digest_valid(
    value: Mapping[str, Any],
    prefix: str,
) -> bool:
    body = dict(value)
    claimed = str(body.pop("content_digest", ""))
    return claimed == prefix + digest_object(body)


def _encoded_bytes(value: bytes | None) -> str | None:
    if value is None:
        return None
    return base64.b64encode(value).decode("ascii")


def _decoded_bytes(value: object, field_name: str) -> bytes | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be base64 text or null")
    try:
        return base64.b64decode(value, validate=True)
    except ValueError as error:
        raise ValueError(f"{field_name} base64 invalid") from error


def _slot_transaction(
    *,
    checkpoint_dir: Path | None,
    active_manifest_digest: str,
    composition_digest: str,
    candidate_manifest_path: Path,
    candidate_body_path: Path,
) -> tuple[bytes | None, bytes | None, Path | None]:
    current_manifest = (
        candidate_manifest_path.read_bytes()
        if candidate_manifest_path.is_file()
        else None
    )
    current_body = (
        candidate_body_path.read_bytes()
        if candidate_body_path.is_file()
        else None
    )
    if checkpoint_dir is None:
        return current_manifest, current_body, None

    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    transaction_path = checkpoint_dir / _SLOT_TRANSACTION_FILENAME
    context = {
        "active_manifest_digest": active_manifest_digest,
        "composition_digest": composition_digest,
        "candidate_manifest_filename": candidate_manifest_path.name,
        "candidate_body_filename": candidate_body_path.name,
    }
    if transaction_path.is_file():
        transaction = _json_object(transaction_path)
        if (
            transaction.get("schema_version")
            != _SLOT_TRANSACTION_SCHEMA_VERSION
            or not _content_digest_valid(
                transaction,
                _SLOT_TRANSACTION_DIGEST_PREFIX,
            )
            or transaction.get("context") != context
        ):
            raise ValueError(
                "DIRECTIONAL_SETTLE_SLOT_TRANSACTION_INVALID"
            )
        prior_manifest = _decoded_bytes(
            transaction.get("prior_candidate_manifest_base64"),
            "prior candidate manifest",
        )
        prior_body = _decoded_bytes(
            transaction.get("prior_candidate_body_base64"),
            "prior candidate body",
        )
        expected_manifest_digest = transaction.get(
            "prior_candidate_manifest_sha256"
        )
        expected_body_digest = transaction.get(
            "prior_candidate_body_sha256"
        )
        if (
            expected_manifest_digest
            != (
                hashlib.sha256(prior_manifest).hexdigest()
                if prior_manifest is not None
                else None
            )
            or expected_body_digest
            != (
                hashlib.sha256(prior_body).hexdigest()
                if prior_body is not None
                else None
            )
        ):
            raise ValueError(
                "DIRECTIONAL_SETTLE_SLOT_TRANSACTION_BYTES_INVALID"
            )
        return prior_manifest, prior_body, transaction_path

    body: dict[str, object] = {
        "schema_version": _SLOT_TRANSACTION_SCHEMA_VERSION,
        "context": context,
        "prior_candidate_manifest_base64": _encoded_bytes(
            current_manifest
        ),
        "prior_candidate_manifest_sha256": (
            hashlib.sha256(current_manifest).hexdigest()
            if current_manifest is not None
            else None
        ),
        "prior_candidate_body_base64": _encoded_bytes(current_body),
        "prior_candidate_body_sha256": (
            hashlib.sha256(current_body).hexdigest()
            if current_body is not None
            else None
        ),
    }
    transaction = {
        **body,
        "content_digest": _SLOT_TRANSACTION_DIGEST_PREFIX
        + digest_object(body),
    }
    _atomic_write_bytes(transaction_path, _json_bytes(transaction))
    return current_manifest, current_body, transaction_path


def _composition_digest(audit: Mapping[str, Any]) -> str:
    checks = audit.get("contract_checks")
    judgment = audit.get("hds_judgment")
    failures: list[str] = []
    if (
        audit.get("schema_version")
        != P10_DIRECTIONAL_SETTLE_COMPOSITION_AUDIT_SCHEMA_VERSION
    ):
        failures.append("DIRECTIONAL_SETTLE_AUDIT_SCHEMA_INVALID")
    if not _content_digest_valid(audit, _AUDIT_DIGEST_PREFIX):
        failures.append("DIRECTIONAL_SETTLE_AUDIT_DIGEST_INVALID")
    if audit.get("candidate_tier") != "LOCAL_PROBE":
        failures.append("DIRECTIONAL_SETTLE_AUDIT_TIER_INVALID")
    if audit.get("development_only") is not True:
        failures.append(
            "DIRECTIONAL_SETTLE_AUDIT_DEVELOPMENT_BOUNDARY_INVALID"
        )
    if audit.get("runtime_use") != "FORBIDDEN":
        failures.append(
            "DIRECTIONAL_SETTLE_AUDIT_RUNTIME_BOUNDARY_INVALID"
        )
    if not isinstance(checks, Mapping) or not checks or not all(
        value is True for value in checks.values()
    ):
        failures.append("DIRECTIONAL_SETTLE_AUDIT_CHECKS_NOT_PASS")
    if not isinstance(judgment, Mapping):
        failures.append("DIRECTIONAL_SETTLE_AUDIT_HDS_JUDGMENT_MISSING")
    else:
        if judgment.get("local_probe_status") != "PASS":
            failures.append(
                "DIRECTIONAL_SETTLE_LOCAL_PROBE_NOT_PASS"
            )
        if (
            judgment.get("candidate_hybrid_compile_authorized")
            is not True
        ):
            failures.append(
                "DIRECTIONAL_SETTLE_CANDIDATE_COMPILE_NOT_AUTHORIZED"
            )
        if judgment.get("active_p_compile_authorized") is not False:
            failures.append(
                "DIRECTIONAL_SETTLE_ACTIVE_COMPILE_BOUNDARY_INVALID"
            )
        if judgment.get("runtime_p_promotion_authorized") is not False:
            failures.append(
                "DIRECTIONAL_SETTLE_PROMOTION_BOUNDARY_INVALID"
            )
    if failures:
        raise ValueError(";".join(sorted(set(failures))))
    return str(audit["content_digest"])


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
    observed_gap = composition_audit.get("observed_gap")
    contract = composition_audit.get("candidate_contract")
    judgment = composition_audit.get("hds_judgment")
    if (
        not isinstance(observed_gap, Mapping)
        or not isinstance(contract, Mapping)
        or not isinstance(judgment, Mapping)
    ):
        raise TypeError("directional-settle composition evidence invalid")
    observed_digest = digest_object(observed_gap)
    contract_digest = digest_object(contract)
    judgment_digest = digest_object(judgment)
    proposal = PUpdateProposal(
        proposal_id="proposal:directional-settle-hybrid",
        source_p_version=str(hybrid.get("body_version", "")),
        source_p_digest=active_manifest_digest,
        target_component="hybrid-P-B",
        update_type="transition-parameter",
        evidence_refs=(
            composition_digest,
            "evidence:observed-gap:" + observed_digest,
        ),
        expected_effect="bounded-post-progress-reobservation",
        expected_affected_capabilities=(
            "directional-force-obligation-composition",
            "stale-frame-settle-control",
        ),
        expected_unaffected_capabilities=(
            "active-runtime-manifest",
            "symbolic-instruction-body",
            "parametric-weight-matrix",
        ),
        falsifiers=(
            "target-completion-does-not-increase",
            "stable-completion-decreases",
            "candidate-rerun-differs",
            "active-manifest-changes",
        ),
        rollback_target=str(hybrid.get("body_version", "")),
        provenance=(
            composition_digest,
            "development-memory:hds-local-probe",
        ),
    )
    evidence = PUpdateEvidenceSet(
        evidence_set_id="evidence-set:directional-settle-hybrid",
        proposal_digest=proposal.digest,
        memory_snapshot_digest=(
            "development-memory-snapshot:"
            + digest_object(
                {
                    "composition": composition_digest,
                    "observed": observed_digest,
                    "contract": contract_digest,
                }
            )
        ),
        approved_memory_refs=(
            composition_digest,
            "memory:visible-successor:" + observed_digest,
        ),
        hds_memory_decision_digests=(
            "hds-memory-decision:" + judgment_digest,
        ),
        failure_refs=(
            "failure:post-progress-generic-fallback:" + observed_digest,
        ),
        contradiction_refs=(
            "contradiction:parseable-successor-release:"
            + contract_digest,
        ),
        positive_contrast_refs=(
            "contrast:bounded-settle:" + contract_digest,
        ),
        negative_contrast_refs=(
            "contrast:active-limit-zero:" + contract_digest,
        ),
        holdout_refs=(
            "holdout:stable-capability-cohort:" + contract_digest,
        ),
        replay_audit_refs=(
            "audit:identity-free-contract:" + contract_digest,
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
            "directional-settle-local-probe-pass",
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
            P10_DIRECTIONAL_SETTLE_CANDIDATE_SET_VERSION
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
    maximum_transition_observations: int,
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
    transition_mapping = directional_force_route_instruction_mapping(
        maximum_transition_observations=(
            maximum_transition_observations
        )
    )
    predecessor_parameter_digest = (
        "transition-parameter:"
        + digest_object({"maximum_transition_observations": 0})
    )
    parameter_digest = (
        "transition-parameter:"
        + digest_object(
            {
                "maximum_transition_observations": (
                    maximum_transition_observations
                )
            }
        )
    )
    descriptor = CandidatePBundle(
        candidate_id="candidate:p10-directional-settle-hybrid",
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
            transition_mapping
        ),
        parameter_change_attribution=(
            "hds-authorized-bounded-transition-observation-limit"
        ),
    )
    failures = descriptor.validate()
    if failures:
        raise ValueError(";".join(failures))
    return descriptor


def _compact_run(
    result: Mapping[str, Any],
    *,
    probe: P10DirectionalSettleProbe,
    instruction_lifecycle: str,
) -> dict[str, object]:
    reports = result.get("reports")
    errors = result.get("errors")
    if not isinstance(reports, list) or not isinstance(errors, list):
        raise TypeError(
            "directional-settle intervention result shape invalid"
        )
    report = reports[0] if len(reports) == 1 else {}
    if not isinstance(report, Mapping):
        raise TypeError(
            "directional-settle intervention report invalid"
        )
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
        "emitted_provenance_digest": digest_object(
            report.get("emitted_provenance", [])
        ),
        "trace_digests_digest": digest_object(
            report.get("trace_digests", [])
        ),
        "errors_digest": digest_object(errors),
    }
    return {
        **core,
        "run_digest": "p10-directional-settle-intervention-run:"
        + digest_object(core),
    }


class _RunCheckpointStore:
    def __init__(
        self,
        directory: Path,
        *,
        context_digest: str,
    ) -> None:
        self._directory = directory
        self._context_digest = context_digest
        self._hits = 0
        self._misses = 0
        self._records: list[dict[str, object]] = []
        directory.mkdir(parents=True, exist_ok=True)

    def execute(
        self,
        *,
        slot: str,
        probe: P10DirectionalSettleProbe,
        instruction_lifecycle: Literal["active", "candidate"],
        run: Callable[[], dict[str, object]],
    ) -> dict[str, object]:
        key: dict[str, object] = {
            "schema_version": _RUN_CHECKPOINT_SCHEMA_VERSION,
            "context_digest": self._context_digest,
            "slot": slot,
            "probe": dataclasses.asdict(probe),
            "instruction_lifecycle": instruction_lifecycle,
        }
        key_digest = digest_object(key)
        path = self._directory / f"run_{key_digest}.json"
        cache_hit = path.is_file()
        if cache_hit:
            checkpoint = _json_object(path)
            if (
                checkpoint.get("schema_version")
                != _RUN_CHECKPOINT_SCHEMA_VERSION
                or not _content_digest_valid(
                    checkpoint,
                    _RUN_CHECKPOINT_DIGEST_PREFIX,
                )
                or checkpoint.get("key") != key
            ):
                raise ValueError(
                    "DIRECTIONAL_SETTLE_RUN_CHECKPOINT_INVALID:"
                    + path.name
                )
            compact = checkpoint.get("compact_run")
            if not isinstance(compact, dict):
                raise TypeError(
                    "directional-settle checkpoint compact run invalid"
                )
            expected_digest = checkpoint.get("compact_run_digest")
            if expected_digest != digest_object(compact):
                raise ValueError(
                    "DIRECTIONAL_SETTLE_RUN_CHECKPOINT_RESULT_INVALID:"
                    + path.name
                )
            self._hits += 1
            result = dict(compact)
        else:
            result = run()
            body: dict[str, object] = {
                "schema_version": _RUN_CHECKPOINT_SCHEMA_VERSION,
                "key": key,
                "compact_run": result,
                "compact_run_digest": digest_object(result),
            }
            checkpoint = {
                **body,
                "content_digest": _RUN_CHECKPOINT_DIGEST_PREFIX
                + digest_object(body),
            }
            _atomic_write_bytes(path, _json_bytes(checkpoint))
            self._misses += 1
        self._records.append(
            {
                "slot": slot,
                "filename": path.name,
                "sha256": _file_digest(path),
                "cache_hit": cache_hit,
            }
        )
        return result

    def summary(self) -> dict[str, object]:
        return {
            "schema_version": _RUN_CHECKPOINT_SCHEMA_VERSION,
            "context_digest": self._context_digest,
            "cache_hits": self._hits,
            "cache_misses": self._misses,
            "records": list(self._records),
        }


def _execute_probe(
    *,
    environments_dir: Path,
    probe: P10DirectionalSettleProbe,
    instruction_lifecycle: Literal["active", "candidate"],
    runner: _RunFunction,
    authority: HDSPUpdateAuthority | None = None,
    decision: PUpdateDecision | None = None,
    candidate: CandidatePBundle | None = None,
    checkpoint_store: _RunCheckpointStore | None = None,
    checkpoint_slot: str = "",
) -> dict[str, object]:
    def run() -> dict[str, object]:
        result = runner(
            environments_dir=environments_dir,
            requested_games=[probe.environment_selector],
            max_actions=probe.max_actions,
            instruction_variant="hybrid",
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

    if checkpoint_store is None:
        return run()
    if not checkpoint_slot:
        raise ValueError(
            "DIRECTIONAL_SETTLE_CHECKPOINT_SLOT_MISSING"
        )
    return checkpoint_store.execute(
        slot=checkpoint_slot,
        probe=probe,
        instruction_lifecycle=instruction_lifecycle,
        run=run,
    )


def _run_twice(
    *,
    environments_dir: Path,
    probes: tuple[P10DirectionalSettleProbe, ...],
    instruction_lifecycle: Literal["active", "candidate"],
    runner: _RunFunction,
    authority: HDSPUpdateAuthority | None = None,
    decision: PUpdateDecision | None = None,
    candidate: CandidatePBundle | None = None,
    checkpoint_store: _RunCheckpointStore | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    def once(repetition: str) -> list[dict[str, object]]:
        return [
            _execute_probe(
                environments_dir=environments_dir,
                probe=probe,
                instruction_lifecycle=instruction_lifecycle,
                runner=runner,
                authority=authority,
                decision=decision,
                candidate=candidate,
                checkpoint_store=checkpoint_store,
                checkpoint_slot=(
                    f"{instruction_lifecycle}-{repetition}-{index}"
                ),
            )
            for index, probe in enumerate(probes)
        ]

    return once("first"), once("second")


def _integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    return value


def _evaluate_runs(
    *,
    probes: tuple[P10DirectionalSettleProbe, ...],
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
        raise ValueError(
            "DIRECTIONAL_SETTLE_INTERVENTION_RUN_COUNT_MISMATCH"
        )
    stable_indices = tuple(
        index
        for index, probe in enumerate(probes)
        if probe.cohort == "stable"
    )
    target_indices = tuple(
        index
        for index, probe in enumerate(probes)
        if probe.cohort == "target"
    )

    def completed(run: Mapping[str, object]) -> int:
        return _integer(run.get("completed_levels"), "completed levels")

    def errors(run: Mapping[str, object]) -> int:
        return _integer(run.get("error_count"), "error count")

    active_reproducible = active_first == active_second
    candidate_reproducible = candidate_first == candidate_second
    active_errors_zero = all(errors(run) == 0 for run in active_first)
    candidate_errors_zero = all(
        errors(run) == 0 for run in candidate_first
    )
    stable_non_regression = all(
        completed(candidate_first[index])
        >= completed(active_first[index])
        and errors(candidate_first[index]) == 0
        and (
            not bool(active_first[index]["all_complete"])
            or bool(candidate_first[index]["all_complete"])
        )
        for index in stable_indices
    )
    baseline_target = sum(
        completed(active_first[index]) for index in target_indices
    )
    candidate_target = sum(
        completed(candidate_first[index]) for index in target_indices
    )
    baseline_stable = sum(
        completed(active_first[index]) for index in stable_indices
    )
    candidate_stable = sum(
        completed(candidate_first[index]) for index in stable_indices
    )
    target_improved = candidate_target > baseline_target
    bounded_positive = all(
        (
            active_reproducible,
            candidate_reproducible,
            active_errors_zero,
            candidate_errors_zero,
            stable_non_regression,
            target_improved,
            active_manifest_unchanged,
        )
    )
    return {
        "baseline_target_completed": baseline_target,
        "candidate_target_completed": candidate_target,
        "target_completion_delta": candidate_target - baseline_target,
        "target_improved": target_improved,
        "baseline_stable_completed": baseline_stable,
        "candidate_stable_completed": candidate_stable,
        "stable_completion_delta": candidate_stable - baseline_stable,
        "stable_non_regression": stable_non_regression,
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


def execute_p10_directional_settle_candidate_workflow(
    *,
    environments_dir: Path,
    bundle_dir: Path,
    composition_audit_path: Path,
    output_path: Path,
    probes: tuple[P10DirectionalSettleProbe, ...],
    maximum_transition_observations: int = 8,
    checkpoint_dir: Path | None = None,
    runner: _RunFunction = run_p10_offline_samples,
) -> dict[str, object]:
    """Compile and probe candidate hybrid; never promote active P."""

    failures = [
        failure
        for probe in probes
        for failure in probe.validate()
    ]
    selectors = tuple(probe.environment_selector for probe in probes)
    cohorts = {probe.cohort for probe in probes}
    if len(set(selectors)) != len(selectors):
        failures.append(
            "DIRECTIONAL_SETTLE_PROBE_SELECTOR_DUPLICATED"
        )
    if not {"stable", "target"}.issubset(cohorts):
        failures.append(
            "DIRECTIONAL_SETTLE_PROBE_COHORT_COVERAGE_INCOMPLETE"
        )
    if (
        isinstance(maximum_transition_observations, bool)
        or not 1 <= maximum_transition_observations <= 64
    ):
        failures.append(
            "DIRECTIONAL_SETTLE_OBSERVATION_LIMIT_INVALID"
        )
    if failures:
        raise ValueError(";".join(sorted(set(failures))))

    environments_dir = environments_dir.resolve()
    bundle_dir = bundle_dir.resolve()
    if checkpoint_dir is not None:
        checkpoint_dir = checkpoint_dir.resolve()
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
    candidate_body_path = (
        bundle_dir / P10_DIRECTIONAL_SETTLE_HYBRID_FILENAME
    )
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

    proposal, evidence = _proposal_and_evidence(
        active_manifest=active_manifest,
        active_manifest_digest=active_manifest_digest,
        composition_audit=composition_audit,
        composition_digest=composition_digest,
    )
    (
        prior_candidate_manifest,
        prior_candidate_body,
        transaction_path,
    ) = _slot_transaction(
        checkpoint_dir=checkpoint_dir,
        active_manifest_digest=active_manifest_digest,
        composition_digest=composition_digest,
        candidate_manifest_path=candidate_manifest_path,
        candidate_body_path=candidate_body_path,
    )
    archive_dir = output_path.parent / (
        "directional_settle_candidate_archive"
    )
    candidate_slot_retained = False
    try:
        authority, compile_decision, compile_directive = (
            _compile_authorization(proposal, evidence)
        )
        candidate_manifest = (
            compile_p10_directional_settle_hybrid_candidate(
                base_bundle_dir=bundle_dir,
                output_dir=bundle_dir,
                compile_directive=compile_directive,
                compile_decision=compile_decision,
                hds_authority=authority,
                composition_audit_digest=composition_digest,
                maximum_transition_observations=(
                    maximum_transition_observations
                ),
            )
        )
        with tempfile.TemporaryDirectory() as temporary:
            rebuild_dir = Path(temporary)
            rebuild_authority, rebuild_decision, rebuild_directive = (
                _compile_authorization(proposal, evidence)
            )
            rebuilt_manifest = (
                compile_p10_directional_settle_hybrid_candidate(
                    base_bundle_dir=bundle_dir,
                    output_dir=rebuild_dir,
                    compile_directive=rebuild_directive,
                    compile_decision=rebuild_decision,
                    hds_authority=rebuild_authority,
                    composition_audit_digest=composition_digest,
                    maximum_transition_observations=(
                        maximum_transition_observations
                    ),
                )
            )
            if rebuilt_manifest != candidate_manifest:
                raise RuntimeError(
                    "DIRECTIONAL_SETTLE_CANDIDATE_MANIFEST_REBUILD_MISMATCH"
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
                        "DIRECTIONAL_SETTLE_CANDIDATE_BYTE_REBUILD_MISMATCH:"
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
            maximum_transition_observations=(
                maximum_transition_observations
            ),
        )
        checkpoint_context_digest = digest_object(
            {
                "schema_version": (
                    P10_DIRECTIONAL_SETTLE_CANDIDATE_WORKFLOW_SCHEMA_VERSION
                ),
                "active_manifest_digest": active_manifest_digest,
                "composition_digest": composition_digest,
                "candidate_digest": candidate.digest,
                "probe_specs": [
                    dataclasses.asdict(probe) for probe in probes
                ],
                "maximum_transition_observations": (
                    maximum_transition_observations
                ),
            }
        )
        checkpoint_store = (
            _RunCheckpointStore(
                checkpoint_dir / "runs",
                context_digest=checkpoint_context_digest,
            )
            if checkpoint_dir is not None
            else None
        )
        clear_p10_instruction_body_caches()
        probe_decision = authority.decide(
            proposal,
            status="PROBE",
            reason_codes=(
                "candidate-isolated-from-active-manifest",
                "same-condition-active-removal-control",
                "stable-and-target-double-run",
            ),
            candidate_bundle=candidate,
        )
        active_first, active_second = _run_twice(
            environments_dir=environments_dir,
            probes=probes,
            instruction_lifecycle="active",
            runner=runner,
            checkpoint_store=checkpoint_store,
        )
        candidate_first, candidate_second = _run_twice(
            environments_dir=environments_dir,
            probes=probes,
            instruction_lifecycle="candidate",
            runner=runner,
            authority=authority,
            decision=probe_decision,
            candidate=candidate,
            checkpoint_store=checkpoint_store,
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
                    "failed-evaluation-check-"
                    + key.replace("_", "-")
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
            archive_dir / P10_DIRECTIONAL_SETTLE_HYBRID_FILENAME
        )
        archived_manifest_path = archive_dir / (
            "p10_candidate_manifest_directional_settle_v1.json"
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
                P10_DIRECTIONAL_SETTLE_CANDIDATE_WORKFLOW_SCHEMA_VERSION
            ),
            "artifact_type": (
                "arc3_p10_directional_settle_candidate_intervention"
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
                P10_DIRECTIONAL_SETTLE_COMPILER_VERSION
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
            "probe_specs": [
                dataclasses.asdict(probe) for probe in probes
            ],
            "removal_control": {
                "active_transition_observation_limit": 0,
                "candidate_transition_observation_limit": (
                    maximum_transition_observations
                ),
                "active_manifest_unchanged": (
                    active_manifest_unchanged
                ),
            },
            "runs": {
                "active_first": active_first,
                "active_second": active_second,
                "candidate_first": candidate_first,
                "candidate_second": candidate_second,
            },
            "run_checkpoints": (
                checkpoint_store.summary()
                if checkpoint_store is not None
                else {
                    "schema_version": (
                        _RUN_CHECKPOINT_SCHEMA_VERSION
                    ),
                    "enabled": False,
                }
            ),
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
        if transaction_path is not None:
            transaction_path.unlink(missing_ok=True)
        return result
    except Exception:
        _restore_candidate_slot(
            candidate_manifest_path=candidate_manifest_path,
            candidate_body_path=candidate_body_path,
            prior_manifest=prior_candidate_manifest,
            prior_body=prior_candidate_body,
        )
        if transaction_path is not None:
            transaction_path.unlink(missing_ok=True)
        raise


def _parse_probe(
    value: str,
    cohort: _ProbeCohort,
) -> P10DirectionalSettleProbe:
    selector, separator, raw_budget = value.rpartition(":")
    if not separator:
        raise argparse.ArgumentTypeError(
            "probe must be ENVIRONMENT_SELECTOR:MAX_ACTIONS"
        )
    try:
        budget = int(raw_budget)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "probe action budget invalid"
        ) from error
    return P10DirectionalSettleProbe(selector, cohort, budget)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compile and probe the bounded directional-settle candidate "
            "hybrid without promotion."
        )
    )
    parser.add_argument("--environments-dir", type=Path, required=True)
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--composition-audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--checkpoint-dir", type=Path)
    parser.add_argument("--stable", action="append", default=[])
    parser.add_argument("--target", action="append", default=[])
    parser.add_argument(
        "--maximum-transition-observations",
        type=int,
        default=8,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    probes = tuple(
        _parse_probe(value, "stable") for value in args.stable
    ) + tuple(_parse_probe(value, "target") for value in args.target)
    output = execute_p10_directional_settle_candidate_workflow(
        environments_dir=args.environments_dir,
        bundle_dir=args.bundle_dir,
        composition_audit_path=args.composition_audit,
        output_path=args.output,
        probes=probes,
        maximum_transition_observations=(
            args.maximum_transition_observations
        ),
        checkpoint_dir=args.checkpoint_dir,
    )
    print(output["content_digest"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "P10DirectionalSettleProbe",
    "P10_DIRECTIONAL_SETTLE_CANDIDATE_WORKFLOW_SCHEMA_VERSION",
    "execute_p10_directional_settle_candidate_workflow",
    "main",
]
