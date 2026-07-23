"""Adapt P3 identity-free HDS evidence fixtures into typed P5 frames."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .judgment import HDSR, HDSX, HDSFrame, HDSMc, JudgmentCandidate
from .schema import digest_object


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be an object")
    return value


def _strings(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(
        value, (str, bytes, bytearray)
    ):
        raise TypeError(f"{name} must be an array")
    output = tuple(str(item).strip() for item in value)
    if any(not item for item in output):
        raise ValueError(f"{name} contains an empty value")
    return output


def _hazard_evidence(values: tuple[str, ...]) -> bool:
    hazard_terms = (
        "gameover",
        "hazard",
        "irreversible",
        "unsafe",
    )
    return any(
        any(term in value.casefold() for term in hazard_terms)
        for value in values
    )


def hds_frame_from_evidence_record(record: Mapping[str, Any]) -> HDSFrame:
    """Parse one P3 record without making a judgment or applying an effect."""

    if record.get("category") != "hds_frames":
        raise ValueError("P5 fixture category must be hds_frames")
    if record.get("runtime_identity_free") is not True:
        raise ValueError("P5 fixture must be runtime identity-free")
    payload = _mapping(record.get("payload"), "payload")
    x_value = _mapping(payload.get("x"), "payload.x")
    r_value = _mapping(payload.get("r"), "payload.r")
    mc_value = _mapping(payload.get("mc"), "payload.mc")
    candidate_families = _strings(
        x_value.get("candidate_families"),
        "payload.x.candidate_families",
    )
    observation_scope = _strings(
        x_value.get("observation_scope"),
        "payload.x.observation_scope",
    )
    evidence = _strings(r_value.get("evidence"), "payload.r.evidence")
    counter_evidence = _strings(
        r_value.get("counter_evidence"),
        "payload.r.counter_evidence",
    )
    boundary = str(mc_value.get("boundary", "")).strip()
    identity = str(mc_value.get("identity", "")).strip()
    stop_on = _strings(mc_value.get("stop_on"), "payload.mc.stop_on")
    hazard = _hazard_evidence((*evidence, *counter_evidence))
    confidence = record.get("confidence", 0.0)
    score = (
        float(confidence)
        if isinstance(confidence, (int, float))
        and not isinstance(confidence, bool)
        else 0.0
    )
    candidates = tuple(
        JudgmentCandidate(
            candidate_id=candidate_family,
            predicted_outcomes=("rendered-effect-unobserved",),
            evidence_refs=evidence[:16],
            counter_evidence_refs=counter_evidence[:16],
            preconditions=("candidate-supplied-by-fixture",),
            falsification_conditions=("rendered outcome contradicts prediction",),
            score=min(1.0, max(0.0, score)),
            risk=1.0 if hazard else 0.25,
            hazard=hazard,
            admissible=not counter_evidence,
            rejected=bool(counter_evidence),
            reversible=False,
            reason_codes=(
                ("FIXTURE_COUNTER_EVIDENCE",)
                if counter_evidence
                else ("W_X_R_MC_CLOSED",)
            ),
        )
        for candidate_family in candidate_families
    )
    frame = HDSFrame(
        frame_id="hds-frame:"
        + digest_object(
            {
                "record": record.get("record_id"),
                "semantic": identity,
                "payload": payload,
            }
        )[:24],
        purpose=str(payload.get("purpose", "")).strip(),
        x=HDSX(
            targets=("observed-environment",),
            candidate_ids=candidate_families,
            observation_scope=observation_scope,
        ),
        r=HDSR(
            relations=("evidence-supports-or-counters-candidate",),
            evidence_links=evidence,
            counter_evidence_links=counter_evidence,
        ),
        mc=HDSMc(
            identity=identity,
            boundary=boundary,
            acceptance_criteria=("admitted evidence closes X/R/Mc",),
            rejection_criteria=("hazard or contradiction invalidates acceptance",),
            stop_on=stop_on,
            max_risk=0.75,
        ),
        observation_boundary=boundary,
        candidates=candidates,
        evidence=evidence,
        counter_evidence=counter_evidence,
        risk=1.0 if hazard else 0.25,
        hazard=hazard,
        budget=1,
        unknowns=_strings(payload.get("unknowns"), "payload.unknowns"),
        stopping_conditions=(),
        contradiction=bool(counter_evidence),
        observation_available=True,
    )
    failures = frame.validate()
    if failures:
        raise ValueError(";".join(failures))
    return frame


def load_hds_frame_fixtures(path: Path) -> tuple[HDSFrame, ...]:
    frames: list[HDSFrame] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = json.loads(line)
        if not isinstance(value, Mapping):
            raise TypeError("P5 fixture record must be an object")
        frames.append(hds_frame_from_evidence_record(value))
    if not frames:
        raise ValueError("P5 fixture set is empty")
    return tuple(frames)


__all__ = ["hds_frame_from_evidence_record", "load_hds_frame_fixtures"]
