"""Deterministic serialization and boundary validation for ARC-3 IR."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from .ir import (
    CandidateIR,
    ClosureIR,
    CompiledRecord,
    EntityIR,
    HypothesisIR,
    ObservationIR,
    ProofObligationIR,
    TransitionIR,
)

SCHEMA_VERSION = "arc3-agent-ir-v1"

TERMINAL_STATES = frozenset(
    {"RUNNING", "WIN", "NOT_FINISHED", "GAME_OVER", "UNKNOWN"}
)
EVIDENCE_STATES = frozenset({"OPEN", "BOUNDED_SUSPEND", "CLOSED", "UNKNOWN"})
CLOSURE_STATUSES = frozenset(
    {"PASS", "PROBE", "HOLD", "SUSPEND", "FAIL", "REJECT", "STOP"}
)
FORBIDDEN_RUNTIME_KEYS = frozenset(
    {
        "game_id",
        "task_id",
        "level_id",
        "replay_index",
        "answer_map",
        "source_state",
        "hidden_state",
        "fixed_action_sequence",
        "literal_coordinate_table",
    }
)
FORBIDDEN_RUNTIME_KEY_TOKENS = frozenset(
    re.sub(r"[^a-z0-9]", "", key.casefold()) for key in FORBIDDEN_RUNTIME_KEYS
)


def _jsonable(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return {
            item.name: _jsonable(getattr(value, item.name))
            for item in dataclasses.fields(value)
            if item.metadata.get("serialize", True)
        }
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(
        _jsonable(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def digest_object(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def record_to_dict(record: CompiledRecord) -> dict[str, Any]:
    value = _jsonable(record)
    if not isinstance(value, dict):
        raise TypeError("compiled record did not serialize to an object")
    return value


def _entity_from_dict(data: Mapping[str, Any]) -> EntityIR:
    return EntityIR(
        entity_id=str(data["entity_id"]),
        features=tuple(str(item) for item in data.get("features", [])),
        role_hypotheses=tuple(dict(item) for item in data.get("role_hypotheses", [])),
    )


def _candidate_from_dict(data: Mapping[str, Any]) -> CandidateIR:
    expected = {
        str(key): tuple(str(item) for item in values)
        for key, values in dict(data.get("expected_effects_by_hypothesis", {})).items()
    }
    return CandidateIR(
        candidate_id=str(data["candidate_id"]),
        mode=str(data["mode"]),
        steps=tuple(dict(item) for item in data.get("steps", [])),
        preconditions=tuple(str(item) for item in data.get("preconditions", [])),
        expected_effects_by_hypothesis=expected,
        expected_progress=float(data.get("expected_progress", 0.0)),
        expected_information_gain=float(data.get("expected_information_gain", 0.0)),
        expected_risk=float(data.get("expected_risk", 0.0)),
        repetition_cost=float(data.get("repetition_cost", 0.0)),
        rollback_cost=float(data.get("rollback_cost", 0.0)),
        provenance=tuple(str(item) for item in data.get("provenance", [])),
        falsification_conditions=tuple(
            str(item) for item in data.get("falsification_conditions", [])
        ),
    )


def record_from_dict(data: Mapping[str, Any]) -> CompiledRecord:
    observation_data = data["observation"]
    if not isinstance(observation_data, Mapping):
        raise TypeError("observation must be an object")
    dimensions_value = observation_data.get("dimensions")
    dimensions: tuple[int, int] | None
    if dimensions_value is None:
        dimensions = None
    else:
        values = tuple(int(item) for item in dimensions_value)
        if len(values) != 2:
            raise ValueError("dimensions must have two values")
        dimensions = (values[0], values[1])

    observation = ObservationIR(
        frame_signature=str(observation_data["frame_signature"]),
        structural_signature=str(observation_data["structural_signature"]),
        mechanic_signature=str(observation_data["mechanic_signature"]),
        dimensions=dimensions,
        available_actions=tuple(
            int(item) for item in observation_data.get("available_actions", [])
        ),
        visible_effects=tuple(
            str(item) for item in observation_data.get("visible_effects", [])
        ),
        entities=tuple(
            _entity_from_dict(item) for item in observation_data.get("entities", [])
        ),
        relations=tuple(str(item) for item in observation_data.get("relations", [])),
        resources=tuple(str(item) for item in observation_data.get("resources", [])),
        phase_hypotheses=tuple(
            str(item) for item in observation_data.get("phase_hypotheses", [])
        ),
        feature_tokens=tuple(
            str(item) for item in observation_data.get("feature_tokens", [])
        ),
        terminal_state=str(observation_data.get("terminal_state", "UNKNOWN")),
    )

    transition_value = data.get("transition")
    transition: TransitionIR | None = None
    if transition_value is not None:
        if not isinstance(transition_value, Mapping):
            raise TypeError("transition must be an object or null")
        transition = TransitionIR(
            before=str(transition_value["before"]),
            after=(
                str(transition_value["after"])
                if transition_value.get("after") is not None
                else None
            ),
            action_class=str(transition_value["action_class"]),
            effects=tuple(str(item) for item in transition_value.get("effects", [])),
            progress_evidence=tuple(
                str(item) for item in transition_value.get("progress_evidence", [])
            ),
            hazard_evidence=tuple(
                str(item) for item in transition_value.get("hazard_evidence", [])
            ),
            no_effect=bool(transition_value.get("no_effect", False)),
            delayed_visibility=bool(
                transition_value.get("delayed_visibility", False)
            ),
            confidence=float(transition_value.get("confidence", 0.0)),
        )

    hypotheses = tuple(
        HypothesisIR(
            hypothesis_id=str(item["hypothesis_id"]),
            hypothesis_type=str(item["hypothesis_type"]),
            claims=tuple(str(value) for value in item.get("claims", [])),
            predictions=tuple(str(value) for value in item.get("predictions", [])),
            falsification_conditions=tuple(
                str(value) for value in item.get("falsification_conditions", [])
            ),
            support=tuple(str(value) for value in item.get("support", [])),
            contradictions=tuple(
                str(value) for value in item.get("contradictions", [])
            ),
            confidence=float(item.get("confidence", 0.0)),
            state=str(item.get("state", "ACTIVE")),
        )
        for item in data.get("hypotheses", [])
    )

    candidates = tuple(
        _candidate_from_dict(item) for item in data.get("candidates", [])
    )

    closures = tuple(
        ClosureIR(
            candidate_id=str(item["candidate_id"]),
            x=dict(item.get("x", {})),
            r=dict(item.get("r", {})),
            mc=dict(item.get("mc", {})),
            status=str(item["status"]),
            reason_codes=tuple(str(value) for value in item.get("reason_codes", [])),
            missing_terms=tuple(str(value) for value in item.get("missing_terms", [])),
            confidence=float(item.get("confidence", 0.0)),
        )
        for item in data.get("closures", [])
    )

    obligations = tuple(
        ProofObligationIR(
            obligation_id=str(item["obligation_id"]),
            kind=str(item["kind"]),
            status=str(item["status"]),
            missing_terms=tuple(str(value) for value in item.get("missing_terms", [])),
            reopen_condition=str(item.get("reopen_condition", "")),
            evidence_boundary=str(item.get("evidence_boundary", "")),
        )
        for item in data.get("proof_obligations", [])
    )

    return CompiledRecord(
        observation=observation,
        transition=transition,
        hypotheses=hypotheses,
        candidates=candidates,
        closures=closures,
        proof_obligations=obligations,
        evidence_state=str(data.get("evidence_state", "UNKNOWN")),
        source_provenance_digest=str(data.get("source_provenance_digest", "")),
    )


def _confidence_valid(value: float) -> bool:
    return 0.0 <= float(value) <= 1.0


def validate_record(record: CompiledRecord) -> list[str]:
    failures: list[str] = []
    observation = record.observation
    if observation.terminal_state not in TERMINAL_STATES:
        failures.append("invalid terminal_state")
    if any(action < 1 or action > 7 for action in observation.available_actions):
        failures.append("available action outside ACTION1-ACTION7")
    if observation.dimensions is not None:
        if len(observation.dimensions) != 2 or any(value <= 0 for value in observation.dimensions):
            failures.append("dimensions must contain two positive values")
    if not observation.frame_signature:
        failures.append("missing frame_signature")
    if record.evidence_state not in EVIDENCE_STATES:
        failures.append("invalid evidence_state")
    if not record.source_provenance_digest:
        failures.append("missing source provenance digest")

    if record.transition is not None and not _confidence_valid(record.transition.confidence):
        failures.append("transition confidence outside [0,1]")
    hypothesis_ids = [item.hypothesis_id for item in record.hypotheses]
    if len(hypothesis_ids) != len(set(hypothesis_ids)):
        failures.append("duplicate hypothesis_id")
    for hypothesis in record.hypotheses:
        if not _confidence_valid(hypothesis.confidence):
            failures.append(f"hypothesis confidence outside [0,1]: {hypothesis.hypothesis_id}")

    candidate_ids = [item.candidate_id for item in record.candidates]
    if len(candidate_ids) != len(set(candidate_ids)):
        failures.append("duplicate candidate_id")
    known_candidates = set(candidate_ids)
    for closure in record.closures:
        if closure.candidate_id not in known_candidates:
            failures.append(f"closure candidate missing: {closure.candidate_id}")
        if closure.status not in CLOSURE_STATUSES:
            failures.append(f"invalid closure status: {closure.candidate_id}")
        if not _confidence_valid(closure.confidence):
            failures.append(f"closure confidence outside [0,1]: {closure.candidate_id}")
    for obligation in record.proof_obligations:
        if obligation.status not in {"OPEN", "CLOSED"}:
            failures.append(f"invalid proof obligation status: {obligation.obligation_id}")
        if obligation.status == "OPEN" and not obligation.reopen_condition:
            failures.append(
                f"open proof obligation missing reopen condition: {obligation.obligation_id}"
            )
    return failures


def _forbidden_runtime_paths(value: Any, path: str = "$") -> list[str]:
    failures: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).casefold())
            child_path = f"{path}.{key}"
            if normalized in FORBIDDEN_RUNTIME_KEY_TOKENS:
                failures.append(child_path)
            failures.extend(_forbidden_runtime_paths(item, child_path))
    elif isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        for index, item in enumerate(value):
            failures.extend(_forbidden_runtime_paths(item, f"{path}[{index}]"))
    return failures


def forbidden_runtime_paths(value: Any) -> tuple[str, ...]:
    """Return deterministic paths whose keys violate the identity-free boundary."""

    return tuple(sorted(set(_forbidden_runtime_paths(value))))


def validate_runtime_bundle(bundle: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if bundle.get("schema_version") != SCHEMA_VERSION:
        failures.append("unexpected runtime schema version")
    if bundle.get("runtime_identity_free") is not True:
        failures.append("runtime_identity_free must be true")
    entries = bundle.get("entries")
    if not isinstance(entries, list):
        return failures + ["runtime entries must be a list"]

    ids: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            failures.append(f"entry {index} is not an object")
            continue
        entry_id = entry.get("entry_id")
        if not isinstance(entry_id, str) or not entry_id:
            failures.append(f"entry {index}: missing entry_id")
        elif entry_id in ids:
            failures.append(f"duplicate entry_id: {entry_id}")
        else:
            ids.add(entry_id)
        if entry.get("runtime_identity_free") is not True:
            failures.append(f"entry {index}: runtime_identity_free must be true")
        if not isinstance(entry.get("selectors"), Mapping) or not isinstance(
            entry.get("payload"), Mapping
        ):
            failures.append(f"entry {index}: selectors/payload must be objects")
        try:
            support = int(entry.get("support", -1))
            confidence = float(entry.get("confidence", -1.0))
        except (TypeError, ValueError):
            failures.append(f"entry {index}: invalid numeric fields")
        else:
            if support < 1:
                failures.append(f"entry {index}: support must be positive")
            if not _confidence_valid(confidence):
                failures.append(f"entry {index}: confidence outside [0,1]")
        forbidden = _forbidden_runtime_paths(entry, f"$.entries[{index}]")
        failures.extend(f"forbidden runtime identity field: {path}" for path in forbidden)

    if bundle.get("entry_count") != len(entries):
        failures.append("runtime entry_count mismatch")
    return failures


__all__ = [
    "CLOSURE_STATUSES",
    "EVIDENCE_STATES",
    "FORBIDDEN_RUNTIME_KEYS",
    "FORBIDDEN_RUNTIME_KEY_TOKENS",
    "SCHEMA_VERSION",
    "TERMINAL_STATES",
    "canonical_json",
    "digest_object",
    "forbidden_runtime_paths",
    "record_from_dict",
    "record_to_dict",
    "validate_record",
    "validate_runtime_bundle",
]
