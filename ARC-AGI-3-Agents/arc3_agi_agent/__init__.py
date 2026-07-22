"""ARC-3 restart foundation: contracts, IR, schema, and verification."""

from .checkpoint import Checkpoint, CheckpointManager
from .ir import (
    CandidateIR,
    ClosureIR,
    CompiledRecord,
    EntityIR,
    HypothesisIR,
    KnowledgeIndexEntry,
    MechanicRuleIR,
    ObservationIR,
    ProofObligationIR,
    TransitionIR,
)
from .protocol import (
    DEFAULT_INSTRUCTION_BODY_CONTRACT,
    EmissionDirective,
    ComputeRequest,
    ComputeResult,
    HDSDecision,
    InstructionBodyContract,
    MemoryDirective,
    TrinityLifecycle,
)
from .schema import (
    SCHEMA_VERSION,
    canonical_json,
    digest_object,
    record_from_dict,
    record_to_dict,
    validate_record,
    validate_runtime_bundle,
)
from .verification import (
    RenderedObservation,
    VerificationResult,
    verify_rendered_transition,
)

__all__ = [
    "CandidateIR",
    "Checkpoint",
    "CheckpointManager",
    "ClosureIR",
    "CompiledRecord",
    "ComputeRequest",
    "ComputeResult",
    "DEFAULT_INSTRUCTION_BODY_CONTRACT",
    "EmissionDirective",
    "EntityIR",
    "HDSDecision",
    "HypothesisIR",
    "InstructionBodyContract",
    "KnowledgeIndexEntry",
    "MechanicRuleIR",
    "MemoryDirective",
    "ObservationIR",
    "ProofObligationIR",
    "RenderedObservation",
    "SCHEMA_VERSION",
    "TransitionIR",
    "TrinityLifecycle",
    "VerificationResult",
    "canonical_json",
    "digest_object",
    "record_from_dict",
    "record_to_dict",
    "validate_record",
    "validate_runtime_bundle",
    "verify_rendered_transition",
]
