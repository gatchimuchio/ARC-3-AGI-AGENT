"""Executable, versioned, identity-free instruction bodies for compute subject C."""

from __future__ import annotations

import copy
import functools
import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .context import ContextSnapshot
from .ir import ActionPredictionIR, HypothesisIR, ObservationIR
from .memory import MemorySnapshot
from .protocol import ComputeRequest, InstructionBodyContract
from .schema import digest_object, forbidden_runtime_paths

INSTRUCTION_BODY_SCHEMA_VERSION = "arc3-instruction-body-v1"
SYMBOLIC_FORMAT_ID = "symbolic-rule-graph"
PARAMETRIC_FORMAT_ID = "parametric-sigmoid-matrix"
INSTRUCTION_BODY_REMOVAL_WITNESS = (
    "INSTRUCTION_BODY_REMOVED_NO_EXECUTABLE_KNOWLEDGE_OR_TRANSFORM"
)

PARAMETRIC_FEATURES = (
    "bias",
    "action-id-scaled",
    "available-action-fraction",
    "entity-present",
    "relation-present",
    "visible-effect-present",
    "previous-observation-present",
    "action-history-fraction",
    "memory-entry-fraction",
    "failure-present",
    "active-terminal",
    "structural-present",
)
PARAMETRIC_HEADS = (
    "effect",
    "progress",
    "hazard",
    "information_gain",
    "candidate_prior",
    "uncertainty",
)

_CONTROL_MODES = frozenset({"REOBSERVE", "SUSPEND", "STOP", "ROLLBACK", "PLAN"})
_FORBIDDEN_VALUE_PATTERNS = (
    re.compile(r"(?i)(?:^|[^a-z0-9])[a-z]{1,3}\d{2}-[0-9a-f]{8}(?:$|[^a-z0-9])"),
    re.compile(r"(?i)(?:^|[^a-z0-9])(?:game|task|level)[-_ ]?(?:id|\d+)"),
    re.compile(r"(?i)(?:/mnt/|[a-z]:\\|environment_files/|\.json\b|\.py\b)"),
)


def _decimal_digest(value: object, *, length: int = 78) -> str:
    digits = str(int(digest_object(value), 16)).zfill(78)
    return digits[:length]


def _bounded(value: float) -> float:
    return round(min(1.0, max(0.0, float(value))), 6)


def _sigmoid(value: float) -> float:
    if value >= 0.0:
        exponential = math.exp(-min(value, 60.0))
        return 1.0 / (1.0 + exponential)
    exponential = math.exp(max(value, -60.0))
    return exponential / (1.0 + exponential)


def _runtime_value_failures(value: object, path: str = "$") -> tuple[str, ...]:
    failures = list(forbidden_runtime_paths(value))
    stack: list[tuple[str, object]] = [(path, value)]
    while stack:
        current_path, item = stack.pop()
        if isinstance(item, Mapping):
            stack.extend(
                (f"{current_path}.{key}", child)
                for key, child in item.items()
            )
        elif isinstance(item, Sequence) and not isinstance(
            item, (str, bytes, bytearray)
        ):
            stack.extend(
                (f"{current_path}[{index}]", child)
                for index, child in enumerate(item)
            )
        elif isinstance(item, str) and any(
            pattern.search(item) for pattern in _FORBIDDEN_VALUE_PATTERNS
        ):
            failures.append(current_path)
    return tuple(sorted(set(failures)))


def instruction_bundle_digest(value: Mapping[str, Any]) -> str:
    """Digest a bundle while treating both digest slots as blank."""

    normalized = copy.deepcopy(dict(value))
    normalized["content_digest"] = ""
    contract = normalized.get("contract")
    if isinstance(contract, dict):
        contract["content_digest"] = ""
    return "sha256-decimal:" + _decimal_digest(normalized)


def seal_instruction_bundle(value: Mapping[str, Any]) -> dict[str, Any]:
    """Return a detached mapping with content digest fields bound."""

    sealed = copy.deepcopy(dict(value))
    sealed["content_digest"] = ""
    contract = sealed.get("contract")
    if not isinstance(contract, dict):
        raise TypeError("instruction body contract must be an object")
    contract["content_digest"] = ""
    content_digest = instruction_bundle_digest(sealed)
    sealed["content_digest"] = content_digest
    contract["content_digest"] = content_digest
    return sealed


