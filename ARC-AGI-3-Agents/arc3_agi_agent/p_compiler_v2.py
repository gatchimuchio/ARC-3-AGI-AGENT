"""Deterministic symbolic, parametric, and hybrid compiler for PBundle v1."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Final, Sequence

from .compiled_policy import CompiledAutonomousInstructionBody
from .generic_compute import (
    GenericInstructionBody,
    HybridRelationalInstructionBody,
    ParametricRelationalInstructionBody,
    SymbolicRelationalInstructionBody,
)
from .generic_memory import SemanticRecord
from .identity_boundary import IdentityBoundary
from .p_bundle import (
    P_BUNDLE_SCHEMA_VERSION,
    P_COMPILER_SEMANTICS_VERSION,
    PBundle,
    PBundleManifest,
    PCompilerReport,
    bind_program_parameters,
    instruction_body_from_artifact,
    instruction_body_manifest,
    instruction_body_tensors,
)
from .p_ir import compatibility_p_ir_program, p_ir_program_logical_digest
from .p_ir_types import PIRProgram
from .schema import digest_object

P_COMPILER_V2_VERSION: Final = "arc3-p-compiler-v2"
P_COMPILER_MODES: Final = frozenset(
    {"BOOTSTRAP", "SYMBOLIC", "PARAMETRIC", "HYBRID", "PRODUCT"}
)
P_COMPILER_TARGETS: Final = (
    "candidate_scoring",
    "composition",
    "exploration_probe",
    "goal_hazard",
    "object_relation_schema",
    "preconditions",
    "representation",
    "state_variables",
    "transition_effect_delay",
    "uncertainty",
)
_IDENTITY_VALUE = re.compile(
    r"(?i)(?:^|[^a-z0-9])(?:game|task|level)[-_ ]?(?:id|\d+)"
)


@dataclass(frozen=True, slots=True)
class EvidenceSelectionManifest:
    manifest_id: str
    dataset_role: str
    parent_p_logical_digest: str
    selected_record_ids: tuple[str, ...]
    selected_record_digests: tuple[str, ...]
    selected_ledger_event_digests: tuple[str, ...]
    selection_predicate: str
    excluded_roles: tuple[str, ...] = (
        "CV_HOLDOUT",
        "LOCKED_FINAL",
        "OFFICIAL_PRIVATE",
        "OFFICIAL_PUBLIC",
    )

    def digest(self) -> str:
        return "p-evidence-selection:" + digest_object(self)

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not self.manifest_id or not self.parent_p_logical_digest:
            failures.append("P_COMPILER_EVIDENCE_MANIFEST_METADATA_MISSING")
        if self.dataset_role != "DEVELOPMENT_TRAIN":
            failures.append("P_COMPILER_DATASET_ROLE_FORBIDDEN")
        if (
            not self.selected_record_ids
            or self.selected_record_ids
            != tuple(sorted(set(self.selected_record_ids)))
        ):
            failures.append("P_COMPILER_RECORD_IDS_INVALID")
        if (
            len(self.selected_record_digests)
            != len(self.selected_record_ids)
            or self.selected_record_digests
            != tuple(sorted(set(self.selected_record_digests)))
        ):
            failures.append("P_COMPILER_RECORD_DIGESTS_INVALID")
        if self.selected_ledger_event_digests != tuple(
            sorted(set(self.selected_ledger_event_digests))
        ):
            failures.append("P_COMPILER_LEDGER_DIGESTS_INVALID")
        if not self.selection_predicate:
            failures.append("P_COMPILER_SELECTION_PREDICATE_MISSING")
        if "LOCKED_FINAL" not in self.excluded_roles:
            failures.append("P_COMPILER_LOCKED_FINAL_EXCLUSION_MISSING")
        return tuple(sorted(set(failures)))


def evidence_selection_manifest(
    *,
    parent: PBundle,
    records: Sequence[SemanticRecord],
    ledger_event_digests: Sequence[str] = (),
    manifest_id: str = "p-evidence-selection-v1",
) -> EvidenceSelectionManifest:
    ordered = tuple(sorted(records, key=lambda item: item.memory_id))
    return EvidenceSelectionManifest(
        manifest_id=manifest_id,
        dataset_role="DEVELOPMENT_TRAIN",
        parent_p_logical_digest=parent.logical_digest(),
        selected_record_ids=tuple(item.memory_id for item in ordered),
        selected_record_digests=tuple(
            sorted(item.citation().content_digest for item in ordered)
        ),
        selected_ledger_event_digests=tuple(
            sorted(set(ledger_event_digests))
        ),
        selection_predicate=(
            "typed causal/procedure records with explicit falsifier and "
            "development-train provenance"
        ),
    )


def _record_taint_findings(
    records: Sequence[SemanticRecord],
) -> tuple[str, ...]:
    boundary = IdentityBoundary()
    failures = list(boundary.inspect_decision_context(tuple(records)))
    for record in records:
        for field_name, value in (
            ("statement", record.statement),
            ("semantic_tokens", record.semantic_tokens),
            ("relations", record.relations),
            ("evidence", record.evidence),
            ("scope", record.scope),
            ("payload", record.payload()),
        ):
            if _IDENTITY_VALUE.search(str(value)):
                failures.append(
                    f"{record.memory_id}:{field_name}:IDENTITY_VALUE"
                )
    return tuple(sorted(set(failures)))


def _evidence_biases(
    records: Sequence[SemanticRecord],
) -> dict[str, float]:
    totals: dict[str, tuple[int, int, int]] = {}
    for record in records:
        semantic_key = next(
            (
                item
                for item in record.semantic_tokens
                if item.startswith("surface:")
            ),
            None,
        )
        if semantic_key is None:
            continue
        payload = record.payload()

        def count(name: str) -> int:
            value = payload.get(name, 0)
            if isinstance(value, int) and not isinstance(value, bool):
                return max(0, value)
            return 0

        support = count("support_count") or count("success_count")
        contradiction = count("contradiction_count")
        hazard = count("hazard_count")
        prior = totals.get(semantic_key, (0, 0, 0))
        totals[semantic_key] = (
            prior[0] + support,
            prior[1] + contradiction,
            prior[2] + hazard,
        )
    return {
        key: max(
            -2.0,
            min(
                2.0,
                (support - contradiction - 2 * hazard)
                / max(1, support + contradiction + hazard),
            ),
        )
        for key, (support, contradiction, hazard) in sorted(totals.items())
    }


def _base_parametric(body: GenericInstructionBody) -> ParametricRelationalInstructionBody:
    if isinstance(body, ParametricRelationalInstructionBody):
        return body
    if isinstance(body, HybridRelationalInstructionBody):
        return body.parametric
    return ParametricRelationalInstructionBody()


def _body_for_mode(
    *,
    mode: str,
    parent: PBundle,
    records: Sequence[SemanticRecord],
    target_version: str,
    evidence_digest: str,
) -> GenericInstructionBody:
    provenance = (
        f"{P_COMPILER_V2_VERSION}:development-train:{evidence_digest}"
    )
    if mode == "SYMBOLIC":
        return SymbolicRelationalInstructionBody(
            version=target_version,
            provenance=provenance,
        )
    parametric = _base_parametric(parent.body).with_action_bias(
        version=target_version,
        action_bias=_evidence_biases(records),
        provenance=provenance,
    )
    if mode == "PARAMETRIC":
        return parametric
    if mode == "HYBRID":
        return HybridRelationalInstructionBody(
            symbolic=SymbolicRelationalInstructionBody(
                version=target_version,
                provenance=provenance + ":symbolic",
            ),
            parametric=parametric,
            version=target_version,
        )
    raise ValueError("P_COMPILER_MODE_INVALID")


def _projection_for_records(records: Sequence[SemanticRecord]) -> str:
    tokens = {
        token.casefold()
        for record in records
        for token in (*record.semantic_tokens, *record.relations)
    }
    if any("shape:" in token for token in tokens):
        return "shape-centric"
    return "spatial-relational"


@dataclass(frozen=True, slots=True)
class PCompilerV2:
    compiler_version: str = P_COMPILER_V2_VERSION

    def bootstrap(
        self,
        *,
        body: GenericInstructionBody,
        program: PIRProgram | None = None,
        version: str = "p-bootstrap-v1",
    ) -> PBundle:
        selected_program = program or compatibility_p_ir_program()
        return self._build_bundle(
            mode="BOOTSTRAP",
            parent_digest="NONE",
            evidence_digest="p-evidence-selection:BOOTSTRAP_NONE",
            selected_evidence_count=0,
            target_version=version,
            body=body,
            program=selected_program,
            lifecycle="ACTIVE",
        )

    def _require_inputs(
        self,
        *,
        parent: PBundle,
        records: Sequence[SemanticRecord],
        manifest: EvidenceSelectionManifest,
        target_version: str,
    ) -> tuple[SemanticRecord, ...]:
        parent_failures = parent.validate()
        if parent_failures:
            raise ValueError(";".join(parent_failures))
        if parent.manifest.lifecycle != "ACTIVE":
            raise ValueError("P_COMPILER_ACTIVE_PARENT_REQUIRED")
        if not target_version or target_version == parent.manifest.version:
            raise ValueError("P_COMPILER_TARGET_VERSION_INVALID")
        manifest_failures = manifest.validate()
        if manifest_failures:
            raise ValueError(";".join(manifest_failures))
        ordered = tuple(sorted(records, key=lambda item: item.memory_id))
        if manifest.parent_p_logical_digest != parent.logical_digest():
            raise PermissionError("P_COMPILER_PARENT_BINDING_INVALID")
        if manifest.selected_record_ids != tuple(
            item.memory_id for item in ordered
        ):
            raise PermissionError("P_COMPILER_EVIDENCE_IDS_INCOMPLETE")
        if manifest.selected_record_digests != tuple(
            sorted(item.citation().content_digest for item in ordered)
        ):
            raise PermissionError("P_COMPILER_EVIDENCE_DIGESTS_INCOMPLETE")
        if not ordered:
            raise ValueError("P_COMPILER_EVIDENCE_REQUIRED")
        for record in ordered:
            failures = record.validate()
            if failures:
                raise ValueError(";".join(failures))
            if record.state not in {"ACTIVE", "PROBATION"}:
                raise ValueError("P_COMPILER_EVIDENCE_STATE_FORBIDDEN")
        taint = _record_taint_findings(ordered)
        if taint:
            raise PermissionError(
                "P_COMPILER_IDENTITY_TAINT:" + ",".join(taint)
            )
        return ordered

    def _build_bundle(
        self,
        *,
        mode: str,
        parent_digest: str,
        evidence_digest: str,
        selected_evidence_count: int,
        target_version: str,
        body: GenericInstructionBody,
        program: PIRProgram,
        lifecycle: str,
    ) -> PBundle:
        if mode not in P_COMPILER_MODES:
            raise ValueError("P_COMPILER_MODE_INVALID")
        tensors = instruction_body_tensors(body)
        body_manifest = instruction_body_manifest(body)
        canonical_body = instruction_body_from_artifact(
            body_manifest,
            tensors,
        )
        bound_program = bind_program_parameters(
            program,
            body_manifest=body_manifest,
            tensors=tensors,
        )
        program_digest = p_ir_program_logical_digest(bound_program)
        compiler_report = PCompilerReport(
            compiler_version=self.compiler_version,
            mode=mode,
            selected_evidence_count=selected_evidence_count,
            evidence_selection_digest=evidence_digest,
            compiled_targets=P_COMPILER_TARGETS,
            taint_finding_count=0,
            resource_failures=(),
            deterministic=True,
        )
        manifest = PBundleManifest(
            schema_version=P_BUNDLE_SCHEMA_VERSION,
            bundle_id="p-bundle:"
            + digest_object(
                {
                    "mode": mode,
                    "version": target_version,
                    "parent": parent_digest,
                    "program": program_digest,
                    "tensors": tuple(
                        item.logical_digest() for item in tensors
                    ),
                }
            )[:32],
            version=target_version,
            lifecycle=lifecycle,
            compiler_semantics_version=P_COMPILER_SEMANTICS_VERSION,
            parent_logical_digest=parent_digest,
            evidence_selection_digest=evidence_digest,
            l0_abi_version=bound_program.l0_abi_version,
            program_logical_digest=program_digest,
            body_manifest=instruction_body_manifest(canonical_body),
            body_digest=canonical_body.digest(),
            identity_free=True,
        )
        bundle = PBundle(
            manifest=manifest,
            program=bound_program,
            body=canonical_body,
            tensors=tensors,
            compiler_report=compiler_report,
        )
        failures = bundle.validate()
        if failures:
            raise ValueError(";".join(failures))
        return bundle

    def compile(
        self,
        *,
        mode: str,
        parent: PBundle,
        records: Sequence[SemanticRecord],
        evidence_manifest: EvidenceSelectionManifest,
        target_version: str,
    ) -> PBundle:
        if mode not in {"SYMBOLIC", "PARAMETRIC", "HYBRID"}:
            raise ValueError("P_COMPILER_MODE_INVALID")
        ordered = self._require_inputs(
            parent=parent,
            records=records,
            manifest=evidence_manifest,
            target_version=target_version,
        )
        evidence_digest = evidence_manifest.digest()
        body = _body_for_mode(
            mode=mode,
            parent=parent,
            records=ordered,
            target_version=target_version,
            evidence_digest=evidence_digest,
        )
        projection_mode = _projection_for_records(ordered)
        program = compatibility_p_ir_program(
            projection_mode=projection_mode
        )
        program = replace(
            program,
            program_id=(
                "compiled."
                + mode.casefold()
                + "."
                + digest_object((target_version, evidence_digest))[:20]
            ),
            provenance=replace(
                program.provenance,
                source_digests=tuple(
                    sorted(
                        {
                            *program.provenance.source_digests,
                            evidence_digest,
                        }
                    )
                ),
                evidence_manifest_digest=evidence_digest,
            ),
        )
        candidate = self._build_bundle(
            mode=mode,
            parent_digest=parent.logical_digest(),
            evidence_digest=evidence_digest,
            selected_evidence_count=len(ordered),
            target_version=target_version,
            body=body,
            program=program,
            lifecycle="CANDIDATE",
        )
        if candidate.logical_digest() == parent.logical_digest():
            raise RuntimeError("P_COMPILER_CANDIDATE_NOT_ISOLATED")
        return candidate

    def compile_product(
        self,
        *,
        body: CompiledAutonomousInstructionBody,
        program: PIRProgram,
        evidence_digest: str,
        selected_evidence_count: int,
        target_version: str,
    ) -> PBundle:
        """Seal a precompiled identity-free body into the product P bundle."""

        if (
            not evidence_digest
            or isinstance(selected_evidence_count, bool)
            or not isinstance(selected_evidence_count, int)
            or selected_evidence_count <= 0
        ):
            raise ValueError("P_COMPILER_PRODUCT_EVIDENCE_INVALID")
        if not target_version:
            raise ValueError("P_COMPILER_TARGET_VERSION_INVALID")
        if "compatibility" in program.program_id.casefold():
            raise PermissionError("P_COMPILER_PRODUCT_COMPATIBILITY_FORBIDDEN")
        if program.provenance.evidence_manifest_digest != evidence_digest:
            raise PermissionError("P_COMPILER_PRODUCT_EVIDENCE_BINDING_INVALID")
        if body.validate():
            raise ValueError("P_COMPILER_PRODUCT_BODY_INVALID")
        return self._build_bundle(
            mode="PRODUCT",
            parent_digest="NONE",
            evidence_digest=evidence_digest,
            selected_evidence_count=selected_evidence_count,
            target_version=target_version,
            body=body,
            program=program,
            lifecycle="ACTIVE",
        )

    def compile_symbolic(
        self,
        **kwargs: object,
    ) -> PBundle:
        return self.compile(mode="SYMBOLIC", **kwargs)  # type: ignore[arg-type]

    def compile_parametric(
        self,
        **kwargs: object,
    ) -> PBundle:
        return self.compile(mode="PARAMETRIC", **kwargs)  # type: ignore[arg-type]

    def compile_hybrid(
        self,
        **kwargs: object,
    ) -> PBundle:
        return self.compile(mode="HYBRID", **kwargs)  # type: ignore[arg-type]


__all__ = [
    "P_COMPILER_MODES",
    "P_COMPILER_TARGETS",
    "P_COMPILER_V2_VERSION",
    "EvidenceSelectionManifest",
    "PCompilerV2",
    "evidence_selection_manifest",
]
