"""Compiled ARC3 product P/J0/M0 artifact construction and runtime loader."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Final

from .compiled_policy import (
    CompiledAutonomousInstructionBody,
    load_compiled_autonomous_instruction_body,
)
from .generic_hds import HDSConfiguration
from .generic_memory import SemanticRecord, semantic_record
from .identity_boundary import IdentityBoundary
from .initial_state_compiler import (
    InitialStateBundle,
    InitialStateCompiler,
    initial_state_from_package,
)
from .p_compiler_v2 import PCompilerV2
from .p_ir import product_capability_p_ir_program
from .schema import canonical_json, digest_object

PRODUCT_CAPABILITY_SCHEMA_VERSION: Final = "arc3-product-capability-v1"
PRODUCT_CAPABILITY_DESCRIPTOR_FILENAME: Final = (
    "arc3_product_initial_state_v1.json"
)
PRODUCT_CAPABILITY_PACKAGE_FILENAME: Final = (
    "arc3_product_initial_state_v1.zip"
)
PRODUCT_CAPABILITY_PROGRAM_ID: Final = "arc3.product.capability.v1"
PRODUCT_CAPABILITY_P_VERSION: Final = "arc3-product-p-v1"
PRODUCT_CAPABILITY_INITIAL_STATE_VERSION: Final = (
    "arc3-product-initial-state-v1"
)
PRODUCT_CAPABILITY_ADAPTER_DIGEST: Final = (
    "official-adapter:frame-data-raw-temporal-v2"
)


@dataclass(frozen=True, slots=True)
class ProductCompilationEvidence:
    """Development-only closure facts reduced to opaque product provenance."""

    source_digests: tuple[str, ...]
    source_artifact_count: int
    structural_record_count: int
    rendered_only_record_count: int
    action_primitive_count: int
    role_family_count: int
    fixed_action_dependency_count: int
    literal_coordinate_dependency_count: int
    identity_routing_dependency_count: int
    source_state_dependency_count: int

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if (
            not self.source_digests
            or self.source_digests != tuple(sorted(set(self.source_digests)))
            or any(not item.startswith("sha256:") for item in self.source_digests)
        ):
            failures.append("PRODUCT_COMPILATION_SOURCE_DIGEST_INVALID")
        if self.source_artifact_count != len(self.source_digests):
            failures.append("PRODUCT_COMPILATION_SOURCE_COUNT_MISMATCH")
        if self.structural_record_count != 183:
            failures.append("PRODUCT_COMPILATION_STRUCTURE_COVERAGE_INVALID")
        if self.rendered_only_record_count != self.structural_record_count:
            failures.append("PRODUCT_COMPILATION_RENDERED_COVERAGE_INVALID")
        if self.action_primitive_count < 8 or self.role_family_count < 7:
            failures.append("PRODUCT_COMPILATION_ONTOLOGY_COVERAGE_INVALID")
        if any(
            value != 0
            for value in (
                self.fixed_action_dependency_count,
                self.literal_coordinate_dependency_count,
                self.identity_routing_dependency_count,
                self.source_state_dependency_count,
            )
        ):
            failures.append("PRODUCT_COMPILATION_PRIVILEGE_DEPENDENCY_PRESENT")
        return tuple(sorted(set(failures)))

    def digest(self) -> str:
        failures = self.validate()
        if failures:
            raise ValueError(";".join(failures))
        return "product-capability-evidence:" + digest_object(self)


def product_hds_domain_profile(
    *,
    action_budget: int,
    no_progress_limit: int,
) -> HDSConfiguration:
    """Return the ARC3-specific J0 while preserving HDS as sole authority."""

    profile = HDSConfiguration(
        purpose="maximize_progress",
        value_criteria=(
            "action_completion_before_redecision",
            "delayed_effect_reobservation",
            "goal_progress",
            "no_effect_classification",
            "reversible_probe",
            "safe_level_rollback",
            "terminal_safety",
            "unresolved_next_question",
        ),
        risk_limit=0.45,
        evidence_mode="PROBE_WHEN_UNREPRODUCED",
        resource_budget=action_budget,
        stop_after_no_progress=no_progress_limit,
        max_hazard_for_execute=0,
    )
    failures = profile.validate()
    if failures:
        raise ValueError(";".join(failures))
    return profile


def _seed_record(
    *,
    memory_id: str,
    kind: str,
    statement: str,
    semantic_tokens: tuple[str, ...],
    falsification_condition: str,
    evidence: tuple[str, ...],
    payload: Mapping[str, object] | None = None,
) -> SemanticRecord:
    return semantic_record(
        memory_id=memory_id,
        kind=kind,
        statement=statement,
        semantic_tokens=semantic_tokens,
        evidence=evidence,
        scope=("ARC3_PRODUCT_DOMAIN", "SESSION_GLOBAL"),
        falsification_condition=falsification_condition,
        payload={
            "confidence_ppm": 1_000_000,
            "execute_eligibility": False,
            "support_count": 183,
            **(dict(payload) if payload is not None else {}),
        },
    )


def product_initial_memory(
    evidence: ProductCompilationEvidence,
) -> tuple[SemanticRecord, ...]:
    """Compile identity-free structural priors; never store answers or replay."""

    evidence_digest = evidence.digest()
    provenance = tuple(
        sorted((evidence_digest, *evidence.source_digests))
    )
    records = (
        _seed_record(
            memory_id="product-seed:temporal-observation",
            kind="WORLD_MODEL",
            statement=(
                "Treat each external cycle as temporal camera renders ending in "
                "an action-complete composite; attribute effects before replanning."
            ),
            semantic_tokens=(
                "action-complete:false",
                "action-complete:true",
                "action-frame-count:1",
                "action-frame-count:2",
                "action-frame-count:3",
                "action-frame-count:4",
                "animation-observed:false",
                "animation-observed:true",
            ),
            falsification_condition=(
                "an external action yields no ordered render sequence or final composite"
            ),
            evidence=provenance,
        ),
        _seed_record(
            memory_id="product-seed:action-surface",
            kind="PROCEDURE_CAPABILITY",
            statement=(
                "Enumerate only currently available discrete actions and bind any "
                "pointer payload to coordinates derived from the current composite."
            ),
            semantic_tokens=tuple(
                [f"action-count:{value}" for value in range(1, 8)]
                + ["payload-schema:6:x,y"]
            ),
            falsification_condition=(
                "a selected action is absent or a pointer payload is not current-render derived"
            ),
            evidence=provenance,
        ),
        _seed_record(
            memory_id="product-seed:role-relation",
            kind="RELATION_SCHEMA",
            statement=(
                "Normalize rendered components by size, shape, relative position, "
                "neighborhood, and relation before assigning interaction roles."
            ),
            semantic_tokens=(
                "area:large",
                "area:medium",
                "area:point",
                "area:small",
                "horizontal:high",
                "horizontal:low",
                "horizontal:middle",
                "vertical:high",
                "vertical:low",
                "vertical:middle",
            ),
            falsification_condition=(
                "role-normalized relations fail under palette or placement variation"
            ),
            evidence=provenance,
        ),
        _seed_record(
            memory_id="product-seed:mechanism-contrast",
            kind="WORLD_MODEL",
            statement=(
                "Maintain competing mechanism hypotheses and prefer an action whose "
                "predicted effect distinguishes them under a reversible boundary."
            ),
            semantic_tokens=(
                "boundary:reversible",
                "goal:progress",
                "value:information",
            ),
            falsification_condition=(
                "the selected probe cannot distinguish any active mechanism hypothesis"
            ),
            evidence=provenance,
        ),
        _seed_record(
            memory_id="product-seed:goal-progress",
            kind="GOAL_MODEL",
            statement=(
                "Use observed progress, stable relational change, and terminal success "
                "as goal evidence; visible change alone is not completion."
            ),
            semantic_tokens=(
                "goal:progress",
                "terminal:not_finished",
                "terminal:running",
                "terminal:win",
            ),
            falsification_condition=(
                "a claimed goal state lacks progress or terminal success evidence"
            ),
            evidence=provenance,
        ),
        _seed_record(
            memory_id="product-seed:hazard-boundary",
            kind="HAZARD_MODEL",
            statement=(
                "Treat terminal failure, repeated no-effect cycles, regression, and "
                "resource exhaustion as hazards requiring veto, replan, or rollback."
            ),
            semantic_tokens=(
                "current-signature-repeat-count:0",
                "current-signature-repeat-count:1",
                "current-signature-repeat-count:2",
                "terminal:game_over",
            ),
            falsification_condition=(
                "a repeated or terminally unsafe transition is executed as ordinary progress"
            ),
            evidence=provenance,
        ),
        _seed_record(
            memory_id="product-seed:ordered-composition",
            kind="TRANSITION_RULE",
            statement=(
                "Compose actions through observed state variables, verify each effect, "
                "and advance a subgoal only after its predicate is observed."
            ),
            semantic_tokens=tuple(
                [f"history-length:{value}" for value in range(17)]
                + ["goal:progress"]
            ),
            falsification_condition=(
                "a later action is emitted before the prior subgoal effect is observed"
            ),
            evidence=provenance,
        ),
        _seed_record(
            memory_id="product-seed:reset-recovery",
            kind="PROCEDURE_CAPABILITY",
            statement=(
                "Use the reset control only through HDS rollback authority, then clear "
                "local working state and reobserve before selecting a normal action."
            ),
            semantic_tokens=(
                "full-reset:false",
                "full-reset:true",
                "terminal:game_over",
            ),
            falsification_condition=(
                "reset bypasses HDS authority or normal action selection resumes before reobservation"
            ),
            evidence=provenance,
        ),
    )
    ordered = tuple(sorted(records, key=lambda item: item.memory_id))
    failures = tuple(
        failure for record in ordered for failure in record.validate()
    )
    if failures:
        raise ValueError(";".join(sorted(set(failures))))
    return ordered


def compile_product_initial_state(
    *,
    evidence: ProductCompilationEvidence,
    action_budget: int,
    no_progress_limit: int,
    body: CompiledAutonomousInstructionBody | None = None,
) -> InitialStateBundle:
    """Compile one canonical active P/J0/M0 product artifact."""

    evidence_digest = evidence.digest()
    selected_body = body or load_compiled_autonomous_instruction_body()
    program = product_capability_p_ir_program(
        source_digests=evidence.source_digests,
        evidence_manifest_digest=evidence_digest,
    )
    p_bundle = PCompilerV2().compile_product(
        body=selected_body,
        program=program,
        evidence_digest=evidence_digest,
        selected_evidence_count=evidence.structural_record_count,
        target_version=PRODUCT_CAPABILITY_P_VERSION,
    )
    return InitialStateCompiler(
        adapter_digest=PRODUCT_CAPABILITY_ADAPTER_DIGEST,
    ).compile(
        p_bundle=p_bundle,
        j0=product_hds_domain_profile(
            action_budget=action_budget,
            no_progress_limit=no_progress_limit,
        ),
        memory_records=product_initial_memory(evidence),
        version=PRODUCT_CAPABILITY_INITIAL_STATE_VERSION,
    )


def product_capability_descriptor(
    *,
    initial_state: InitialStateBundle,
    evidence: ProductCompilationEvidence,
    package_payload: bytes,
) -> dict[str, object]:
    """Describe the exact canonical package without embedding development data."""

    body: dict[str, object] = {
        "schema_version": PRODUCT_CAPABILITY_SCHEMA_VERSION,
        "product_bundle_id": "ARC3ProductBundle-v1",
        "package_filename": PRODUCT_CAPABILITY_PACKAGE_FILENAME,
        "package_sha256": hashlib.sha256(package_payload).hexdigest(),
        "package_size_bytes": len(package_payload),
        "initial_state_logical_digest": initial_state.logical_digest,
        "p_logical_digest": initial_state.p_bundle.logical_digest(),
        "p_program_logical_digest": (
            initial_state.p_bundle.manifest.program_logical_digest
        ),
        "p_program_id": initial_state.p_bundle.program.program_id,
        "p_body_digest": initial_state.p_bundle.body.digest(),
        "p_body_format": initial_state.p_bundle.body.format_id(),
        "p_body_version": initial_state.p_bundle.body.body_version(),
        "p_compiler_mode": initial_state.p_bundle.compiler_report.mode,
        "p_selected_evidence_count": (
            initial_state.p_bundle.compiler_report.selected_evidence_count
        ),
        "j0_digest": "j0:" + digest_object(initial_state.j0),
        "m0_digest": "m0:" + digest_object(initial_state.m0),
        "m0_record_count": len(initial_state.m0),
        "source_artifact_count": evidence.source_artifact_count,
        "source_evidence_digests": evidence.source_digests,
        "source_structure_count": evidence.structural_record_count,
        "rendered_only_structure_count": evidence.rendered_only_record_count,
        "contains_runtime_examples": False,
        "contains_fixed_trajectory": False,
        "contains_identity_router": False,
        "identity_free": True,
    }
    body["content_digest"] = (
        "product-capability-descriptor:" + digest_object(body)
    )
    return body


def _descriptor_body(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError("PRODUCT_CAPABILITY_DESCRIPTOR_INVALID")
    descriptor = {str(key): item for key, item in value.items()}
    expected = descriptor.pop("content_digest", None)
    actual = "product-capability-descriptor:" + digest_object(descriptor)
    if expected != actual:
        raise ValueError("PRODUCT_CAPABILITY_DESCRIPTOR_DIGEST_MISMATCH")
    descriptor["content_digest"] = expected
    return descriptor


def _load_product_initial_state(
    descriptor_path: Path,
    package_path: Path,
) -> InitialStateBundle:
    return load_product_initial_state_payloads(
        descriptor_payload=descriptor_path.read_bytes(),
        package_payload=package_path.read_bytes(),
    )


def load_product_initial_state_payloads(
    *,
    descriptor_payload: bytes,
    package_payload: bytes,
) -> InitialStateBundle:
    """Load the canonical product initial state from bound in-memory bytes."""

    descriptor = _descriptor_body(
        json.loads(descriptor_payload.decode("utf-8"))
    )
    if (
        descriptor.get("schema_version") != PRODUCT_CAPABILITY_SCHEMA_VERSION
        or descriptor.get("package_filename")
        != PRODUCT_CAPABILITY_PACKAGE_FILENAME
        or descriptor.get("p_program_id") != PRODUCT_CAPABILITY_PROGRAM_ID
        or descriptor.get("p_compiler_mode") != "PRODUCT"
        or descriptor.get("identity_free") is not True
        or descriptor.get("contains_runtime_examples") is not False
        or descriptor.get("contains_fixed_trajectory") is not False
        or descriptor.get("contains_identity_router") is not False
    ):
        raise ValueError("PRODUCT_CAPABILITY_DESCRIPTOR_CONTRACT_INVALID")
    if (
        descriptor.get("package_sha256")
        != hashlib.sha256(package_payload).hexdigest()
        or descriptor.get("package_size_bytes") != len(package_payload)
    ):
        raise ValueError("PRODUCT_CAPABILITY_PACKAGE_DIGEST_MISMATCH")
    initial_state = initial_state_from_package(package_payload)
    p_bundle = initial_state.p_bundle
    if (
        initial_state.logical_digest
        != descriptor.get("initial_state_logical_digest")
        or p_bundle.logical_digest() != descriptor.get("p_logical_digest")
        or p_bundle.manifest.program_logical_digest
        != descriptor.get("p_program_logical_digest")
        or p_bundle.body.digest() != descriptor.get("p_body_digest")
        or p_bundle.body.format_id() != descriptor.get("p_body_format")
        or p_bundle.body.body_version() != descriptor.get("p_body_version")
        or "j0:" + digest_object(initial_state.j0)
        != descriptor.get("j0_digest")
        or "m0:" + digest_object(initial_state.m0)
        != descriptor.get("m0_digest")
        or len(initial_state.m0) != descriptor.get("m0_record_count")
    ):
        raise ValueError("PRODUCT_CAPABILITY_COMPONENT_BINDING_MISMATCH")
    if not isinstance(p_bundle.body, CompiledAutonomousInstructionBody):
        raise TypeError("PRODUCT_CAPABILITY_COMPILED_BODY_REQUIRED")
    if (
        p_bundle.program.program_id != PRODUCT_CAPABILITY_PROGRAM_ID
        or "compatibility" in canonical_json(p_bundle.program).casefold()
        or p_bundle.compiler_report.mode != "PRODUCT"
    ):
        raise PermissionError("PRODUCT_CAPABILITY_COMPATIBILITY_PATH_ACTIVE")
    identity_failures = IdentityBoundary().inspect_decision_context(
        p_bundle.program,
        initial_state.j0,
        initial_state.m0,
    )
    if identity_failures:
        raise PermissionError(
            "PRODUCT_CAPABILITY_IDENTITY_BOUNDARY:" + ",".join(identity_failures)
        )
    return initial_state


def _default_bundle_directory() -> Path:
    return Path(__file__).resolve().parent / "bundles"


@lru_cache(maxsize=1)
def _load_default_product_initial_state() -> InitialStateBundle:
    directory = _default_bundle_directory()
    return _load_product_initial_state(
        directory / PRODUCT_CAPABILITY_DESCRIPTOR_FILENAME,
        directory / PRODUCT_CAPABILITY_PACKAGE_FILENAME,
    )


def load_product_initial_state(
    *,
    descriptor_path: Path | None = None,
    package_path: Path | None = None,
) -> InitialStateBundle:
    """Load and verify the one active product artifact before session creation."""

    if descriptor_path is None and package_path is None:
        return _load_default_product_initial_state()
    if descriptor_path is None or package_path is None:
        raise ValueError("PRODUCT_CAPABILITY_ARTIFACT_PAIR_REQUIRED")
    return _load_product_initial_state(descriptor_path, package_path)


__all__ = [
    "PRODUCT_CAPABILITY_ADAPTER_DIGEST",
    "PRODUCT_CAPABILITY_DESCRIPTOR_FILENAME",
    "PRODUCT_CAPABILITY_INITIAL_STATE_VERSION",
    "PRODUCT_CAPABILITY_PACKAGE_FILENAME",
    "PRODUCT_CAPABILITY_PROGRAM_ID",
    "PRODUCT_CAPABILITY_P_VERSION",
    "PRODUCT_CAPABILITY_SCHEMA_VERSION",
    "ProductCompilationEvidence",
    "compile_product_initial_state",
    "load_product_initial_state",
    "load_product_initial_state_payloads",
    "product_capability_descriptor",
    "product_hds_domain_profile",
    "product_initial_memory",
]