def _tuple_of_text(value: object, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(
        value, (str, bytes, bytearray)
    ):
        raise TypeError(f"{field_name} must be an array")
    output = tuple(str(item).strip() for item in value)
    if any(not item for item in output):
        raise ValueError(f"{field_name} contains an empty value")
    return output


def _mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be an object")
    return value


def _float(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field_name} must be finite")
    return result


def _int(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    return value


def _contract_from_mapping(value: object) -> InstructionBodyContract:
    data = _mapping(value, "contract")
    return InstructionBodyContract(
        version=str(data.get("version", "")),
        format_id=str(data.get("format_id", "")),
        schema_version=str(data.get("schema_version", "")),
        body_version=str(data.get("body_version", "")),
        content_digest=str(data.get("content_digest", "")),
        addressable=data.get("addressable") is True,
        state_dependent=data.get("state_dependent") is True,
        composable=data.get("composable") is True,
        executable_by_layer0=data.get("executable_by_layer0") is True,
        deterministic_under_fixed_state=(
            data.get("deterministic_under_fixed_state") is True
        ),
        runtime_identity_free=data.get("runtime_identity_free") is True,
        provenance_digest=str(data.get("provenance_digest", "")),
        input_contract=_tuple_of_text(
            data.get("input_contract"),
            "contract.input_contract",
        ),
        state_contract=_tuple_of_text(
            data.get("state_contract"),
            "contract.state_contract",
        ),
        output_contract=_tuple_of_text(
            data.get("output_contract"),
            "contract.output_contract",
        ),
        compile_contract=_tuple_of_text(
            data.get("compile_contract"),
            "contract.compile_contract",
        ),
        bound=data.get("bound") is True,
    )


@dataclass(frozen=True, slots=True)
class ControlInstruction:
    mode: str
    preconditions: tuple[str, ...]
    expected_progress: float
    information_gain: float
    expected_risk: float
    repetition_cost: float
    rollback_cost: float
    falsification_conditions: tuple[str, ...]
    provenance: tuple[str, ...]

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if self.mode not in _CONTROL_MODES:
            failures.append("CONTROL_MODE_INVALID")
        if not self.preconditions:
            failures.append("CONTROL_PRECONDITION_MISSING")
        if not self.falsification_conditions:
            failures.append("CONTROL_FALSIFIER_MISSING")
        if not self.provenance:
            failures.append("CONTROL_PROVENANCE_MISSING")
        for field_name, value in (
            ("PROGRESS", self.expected_progress),
            ("INFORMATION_GAIN", self.information_gain),
            ("RISK", self.expected_risk),
            ("REPETITION_COST", self.repetition_cost),
            ("ROLLBACK_COST", self.rollback_cost),
        ):
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                failures.append(f"CONTROL_{field_name}_OUT_OF_RANGE")
        return tuple(sorted(set(failures)))


@dataclass(frozen=True, slots=True)
class SemanticOperatorInstruction:
    """Addressable P material for one identity-free Layer-0 primitive."""

    operator_id: str
    action_id: int
    detector: str
    transform: str
    parameter_items: tuple[tuple[str, object], ...]
    preconditions: tuple[str, ...]
    falsification_conditions: tuple[str, ...]
    provenance: tuple[str, ...]

    def parameters(self) -> dict[str, object]:
        return dict(self.parameter_items)

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not self.operator_id:
            failures.append("SEMANTIC_OPERATOR_ID_MISSING")
        if not 1 <= self.action_id <= 7:
            failures.append("SEMANTIC_OPERATOR_ACTION_INVALID")
        if not self.detector:
            failures.append("SEMANTIC_OPERATOR_DETECTOR_MISSING")
        if not self.transform:
            failures.append("SEMANTIC_OPERATOR_TRANSFORM_MISSING")
        if len(self.parameters()) != len(self.parameter_items):
            failures.append("SEMANTIC_OPERATOR_PARAMETER_DUPLICATE")
        if any(not key for key, _value in self.parameter_items):
            failures.append("SEMANTIC_OPERATOR_PARAMETER_KEY_MISSING")
        if not self.preconditions:
            failures.append("SEMANTIC_OPERATOR_PRECONDITION_MISSING")
        if not self.falsification_conditions:
            failures.append("SEMANTIC_OPERATOR_FALSIFIER_MISSING")
        if not self.provenance:
            failures.append("SEMANTIC_OPERATOR_PROVENANCE_MISSING")
        runtime_identity_surface = {
            "operator_id": self.operator_id,
            "action_id": self.action_id,
            "detector": self.detector,
            "transform": self.transform,
            "parameters": self.parameters(),
            "preconditions": self.preconditions,
            "falsification_conditions": self.falsification_conditions,
            "provenance": self.provenance,
        }
        failures.extend(
            f"SEMANTIC_OPERATOR_RUNTIME_IDENTITY_FORBIDDEN:{path}"
            for path in _runtime_value_failures(runtime_identity_surface)
        )
        return tuple(sorted(set(failures)))


@dataclass(frozen=True, slots=True)
class InstructionQueryResult:
    body_format: str
    body_version: str
    body_digest: str
    query_digest: str
    representations: tuple[str, ...]
    retrieved_items: tuple[str, ...]
    hypotheses: tuple[HypothesisIR, ...]
    predictions: tuple[ActionPredictionIR, ...]
    controls: tuple[ControlInstruction, ...]
    uncertainty: float
    falsification_conditions: tuple[str, ...]
    provenance: tuple[str, ...]
    operator_instructions: tuple[SemanticOperatorInstruction, ...] = ()

    def validate(self, observation: ObservationIR) -> tuple[str, ...]:
        failures: list[str] = []
        if not self.body_format:
            failures.append("QUERY_BODY_FORMAT_MISSING")
        if not self.body_version:
            failures.append("QUERY_BODY_VERSION_MISSING")
        if not self.body_digest:
            failures.append("QUERY_BODY_DIGEST_MISSING")
        if not self.query_digest:
            failures.append("QUERY_DIGEST_MISSING")
        if not self.representations:
            failures.append("QUERY_REPRESENTATION_MISSING")
        if not self.retrieved_items:
            failures.append("QUERY_RETRIEVAL_MISSING")
        if len(self.hypotheses) < 2:
            failures.append("QUERY_COUNTER_HYPOTHESIS_MISSING")
        if len({item.hypothesis_id for item in self.hypotheses}) != len(
            self.hypotheses
        ):
            failures.append("QUERY_HYPOTHESIS_DUPLICATE")
        available = set(observation.available_actions)
        if any(item.action_id not in available for item in self.predictions):
            failures.append("QUERY_PREDICTION_ACTION_UNAVAILABLE")
        if available and not self.predictions:
            failures.append("QUERY_ACTION_PREDICTION_MISSING")
        for prediction in self.predictions:
            for value in (
                prediction.progress_likelihood,
                prediction.hazard_likelihood,
                prediction.information_gain,
                prediction.candidate_prior,
                prediction.uncertainty,
            ):
                if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                    failures.append("QUERY_PREDICTION_VALUE_OUT_OF_RANGE")
            if not prediction.predicted_effects:
                failures.append("QUERY_PREDICTED_EFFECT_MISSING")
            if not prediction.instruction_refs:
                failures.append("QUERY_INSTRUCTION_REF_MISSING")
            if not prediction.preconditions:
                failures.append("QUERY_PREDICTION_PRECONDITION_MISSING")
            if not prediction.falsification_conditions:
                failures.append("QUERY_PREDICTION_FALSIFIER_MISSING")
        if {item.mode for item in self.controls} != _CONTROL_MODES:
            failures.append("QUERY_CONTROL_SURFACE_INCOMPLETE")
        failures.extend(
            failure
            for control in self.controls
            for failure in control.validate()
        )
        if not math.isfinite(self.uncertainty) or not 0.0 <= self.uncertainty <= 1.0:
            failures.append("QUERY_UNCERTAINTY_OUT_OF_RANGE")
        if not self.falsification_conditions:
            failures.append("QUERY_FALSIFIER_MISSING")
        if not self.provenance:
            failures.append("QUERY_PROVENANCE_MISSING")
        failures.extend(
            failure
            for instruction in self.operator_instructions
            for failure in instruction.validate()
        )
        if len(
            {item.operator_id for item in self.operator_instructions}
        ) != len(self.operator_instructions):
            failures.append("QUERY_SEMANTIC_OPERATOR_DUPLICATE")
        if any(
            instruction.action_id not in available
            for instruction in self.operator_instructions
        ):
            failures.append("QUERY_SEMANTIC_OPERATOR_ACTION_UNAVAILABLE")
        return tuple(sorted(set(failures)))


@runtime_checkable
class InstructionBody(Protocol):
    @property
    def format_id(self) -> str: ...

    @property
    def body_version(self) -> str: ...

    @property
    def provenance_digest(self) -> str: ...

    @property
    def contract(self) -> InstructionBodyContract: ...

    def validate(self) -> tuple[str, ...]: ...

    def query(
        self,
        request: ComputeRequest,
        observation: ObservationIR,
        context: ContextSnapshot,
        memory_view: MemorySnapshot,
    ) -> InstructionQueryResult: ...

    def digest(self) -> str: ...

    def serialize(self) -> bytes: ...


@dataclass(frozen=True, slots=True)
class SymbolicRule:
    rule_id: str
    action_id: int
    predicted_effects: tuple[str, ...]
    progress_likelihood: float
    hazard_likelihood: float
    information_gain: float
    candidate_prior: float
    uncertainty: float
    support: int
    contradiction: int
    confidence: float
    preconditions: tuple[str, ...]
    falsification_conditions: tuple[str, ...]
    selectors: tuple[str, ...]
    evidence_refs: tuple[str, ...]

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not self.rule_id:
            failures.append("SYMBOLIC_RULE_ID_MISSING")
        if not 1 <= self.action_id <= 7:
            failures.append("SYMBOLIC_RULE_ACTION_INVALID")
        if not self.predicted_effects:
            failures.append("SYMBOLIC_RULE_EFFECT_MISSING")
        if self.support < 1:
            failures.append("SYMBOLIC_RULE_SUPPORT_INVALID")
        if self.contradiction < 0:
            failures.append("SYMBOLIC_RULE_CONTRADICTION_INVALID")
        if not self.preconditions:
            failures.append("SYMBOLIC_RULE_PRECONDITION_MISSING")
        if not self.falsification_conditions:
            failures.append("SYMBOLIC_RULE_FALSIFIER_MISSING")
        if not self.selectors:
            failures.append("SYMBOLIC_RULE_SELECTOR_MISSING")
        if not self.evidence_refs:
            failures.append("SYMBOLIC_RULE_EVIDENCE_MISSING")
        for value in (
            self.progress_likelihood,
            self.hazard_likelihood,
            self.information_gain,
            self.candidate_prior,
            self.uncertainty,
            self.confidence,
        ):
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                failures.append("SYMBOLIC_RULE_VALUE_OUT_OF_RANGE")
        return tuple(sorted(set(failures)))


def _validate_request_binding(
    request: ComputeRequest,
    contract: InstructionBodyContract,
    observation: ObservationIR,
    context: ContextSnapshot,
    memory_view: MemorySnapshot,
) -> tuple[str, ...]:
    failures = list(request.validate(contract))
    if request.observation_signature != observation.frame_signature:
        failures.append("INSTRUCTION_QUERY_OBSERVATION_MISMATCH")
    if request.context_signature != context.digest:
        failures.append("INSTRUCTION_QUERY_CONTEXT_MISMATCH")
    if request.memory_signature != memory_view.digest:
        failures.append("INSTRUCTION_QUERY_MEMORY_MISMATCH")
    if context.current_observation != observation:
        failures.append("INSTRUCTION_QUERY_CONTEXT_OBSERVATION_MISMATCH")
    return tuple(sorted(set(failures)))


def _representations(
    observation: ObservationIR,
    context: ContextSnapshot,
    memory_view: MemorySnapshot,
) -> tuple[str, ...]:
    output = {
        f"available-action-count:{len(observation.available_actions)}",
        f"entity-count:{len(observation.entities)}",
        f"relation-count:{len(observation.relations)}",
        f"context-action-count:{len(context.action_history)}",
        f"memory-entry-count:{len(memory_view.entries)}",
        f"terminal:{observation.terminal_state.casefold()}",
        "structural-state:present"
        if observation.structural_signature
        else "structural-state:missing",
    }
    output.update(observation.feature_tokens)
    return tuple(sorted(output))


def _hypotheses_from_predictions(
    *,
    body_format: str,
    body_digest: str,
    predictions: tuple[ActionPredictionIR, ...],
    provenance: tuple[str, ...],
) -> tuple[HypothesisIR, ...]:
    if predictions:
        selected = sorted(
            predictions,
            key=lambda item: (-item.candidate_prior, item.action_id),
        )[0]
        effect = selected.predicted_effects[0]
        confidence = _bounded(1.0 - selected.uncertainty)
        counter_effect = (
            "NO_VISIBLE_CHANGE"
            if effect != "NO_VISIBLE_CHANGE"
            else "VISIBLE_STATE_CHANGE"
        )
        action_claim = f"available-action-class:{selected.action_id}"
        support = tuple(
            sorted(
                {
                    *selected.evidence_refs,
                    *selected.instruction_refs,
                    *provenance,
                }
            )
        )
    else:
        effect = "NO_VISIBLE_CHANGE"
        counter_effect = "VISIBLE_STATE_CHANGE"
        confidence = 0.5
        action_claim = "no-action-currently-available"
        support = provenance
    suffix = _decimal_digest(
        {
            "body_format": body_format,
            "body_digest": body_digest,
            "predictions": predictions,
        },
        length=20,
    )
    return (
        HypothesisIR(
            hypothesis_id=f"hypothesis:instruction:{suffix}:primary",
            hypothesis_type="instruction-conditioned-transition",
            claims=(action_claim, "rendered effect is predicted"),
            predictions=(effect,),
            falsification_conditions=(
                "observed rendered effect differs from prediction",
            ),
            support=support,
            confidence=confidence,
            state="PROPOSED",
        ),
        HypothesisIR(
            hypothesis_id=f"hypothesis:instruction:{suffix}:counter",
            hypothesis_type="counter-hypothesis",
            claims=(action_claim, "opposite rendered effect remains possible"),
            predictions=(counter_effect,),
            falsification_conditions=(
                "observed rendered effect supports primary prediction",
            ),
            support=support,
            confidence=_bounded(1.0 - confidence),
            state="PROPOSED",
        ),
    )


def _controls_from_bundle(
    values: Sequence[Mapping[str, Any]],
    *,
    state_risk: float,
) -> tuple[ControlInstruction, ...]:
    controls: list[ControlInstruction] = []
    for value in values:
        controls.append(
            ControlInstruction(
                mode=str(value.get("mode", "")),
                preconditions=_tuple_of_text(
                    value.get("preconditions"),
                    "control.preconditions",
                ),
                expected_progress=_bounded(
                    _float(
                        value.get("expected_progress"),
                        "control.expected_progress",
                    )
                ),
                information_gain=_bounded(
                    _float(
                        value.get("information_gain"),
                        "control.information_gain",
                    )
                ),
                expected_risk=_bounded(
                    _float(value.get("expected_risk"), "control.expected_risk")
                    + state_risk
                ),
                repetition_cost=_bounded(
                    _float(
                        value.get("repetition_cost"),
                        "control.repetition_cost",
                    )
                ),
                rollback_cost=_bounded(
                    _float(
                        value.get("rollback_cost"),
                        "control.rollback_cost",
                    )
                ),
                falsification_conditions=_tuple_of_text(
                    value.get("falsification_conditions"),
                    "control.falsification_conditions",
                ),
                provenance=_tuple_of_text(
                    value.get("provenance"),
                    "control.provenance",
                ),
            )
        )
    return tuple(sorted(controls, key=lambda item: item.mode))


def _base_bundle_failures(
    *,
    bundle: Mapping[str, Any],
    contract: InstructionBodyContract,
    expected_format: str,
) -> list[str]:
    failures = list(contract.validate())
    if bundle.get("schema_version") != INSTRUCTION_BODY_SCHEMA_VERSION:
        failures.append("INSTRUCTION_BODY_SCHEMA_VERSION_INVALID")
    if contract.schema_version != INSTRUCTION_BODY_SCHEMA_VERSION:
        failures.append("INSTRUCTION_BODY_CONTRACT_SCHEMA_VERSION_INVALID")
    if bundle.get("format_id") != expected_format:
        failures.append("INSTRUCTION_BODY_FORMAT_INVALID")
    if contract.format_id != expected_format:
        failures.append("INSTRUCTION_BODY_CONTRACT_FORMAT_INVALID")
    if bundle.get("body_version") != contract.body_version:
        failures.append("INSTRUCTION_BODY_VERSION_MISMATCH")
    if bundle.get("provenance_digest") != contract.provenance_digest:
        failures.append("INSTRUCTION_BODY_PROVENANCE_MISMATCH")
    expected_digest = instruction_bundle_digest(bundle)
    if bundle.get("content_digest") != expected_digest:
        failures.append("INSTRUCTION_BODY_CONTENT_DIGEST_MISMATCH")
    if contract.content_digest != expected_digest:
        failures.append("INSTRUCTION_BODY_CONTRACT_DIGEST_MISMATCH")
    if bundle.get("runtime_identity_free") is not True:
        failures.append("INSTRUCTION_BODY_RUNTIME_IDENTITY_FLAG_INVALID")
    if contract.bound is not True:
        failures.append("INSTRUCTION_BODY_CONTRACT_UNBOUND")
    failures.extend(
        f"INSTRUCTION_BODY_RUNTIME_IDENTITY_FORBIDDEN:{path}"
        for path in _runtime_value_failures(bundle)
    )
    return failures


@dataclass(frozen=True, slots=True)
class SymbolicInstructionBody:
    _bundle: Mapping[str, Any]
    contract: InstructionBodyContract
    nodes: tuple[tuple[str, str], ...]
    edges: tuple[tuple[str, str, str], ...]
    rules: tuple[SymbolicRule, ...]
    control_profiles: tuple[Mapping[str, Any], ...]
    operator_instructions: tuple[SemanticOperatorInstruction, ...] = ()

    @property
    def format_id(self) -> str:
        return SYMBOLIC_FORMAT_ID

    @property
    def body_version(self) -> str:
        return self.contract.body_version

    @property
    def provenance_digest(self) -> str:
        return self.contract.provenance_digest

    def digest(self) -> str:
        return self.contract.content_digest

    def serialize(self) -> bytes:
        return (
            json.dumps(
                self._bundle,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")

    def validate(self) -> tuple[str, ...]:
        failures = _base_bundle_failures(
            bundle=self._bundle,
            contract=self.contract,
            expected_format=self.format_id,
        )
        if not self.nodes:
            failures.append("SYMBOLIC_NODE_SET_EMPTY")
        if not self.edges:
            failures.append("SYMBOLIC_EDGE_SET_EMPTY")
        if not self.rules:
            failures.append("SYMBOLIC_RULE_SET_EMPTY")
        failures.extend(
            failure for rule in self.rules for failure in rule.validate()
        )
        if len({rule.rule_id for rule in self.rules}) != len(self.rules):
            failures.append("SYMBOLIC_RULE_ID_DUPLICATE")
        if {rule.action_id for rule in self.rules} != set(range(1, 8)):
            failures.append("SYMBOLIC_ACTION_COVERAGE_INCOMPLETE")
        controls = _controls_from_bundle(self.control_profiles, state_risk=0.0)
        if {item.mode for item in controls} != _CONTROL_MODES:
            failures.append("SYMBOLIC_CONTROL_COVERAGE_INCOMPLETE")
        failures.extend(
            failure
            for instruction in self.operator_instructions
            for failure in instruction.validate()
        )
        if len(
            {item.operator_id for item in self.operator_instructions}
        ) != len(self.operator_instructions):
            failures.append("SYMBOLIC_SEMANTIC_OPERATOR_DUPLICATE")
        return tuple(sorted(set(failures)))

    def query(
        self,
        request: ComputeRequest,
        observation: ObservationIR,
        context: ContextSnapshot,
        memory_view: MemorySnapshot,
    ) -> InstructionQueryResult:
        failures = list(self.validate())
        failures.extend(
            _validate_request_binding(
                request,
                self.contract,
                observation,
                context,
                memory_view,
            )
        )
        if failures:
            raise ValueError(";".join(sorted(set(failures))))

        predictions: list[ActionPredictionIR] = []
        action_history = context.action_history
        state_risk = 0.1 if context.failures else 0.0
        if any(effect in {"HAZARD", "IRREVERSIBLE_FAILURE"} for effect in observation.visible_effects):
            state_risk = 0.25
        for rule in self.rules:
            if rule.action_id not in observation.available_actions:
                continue
            repetitions = action_history.count(rule.action_id)
            repetition_penalty = min(0.25, 0.05 * repetitions)
            memory_bonus = min(0.1, 0.01 * len(memory_view.entries))
            progress = _bounded(rule.progress_likelihood + memory_bonus)
            hazard = _bounded(rule.hazard_likelihood + state_risk)
            information_gain = _bounded(
                rule.information_gain + repetition_penalty
            )
            prior = _bounded(
                rule.candidate_prior
                + (0.15 * progress)
                - (0.2 * hazard)
                - repetition_penalty
            )
            predictions.append(
                ActionPredictionIR(
                    action_id=rule.action_id,
                    predicted_effects=rule.predicted_effects,
                    progress_likelihood=progress,
                    hazard_likelihood=hazard,
                    information_gain=information_gain,
                    candidate_prior=prior,
                    uncertainty=_bounded(
                        rule.uncertainty + (0.05 * repetitions)
                    ),
                    evidence_refs=rule.evidence_refs,
                    instruction_refs=(rule.rule_id,),
                    preconditions=rule.preconditions,
                    falsification_conditions=rule.falsification_conditions,
                )
            )
        ordered_predictions = tuple(
            sorted(predictions, key=lambda item: item.action_id)
        )
        provenance = (
            self.provenance_digest,
            self.digest(),
        )
        hypotheses = _hypotheses_from_predictions(
            body_format=self.format_id,
            body_digest=self.digest(),
            predictions=ordered_predictions,
            provenance=provenance,
        )
        controls = _controls_from_bundle(
            self.control_profiles,
            state_risk=state_risk,
        )
        operator_instructions = tuple(
            sorted(
                (
                    instruction
                    for instruction in self.operator_instructions
                    if instruction.action_id in observation.available_actions
                ),
                key=lambda item: item.operator_id,
            )
        )
        query_seed = {
            "request": request,
            "body": self.digest(),
            "representations": _representations(
                observation,
                context,
                memory_view,
            ),
            "predictions": ordered_predictions,
            "controls": controls,
            "operator_instructions": operator_instructions,
        }
        result = InstructionQueryResult(
            body_format=self.format_id,
            body_version=self.body_version,
            body_digest=self.digest(),
            query_digest="query:" + _decimal_digest(query_seed, length=24),
            representations=_representations(
                observation,
                context,
                memory_view,
            ),
            retrieved_items=tuple(
                sorted(
                    {
                        *(
                            ref
                            for prediction in ordered_predictions
                            for ref in prediction.instruction_refs
                        ),
                        *(
                            instruction.operator_id
                            for instruction in operator_instructions
                        ),
                    }
                )
            )
            or ("control-profile-set",),
            hypotheses=hypotheses,
            predictions=ordered_predictions,
            controls=controls,
            uncertainty=_bounded(
                sum(item.uncertainty for item in ordered_predictions)
                / max(1, len(ordered_predictions))
            ),
            falsification_conditions=(
                tuple(
                    sorted(
                        {
                            condition
                            for rule in self.rules
                            if rule.action_id in observation.available_actions
                            for condition in rule.falsification_conditions
                        }
                    )
                )
                or ("new observation enables an action class",)
            ),
            provenance=provenance,
            operator_instructions=operator_instructions,
        )
        result_failures = result.validate(observation)
        if result_failures:
            raise ValueError(";".join(result_failures))
        return result


def runtime_feature_vector(
    action_id: int,
    observation: ObservationIR,
    context: ContextSnapshot,
    memory_view: MemorySnapshot,
) -> tuple[float, ...]:
    """Map identity-free runtime state to the fixed P-B feature contract."""

    active_terminal = observation.terminal_state in {"RUNNING", "NOT_FINISHED"}
    return (
        1.0,
        action_id / 7.0,
        len(observation.available_actions) / 7.0,
        float(bool(observation.entities)),
        float(bool(observation.relations)),
        float(bool(observation.visible_effects)),
        float(context.previous_observation is not None),
        min(1.0, len(context.action_history) / 16.0),
        min(1.0, len(memory_view.entries) / 32.0),
        float(bool(context.failures)),
        float(active_terminal),
        float(bool(observation.structural_signature)),
    )


@dataclass(frozen=True, slots=True)
class ParametricInstructionBody:
    _bundle: Mapping[str, Any]
    contract: InstructionBodyContract
    feature_names: tuple[str, ...]
    heads: tuple[str, ...]
    weights: tuple[tuple[float, ...], ...]
    action_preconditions: tuple[str, ...]
    action_falsification_conditions: tuple[str, ...]
    control_profiles: tuple[Mapping[str, Any], ...]
    training_record_count: int
    holdout_record_count: int
    parameter_count: int
    parameter_digest: str
    operator_instructions: tuple[SemanticOperatorInstruction, ...] = ()

    @property
    def format_id(self) -> str:
        return PARAMETRIC_FORMAT_ID

    @property
    def body_version(self) -> str:
        return self.contract.body_version

    @property
    def provenance_digest(self) -> str:
        return self.contract.provenance_digest

    def digest(self) -> str:
        return self.contract.content_digest

    def serialize(self) -> bytes:
        return (
            json.dumps(
                self._bundle,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")

    def validate(self) -> tuple[str, ...]:
        failures = _base_bundle_failures(
            bundle=self._bundle,
            contract=self.contract,
            expected_format=self.format_id,
        )
        if self.feature_names != PARAMETRIC_FEATURES:
            failures.append("PARAMETRIC_FEATURE_SCHEMA_INVALID")
        if self.heads != PARAMETRIC_HEADS:
            failures.append("PARAMETRIC_HEAD_SCHEMA_INVALID")
        if len(self.weights) != len(self.heads):
            failures.append("PARAMETRIC_WEIGHT_HEAD_COUNT_INVALID")
        if any(len(row) != len(self.feature_names) for row in self.weights):
            failures.append("PARAMETRIC_WEIGHT_SHAPE_INVALID")
        flattened = tuple(value for row in self.weights for value in row)
        if any(not math.isfinite(value) for value in flattened):
            failures.append("PARAMETRIC_WEIGHT_NONFINITE")
        if not any(abs(value) > 1e-12 for value in flattened):
            failures.append("PARAMETRIC_WEIGHTS_UNTRAINED")
        if self.parameter_count != len(flattened):
            failures.append("PARAMETRIC_PARAMETER_COUNT_MISMATCH")
        expected_parameter_digest = (
            "parameter-matrix:" + _decimal_digest(self.weights, length=40)
        )
        if self.parameter_digest != expected_parameter_digest:
            failures.append("PARAMETRIC_PARAMETER_DIGEST_MISMATCH")
        if not self.action_preconditions:
            failures.append("PARAMETRIC_ACTION_PRECONDITION_MISSING")
        if not self.action_falsification_conditions:
            failures.append("PARAMETRIC_ACTION_FALSIFIER_MISSING")
        if self.training_record_count < 1:
            failures.append("PARAMETRIC_TRAINING_RECORDS_MISSING")
        if self.holdout_record_count < 1:
            failures.append("PARAMETRIC_HOLDOUT_RECORDS_MISSING")
        controls = _controls_from_bundle(self.control_profiles, state_risk=0.0)
        if {item.mode for item in controls} != _CONTROL_MODES:
            failures.append("PARAMETRIC_CONTROL_COVERAGE_INCOMPLETE")
        failures.extend(
            failure
            for instruction in self.operator_instructions
            for failure in instruction.validate()
        )
        if len(
            {item.operator_id for item in self.operator_instructions}
        ) != len(self.operator_instructions):
            failures.append("PARAMETRIC_SEMANTIC_OPERATOR_DUPLICATE")
        return tuple(sorted(set(failures)))

    def query(
        self,
        request: ComputeRequest,
        observation: ObservationIR,
        context: ContextSnapshot,
        memory_view: MemorySnapshot,
    ) -> InstructionQueryResult:
        failures = list(self.validate())
        failures.extend(
            _validate_request_binding(
                request,
                self.contract,
                observation,
                context,
                memory_view,
            )
        )
        if failures:
            raise ValueError(";".join(sorted(set(failures))))

        predictions: list[ActionPredictionIR] = []
        head_index = {name: index for index, name in enumerate(self.heads)}
        parameter_ref = "parameter-matrix:" + _decimal_digest(
            self.weights,
            length=24,
        )
        for action_id in observation.available_actions:
            features = runtime_feature_vector(
                action_id,
                observation,
                context,
                memory_view,
            )
            outputs = {
                head: _bounded(
                    _sigmoid(
                        sum(
                            weight * feature
                            for weight, feature in zip(
                                self.weights[index],
                                features,
                                strict=True,
                            )
                        )
                    )
                )
                for head, index in head_index.items()
            }
            effect = (
                "VISIBLE_STATE_CHANGE"
                if outputs["effect"] >= 0.5
                else "NO_VISIBLE_CHANGE"
            )
            predictions.append(
                ActionPredictionIR(
                    action_id=action_id,
                    predicted_effects=(effect,),
                    progress_likelihood=outputs["progress"],
                    hazard_likelihood=outputs["hazard"],
                    information_gain=outputs["information_gain"],
                    candidate_prior=outputs["candidate_prior"],
                    uncertainty=outputs["uncertainty"],
                    evidence_refs=(self.provenance_digest,),
                    instruction_refs=(parameter_ref,),
                    preconditions=tuple(
                        value.replace("{action_id}", str(action_id))
                        for value in self.action_preconditions
                    ),
                    falsification_conditions=(
                        self.action_falsification_conditions
                    ),
                )
            )
        ordered_predictions = tuple(
            sorted(predictions, key=lambda item: item.action_id)
        )
        state_risk = (
            max(
                (item.hazard_likelihood for item in ordered_predictions),
                default=0.0,
            )
            * 0.1
        )
        controls = _controls_from_bundle(
            self.control_profiles,
            state_risk=state_risk,
        )
        provenance = (
            self.provenance_digest,
            self.digest(),
            parameter_ref,
        )
        hypotheses = _hypotheses_from_predictions(
            body_format=self.format_id,
            body_digest=self.digest(),
            predictions=ordered_predictions,
            provenance=provenance,
        )
        representations = _representations(
            observation,
            context,
            memory_view,
        )
        operator_instructions = tuple(
            sorted(
                (
                    instruction
                    for instruction in self.operator_instructions
                    if instruction.action_id in observation.available_actions
                ),
                key=lambda item: item.operator_id,
            )
        )
        result = InstructionQueryResult(
            body_format=self.format_id,
            body_version=self.body_version,
            body_digest=self.digest(),
            query_digest="query:"
            + _decimal_digest(
                {
                    "request": request,
                    "body": self.digest(),
                    "features": tuple(
                        runtime_feature_vector(
                            action,
                            observation,
                            context,
                            memory_view,
                        )
                        for action in observation.available_actions
                    ),
                    "predictions": ordered_predictions,
                },
                length=24,
            ),
            representations=representations,
            retrieved_items=tuple(
                sorted(
                    {
                        parameter_ref,
                        *(
                            instruction.operator_id
                            for instruction in operator_instructions
                        ),
                    }
                )
            ),
            hypotheses=hypotheses,
            predictions=ordered_predictions,
            controls=controls,
            uncertainty=_bounded(
                sum(item.uncertainty for item in ordered_predictions)
                / max(1, len(ordered_predictions))
            ),
            falsification_conditions=(
                "held-out rendered effect contradicts predicted effect",
                "held-out hazard rate exceeds predicted likelihood",
            ),
            provenance=provenance,
            operator_instructions=operator_instructions,
        )
        result_failures = result.validate(observation)
        if result_failures:
            raise ValueError(";".join(result_failures))
        return result


def _control_profiles(value: object) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(
        value, (str, bytes, bytearray)
    ):
        raise TypeError("control_profiles must be an array")
    return tuple(_mapping(item, "control profile") for item in value)


def _semantic_operator_instructions(
    value: object,
) -> tuple[SemanticOperatorInstruction, ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(
        value,
        (str, bytes, bytearray),
    ):
        raise TypeError("operator_instructions must be an array")
    instructions: list[SemanticOperatorInstruction] = []
    for raw_value in value:
        raw = _mapping(raw_value, "operator instruction")
        parameters = _mapping(
            raw.get("parameters"),
            "operator instruction parameters",
        )
        instructions.append(
            SemanticOperatorInstruction(
                operator_id=str(raw.get("operator_id", "")),
                action_id=_int(
                    raw.get("action_id"),
                    "operator instruction action_id",
                ),
                detector=str(raw.get("detector", "")),
                transform=str(raw.get("transform", "")),
                parameter_items=tuple(
                    sorted(
                        (str(key), copy.deepcopy(item))
                        for key, item in parameters.items()
                    )
                ),
                preconditions=_tuple_of_text(
                    raw.get("preconditions"),
                    "operator instruction preconditions",
                ),
                falsification_conditions=_tuple_of_text(
                    raw.get("falsification_conditions"),
                    "operator instruction falsification_conditions",
                ),
                provenance=_tuple_of_text(
                    raw.get("provenance"),
                    "operator instruction provenance",
                ),
            )
        )
    return tuple(
        sorted(instructions, key=lambda instruction: instruction.operator_id)
    )


def instruction_body_from_mapping(
    value: Mapping[str, Any],
) -> SymbolicInstructionBody | ParametricInstructionBody:
    bundle = copy.deepcopy(dict(value))
    contract = _contract_from_mapping(bundle.get("contract"))
    format_id = str(bundle.get("format_id", ""))
    payload = _mapping(bundle.get("payload"), "payload")
    controls = _control_profiles(payload.get("control_profiles"))
    operator_instructions = _semantic_operator_instructions(
        payload.get("operator_instructions", ())
    )
    body: SymbolicInstructionBody | ParametricInstructionBody

    if format_id == SYMBOLIC_FORMAT_ID:
        graph = _mapping(payload.get("graph"), "payload.graph")
        nodes_value = graph.get("nodes")
        edges_value = graph.get("edges")
        rules_value = payload.get("rules")
        if not isinstance(nodes_value, Sequence) or isinstance(
            nodes_value, (str, bytes, bytearray)
        ):
            raise TypeError("graph.nodes must be an array")
        if not isinstance(edges_value, Sequence) or isinstance(
            edges_value, (str, bytes, bytearray)
        ):
            raise TypeError("graph.edges must be an array")
        if not isinstance(rules_value, Sequence) or isinstance(
            rules_value, (str, bytes, bytearray)
        ):
            raise TypeError("payload.rules must be an array")
        nodes = tuple(
            (
                str(_mapping(item, "node").get("node_id", "")),
                str(_mapping(item, "node").get("node_type", "")),
            )
            for item in nodes_value
        )
        edges = tuple(
            (
                str(_mapping(item, "edge").get("source", "")),
                str(_mapping(item, "edge").get("relation", "")),
                str(_mapping(item, "edge").get("target", "")),
            )
            for item in edges_value
        )
        rules: list[SymbolicRule] = []
        for item in rules_value:
            rule = _mapping(item, "rule")
            rules.append(
                SymbolicRule(
                    rule_id=str(rule.get("rule_id", "")),
                    action_id=_int(rule.get("action_id"), "rule.action_id"),
                    predicted_effects=_tuple_of_text(
                        rule.get("predicted_effects"),
                        "rule.predicted_effects",
                    ),
                    progress_likelihood=_float(
                        rule.get("progress_likelihood"),
                        "rule.progress_likelihood",
                    ),
                    hazard_likelihood=_float(
                        rule.get("hazard_likelihood"),
                        "rule.hazard_likelihood",
                    ),
                    information_gain=_float(
                        rule.get("information_gain"),
                        "rule.information_gain",
                    ),
                    candidate_prior=_float(
                        rule.get("candidate_prior"),
                        "rule.candidate_prior",
                    ),
                    uncertainty=_float(
                        rule.get("uncertainty"),
                        "rule.uncertainty",
                    ),
                    support=_int(rule.get("support"), "rule.support"),
                    contradiction=_int(
                        rule.get("contradiction"),
                        "rule.contradiction",
                    ),
                    confidence=_float(
                        rule.get("confidence"),
                        "rule.confidence",
                    ),
                    preconditions=_tuple_of_text(
                        rule.get("preconditions"),
                        "rule.preconditions",
                    ),
                    falsification_conditions=_tuple_of_text(
                        rule.get("falsification_conditions"),
                        "rule.falsification_conditions",
                    ),
                    selectors=_tuple_of_text(
                        rule.get("selectors"),
                        "rule.selectors",
                    ),
                    evidence_refs=_tuple_of_text(
                        rule.get("evidence_refs"),
                        "rule.evidence_refs",
                    ),
                )
            )
        body = SymbolicInstructionBody(
            _bundle=bundle,
            contract=contract,
            nodes=nodes,
            edges=edges,
            rules=tuple(rules),
            control_profiles=controls,
            operator_instructions=operator_instructions,
        )
    elif format_id == PARAMETRIC_FORMAT_ID:
        model = _mapping(payload.get("model"), "payload.model")
        weights_value = model.get("weights")
        if not isinstance(weights_value, Sequence) or isinstance(
            weights_value, (str, bytes, bytearray)
        ):
            raise TypeError("model.weights must be an array")
        weights = tuple(
            tuple(
                _float(weight, "model.weight")
                for weight in _tuple_sequence(row, "model.weight row")
            )
            for row in weights_value
        )
        body = ParametricInstructionBody(
            _bundle=bundle,
            contract=contract,
            feature_names=_tuple_of_text(
                model.get("feature_names"),
                "model.feature_names",
            ),
            heads=_tuple_of_text(model.get("heads"), "model.heads"),
            weights=weights,
            action_preconditions=_tuple_of_text(
                model.get("action_preconditions"),
                "model.action_preconditions",
            ),
            action_falsification_conditions=_tuple_of_text(
                model.get("action_falsification_conditions"),
                "model.action_falsification_conditions",
            ),
            control_profiles=controls,
            training_record_count=_int(
                model.get("training_record_count"),
                "model.training_record_count",
            ),
            holdout_record_count=_int(
                model.get("holdout_record_count"),
                "model.holdout_record_count",
            ),
            parameter_count=_int(
                model.get("parameter_count"),
                "model.parameter_count",
            ),
            parameter_digest=str(model.get("parameter_digest", "")),
            operator_instructions=operator_instructions,
        )
    else:
        raise ValueError("unsupported instruction body format")

    failures = body.validate()
    if failures:
        raise ValueError(";".join(failures))
    return body


def _tuple_sequence(value: object, field_name: str) -> tuple[object, ...]:
    if not isinstance(value, Sequence) or isinstance(
        value, (str, bytes, bytearray)
    ):
        raise TypeError(f"{field_name} must be an array")
    return tuple(value)


def load_instruction_body(
    path: Path,
) -> SymbolicInstructionBody | ParametricInstructionBody:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise TypeError("instruction body must decode to an object")
    return instruction_body_from_mapping(value)


def _bundle_path(filename: str) -> Path:
    return Path(__file__).resolve().parent / "bundles" / filename


def _load_p10_manifest_body(
    manifest_filename: str,
    variant: str,
) -> SymbolicInstructionBody | ParametricInstructionBody:
    manifest_path = _bundle_path(manifest_filename)
    manifest_value = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest_value, Mapping):
        raise TypeError("P10 manifest must decode to an object")
    if manifest_value.get("runtime_identity_free") is not True:
        raise ValueError("P10 manifest is not runtime identity-free")
    expected_lifecycles = (
        ("CANDIDATE", "PROMOTED")
        if manifest_filename == "p10_candidate_manifest.json"
        else ("ACTIVE",)
    )
    lifecycle = manifest_value.get("lifecycle", "ACTIVE")
    if lifecycle not in expected_lifecycles:
        raise ValueError(
            "P10 manifest lifecycle mismatch:"
            f"expected={'|'.join(expected_lifecycles)}:actual={lifecycle}"
        )
    bundles = manifest_value.get("bundles")
    if not isinstance(bundles, Mapping):
        raise TypeError("P10 manifest bundles must be an object")
    entry = bundles.get(variant)
    if not isinstance(entry, Mapping):
        raise KeyError(f"P10 manifest variant missing: {variant}")
    filename = entry.get("filename")
    if (
        not isinstance(filename, str)
        or not filename
        or Path(filename).name != filename
    ):
        raise ValueError("P10 manifest bundle filename invalid")
    path = _bundle_path(filename)
    expected_sha256 = entry.get("sha256")
    actual_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    if expected_sha256 != actual_sha256:
        raise ValueError(f"P10 manifest bundle sha256 mismatch: {variant}")
    body = load_instruction_body(path)
    if entry.get("body_version") != body.body_version:
        raise ValueError(f"P10 manifest body version mismatch: {variant}")
    if entry.get("content_digest") != body.digest():
        raise ValueError(f"P10 manifest content digest mismatch: {variant}")
    if entry.get("format_id") != body.format_id:
        raise ValueError(f"P10 manifest format mismatch: {variant}")
    return body


@functools.lru_cache(maxsize=1)
def load_default_symbolic_instruction_body() -> SymbolicInstructionBody:
    body = load_instruction_body(_bundle_path("p_a_symbolic_v1.json"))
    if not isinstance(body, SymbolicInstructionBody):
        raise TypeError("default symbolic bundle has wrong format")
    return body


@functools.lru_cache(maxsize=1)
def load_default_parametric_instruction_body() -> ParametricInstructionBody:
    body = load_instruction_body(_bundle_path("p_b_parametric_v1.json"))
    if not isinstance(body, ParametricInstructionBody):
        raise TypeError("default parametric bundle has wrong format")
    return body


@functools.lru_cache(maxsize=1)
def load_p10_symbolic_instruction_body() -> SymbolicInstructionBody:
    """Load only the HDS-promoted active P-A bundle."""

    body = _load_p10_manifest_body("p10_manifest.json", "P-A")
    if not isinstance(body, SymbolicInstructionBody):
        raise TypeError("P10 symbolic bundle has wrong format")
    return body


@functools.lru_cache(maxsize=1)
def load_p10_parametric_instruction_body() -> ParametricInstructionBody:
    """Load only the HDS-promoted active P-B bundle."""

    body = _load_p10_manifest_body("p10_manifest.json", "P-B")
    if not isinstance(body, ParametricInstructionBody):
        raise TypeError("P10 parametric bundle has wrong format")
    return body


@functools.lru_cache(maxsize=1)
def load_p10_hybrid_instruction_body() -> ParametricInstructionBody:
    """Load only the HDS-promoted active hybrid bundle."""

    body = _load_p10_manifest_body("p10_manifest.json", "hybrid")
    if not isinstance(body, ParametricInstructionBody):
        raise TypeError("P10 hybrid bundle has wrong format")
    return body


@functools.lru_cache(maxsize=1)
def load_p10_candidate_symbolic_instruction_body() -> SymbolicInstructionBody:
    """Load the isolated candidate or its immutable promoted archive."""

    body = _load_p10_manifest_body("p10_candidate_manifest.json", "P-A")
    if not isinstance(body, SymbolicInstructionBody):
        raise TypeError("P10 candidate symbolic bundle has wrong format")
    return body


@functools.lru_cache(maxsize=1)
def load_p10_candidate_parametric_instruction_body() -> ParametricInstructionBody:
    """Load the isolated candidate or its immutable promoted archive."""

    body = _load_p10_manifest_body("p10_candidate_manifest.json", "P-B")
    if not isinstance(body, ParametricInstructionBody):
        raise TypeError("P10 candidate parametric bundle has wrong format")
    return body


@functools.lru_cache(maxsize=1)
def load_p10_candidate_hybrid_instruction_body() -> ParametricInstructionBody:
    """Load the isolated candidate or its immutable promoted archive."""

    body = _load_p10_manifest_body("p10_candidate_manifest.json", "hybrid")
    if not isinstance(body, ParametricInstructionBody):
        raise TypeError("P10 candidate hybrid bundle has wrong format")
    return body


def clear_p10_instruction_body_caches() -> None:
    """Invalidate active/candidate loaders after an HDS lifecycle transition."""

    load_p10_symbolic_instruction_body.cache_clear()
    load_p10_parametric_instruction_body.cache_clear()
    load_p10_hybrid_instruction_body.cache_clear()
    load_p10_candidate_symbolic_instruction_body.cache_clear()
    load_p10_candidate_parametric_instruction_body.cache_clear()
    load_p10_candidate_hybrid_instruction_body.cache_clear()


__all__ = [
    "INSTRUCTION_BODY_REMOVAL_WITNESS",
    "INSTRUCTION_BODY_SCHEMA_VERSION",
    "InstructionBody",
    "InstructionQueryResult",
    "PARAMETRIC_FEATURES",
    "PARAMETRIC_FORMAT_ID",
    "PARAMETRIC_HEADS",
    "ParametricInstructionBody",
    "SYMBOLIC_FORMAT_ID",
    "SymbolicInstructionBody",
    "SymbolicRule",
    "clear_p10_instruction_body_caches",
    "instruction_body_from_mapping",
    "instruction_bundle_digest",
    "load_default_parametric_instruction_body",
    "load_default_symbolic_instruction_body",
    "load_instruction_body",
    "load_p10_candidate_hybrid_instruction_body",
    "load_p10_candidate_parametric_instruction_body",
    "load_p10_candidate_symbolic_instruction_body",
    "load_p10_hybrid_instruction_body",
    "load_p10_parametric_instruction_body",
    "load_p10_symbolic_instruction_body",
    "runtime_feature_vector",
    "seal_instruction_bundle",
]
