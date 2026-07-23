"""Compile P3 identity-free fixtures into symbolic P-A and trained P-B bodies."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .instruction_body import (
    INSTRUCTION_BODY_SCHEMA_VERSION,
    PARAMETRIC_FEATURES,
    PARAMETRIC_FORMAT_ID,
    PARAMETRIC_HEADS,
    SYMBOLIC_FORMAT_ID,
    instruction_body_from_mapping,
    seal_instruction_bundle,
)
from .protocol import InstructionBodyContract
from .schema import canonical_json, digest_object

INSTRUCTION_COMPILER_VERSION = "arc3-instruction-compiler-v1"
FIXED_SEED = 0
_CATEGORIES = (
    "observations",
    "transitions",
    "effects",
    "hazards",
    "progress",
    "contradictions",
)


def _decimal_digest(value: object, *, length: int = 78) -> str:
    digits = str(int(digest_object(value), 16)).zfill(78)
    return digits[:length]


def _bounded(value: float) -> float:
    return round(min(1.0, max(0.0, float(value))), 9)


def _sigmoid(value: float) -> float:
    if value >= 0.0:
        exponential = math.exp(-min(value, 60.0))
        return 1.0 / (1.0 + exponential)
    exponential = math.exp(max(value, -60.0))
    return exponential / (1.0 + exponential)


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected object: {path}")
    return value


def _load_records(dataset_dir: Path) -> tuple[dict[str, Any], ...]:
    records: list[dict[str, Any]] = []
    for category in _CATEGORIES:
        path = dataset_dir / category / "records.jsonl"
        if not path.is_file():
            raise FileNotFoundError(f"P3 category missing: {path}")
        for line in path.read_text(encoding="utf-8").splitlines():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise TypeError(f"P3 record must be an object: {path}")
            if value.get("category") != category:
                raise ValueError(f"P3 category mismatch: {path}")
            if value.get("runtime_identity_free") is not True:
                raise ValueError(f"P3 runtime identity flag missing: {path}")
            records.append(value)
    return tuple(sorted(records, key=lambda item: str(item["record_id"])))


def _signals(record: Mapping[str, Any]) -> frozenset[str]:
    payload = record.get("payload")
    if not isinstance(payload, Mapping):
        return frozenset()
    values = payload.get("signals", ())
    if not isinstance(values, Sequence) or isinstance(
        values, (str, bytes, bytearray)
    ):
        return frozenset()
    return frozenset(str(item).casefold() for item in values)


def _action_ids(record: Mapping[str, Any]) -> tuple[int, ...]:
    selectors = record.get("selectors")
    if not isinstance(selectors, Mapping):
        return ()
    values = selectors.get("action_classes", ())
    if not isinstance(values, Sequence) or isinstance(
        values, (str, bytes, bytearray)
    ):
        return ()
    actions: set[int] = set()
    for value in values:
        text = str(value)
        if not text.startswith("action:"):
            continue
        try:
            action_id = int(text.split(":", maxsplit=1)[1])
        except ValueError:
            continue
        if 1 <= action_id <= 7:
            actions.add(action_id)
    return tuple(sorted(actions))


def _contains(signals: frozenset[str], *terms: str) -> bool:
    return any(
        any(term in signal for term in terms)
        for signal in signals
    )


def _record_feature_vector(
    record: Mapping[str, Any],
    action_id: int,
) -> tuple[float, ...]:
    signals = _signals(record)
    actions = _action_ids(record)
    return (
        1.0,
        action_id / 7.0,
        len(actions) / 7.0,
        float(_contains(signals, "object", "entity")),
        float(_contains(signals, "relation", "adjacent")),
        float(_contains(signals, "visible", "effect", "change")),
        float(_contains(signals, "before", "after", "previous", "transition")),
        float(_contains(signals, "action", "transition", "history")),
        float(_contains(signals, "memory", "support", "hypothesis")),
        float(_contains(signals, "failure", "hazard", "unsafe", "gameover")),
        float(_contains(signals, "active", "running", "progress")),
        float(_contains(signals, "structure", "frame", "observation")),
    )


def _record_targets(record: Mapping[str, Any]) -> tuple[float, ...]:
    category = str(record.get("category", ""))
    signals = _signals(record)
    payload = record.get("payload")
    polarity = (
        str(payload.get("evidence_polarity", "unknown"))
        if isinstance(payload, Mapping)
        else "unknown"
    )
    effect = float(
        category in {"effects", "transitions"}
        or _contains(signals, "effect", "visible", "change")
    )
    progress = float(
        category == "progress"
        and polarity not in {"negative", "unknown"}
    )
    hazard = float(
        category == "hazards"
        or _contains(signals, "failure", "hazard", "unsafe", "gameover")
    )
    information_gain = float(
        category in {"observations", "transitions", "contradictions"}
        or _contains(signals, "evidence", "falsifier", "uncertainty")
    )
    prior_score = (
        (0.4 * effect)
        + (0.35 * progress)
        + (0.25 * information_gain)
        - (0.55 * hazard)
    )
    candidate_prior = float(prior_score >= 0.35)
    confidence = record.get("confidence", 0.5)
    confidence_value = (
        float(confidence)
        if isinstance(confidence, (int, float))
        and not isinstance(confidence, bool)
        else 0.5
    )
    uncertainty = float(
        polarity in {"mixed", "unknown"}
        or confidence_value < 0.65
    )
    return (
        effect,
        progress,
        hazard,
        information_gain,
        candidate_prior,
        uncertainty,
    )


@dataclass(frozen=True, slots=True)
class _TrainingExample:
    record_id: str
    split: str
    features: tuple[float, ...]
    targets: tuple[float, ...]


def _training_examples(
    records: Sequence[Mapping[str, Any]],
) -> tuple[_TrainingExample, ...]:
    examples: list[_TrainingExample] = []
    for record in records:
        split_value = record.get("split")
        split = (
            str(split_value.get("family", ""))
            if isinstance(split_value, Mapping)
            else ""
        )
        for action_id in _action_ids(record):
            examples.append(
                _TrainingExample(
                    record_id=str(record["record_id"]),
                    split=split,
                    features=_record_feature_vector(record, action_id),
                    targets=_record_targets(record),
                )
            )
    return tuple(
        sorted(
            examples,
            key=lambda item: (
                item.split,
                item.record_id,
                item.features[1],
            ),
        )
    )


def _binary_cross_entropy(
    weights: Sequence[Sequence[float]],
    examples: Sequence[_TrainingExample],
) -> float:
    if not examples:
        raise ValueError("metric requires at least one example")
    total = 0.0
    count = 0
    for example in examples:
        for head_index, row in enumerate(weights):
            probability = min(
                1.0 - 1e-12,
                max(
                    1e-12,
                    _sigmoid(
                        sum(
                            weight * feature
                            for weight, feature in zip(
                                row,
                                example.features,
                                strict=True,
                            )
                        )
                    ),
                ),
            )
            target = example.targets[head_index]
            total -= (
                target * math.log(probability)
                + (1.0 - target) * math.log(1.0 - probability)
            )
            count += 1
    return total / count


def _train_sigmoid_matrix(
    examples: Sequence[_TrainingExample],
    *,
    epochs: int = 120,
    learning_rate: float = 0.2,
    l2: float = 0.001,
) -> tuple[tuple[tuple[float, ...], ...], dict[str, float | int]]:
    train = tuple(item for item in examples if item.split == "train")
    holdout = tuple(item for item in examples if item.split == "holdout")
    validation = tuple(item for item in examples if item.split == "validation")
    if not train or not holdout or not validation:
        raise ValueError("P-B requires non-empty train/validation/holdout examples")

    weights = [
        [0.0 for _ in PARAMETRIC_FEATURES]
        for _ in PARAMETRIC_HEADS
    ]
    baseline_train = _binary_cross_entropy(weights, train)
    baseline_holdout = _binary_cross_entropy(weights, holdout)
    for _ in range(epochs):
        gradients = [
            [0.0 for _ in PARAMETRIC_FEATURES]
            for _ in PARAMETRIC_HEADS
        ]
        for example in train:
            for head_index, row in enumerate(weights):
                probability = _sigmoid(
                    sum(
                        weight * feature
                        for weight, feature in zip(
                            row,
                            example.features,
                            strict=True,
                        )
                    )
                )
                error = probability - example.targets[head_index]
                for feature_index, feature in enumerate(example.features):
                    gradients[head_index][feature_index] += error * feature
        scale = 1.0 / len(train)
        for head_index, row in enumerate(weights):
            for feature_index, weight in enumerate(row):
                gradient = (
                    gradients[head_index][feature_index] * scale
                    + (l2 * weight)
                )
                row[feature_index] = weight - (learning_rate * gradient)

    rounded = tuple(
        tuple(round(value, 12) for value in row)
        for row in weights
    )
    trained_train = _binary_cross_entropy(rounded, train)
    trained_validation = _binary_cross_entropy(rounded, validation)
    trained_holdout = _binary_cross_entropy(rounded, holdout)
    if trained_train >= baseline_train:
        raise ValueError("P-B training did not improve training loss")
    if trained_holdout > baseline_holdout:
        raise ValueError("P-B training regressed beyond holdout baseline")
    metrics: dict[str, float | int] = {
        "epochs": epochs,
        "learning_rate": learning_rate,
        "l2": l2,
        "baseline_train_bce": round(baseline_train, 9),
        "trained_train_bce": round(trained_train, 9),
        "trained_validation_bce": round(trained_validation, 9),
        "baseline_holdout_bce": round(baseline_holdout, 9),
        "trained_holdout_bce": round(trained_holdout, 9),
        "training_example_count": len(train),
        "validation_example_count": len(validation),
        "holdout_example_count": len(holdout),
    }
    return rounded, metrics


def _mean(values: Iterable[float]) -> float:
    sequence = tuple(values)
    return sum(sequence) / len(sequence) if sequence else 0.0


def _control_profiles(
    records: Sequence[Mapping[str, Any]],
    *,
    variant: str,
) -> list[dict[str, object]]:
    targets = tuple(_record_targets(record) for record in records)
    effect = _mean(item[0] for item in targets)
    progress = _mean(item[1] for item in targets)
    hazard = _mean(item[2] for item in targets)
    information = _mean(item[3] for item in targets)
    uncertainty = _mean(item[5] for item in targets)
    variant_shift = 0.03 if variant == "parametric" else 0.0
    source = f"compiled-control-profile:{variant}"
    return [
        {
            "mode": "REOBSERVE",
            "preconditions": ["OBSERVATION_CHANNEL_AVAILABLE"],
            "expected_progress": 0.0,
            "information_gain": _bounded(information + uncertainty),
            "expected_risk": 0.0,
            "repetition_cost": 0.0,
            "rollback_cost": 0.0,
            "falsification_conditions": ["observation channel unavailable"],
            "provenance": [source],
        },
        {
            "mode": "SUSPEND",
            "preconditions": ["OPEN_PROOF_OBLIGATION"],
            "expected_progress": 0.0,
            "information_gain": _bounded(uncertainty),
            "expected_risk": 0.0,
            "repetition_cost": 0.0,
            "rollback_cost": 0.0,
            "falsification_conditions": ["all closure terms become observed"],
            "provenance": [source],
        },
        {
            "mode": "STOP",
            "preconditions": ["TERMINAL_OR_BUDGET_BOUNDARY"],
            "expected_progress": _bounded(progress),
            "information_gain": 0.0,
            "expected_risk": _bounded(hazard),
            "repetition_cost": 0.0,
            "rollback_cost": 0.0,
            "falsification_conditions": ["safe bounded work remains"],
            "provenance": [source],
        },
        {
            "mode": "ROLLBACK",
            "preconditions": ["REVERSIBLE_FAILURE_EVIDENCE"],
            "expected_progress": 0.0,
            "information_gain": _bounded(information),
            "expected_risk": _bounded(hazard + variant_shift),
            "repetition_cost": 0.0,
            "rollback_cost": _bounded(hazard),
            "falsification_conditions": ["no reversible checkpoint exists"],
            "provenance": [source],
        },
        {
            "mode": "PLAN",
            "preconditions": ["MULTIPLE_HYPOTHESES_AVAILABLE"],
            "expected_progress": _bounded(progress + (0.2 * effect)),
            "information_gain": _bounded(information + variant_shift),
            "expected_risk": _bounded(hazard),
            "repetition_cost": _bounded(uncertainty * 0.2),
            "rollback_cost": _bounded(hazard * 0.5),
            "falsification_conditions": ["no bounded plan can be grounded"],
            "provenance": [source],
        },
    ]


def _contract(
    *,
    format_id: str,
    body_version: str,
    provenance_digest: str,
) -> dict[str, object]:
    return InstructionBodyContract(
        format_id=format_id,
        schema_version=INSTRUCTION_BODY_SCHEMA_VERSION,
        body_version=body_version,
        content_digest="PENDING",
        provenance_digest=provenance_digest,
        bound=True,
    ).to_dict()


def _compile_symbolic(
    records: Sequence[Mapping[str, Any]],
    *,
    provenance_digest: str,
    dataset_digest: str,
) -> dict[str, Any]:
    by_action: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    concepts: set[str] = set()
    for record in records:
        signals = _signals(record)
        for concept in (
            "object",
            "role",
            "feature",
            "relation",
            "action",
            "effect",
            "transition",
            "precondition",
            "goal",
            "hazard",
            "falsifier",
            "support",
            "contradiction",
            "confidence",
            "structure",
            "observation",
        ):
            if _contains(signals, concept):
                concepts.add(concept)
        for action_id in _action_ids(record):
            by_action[action_id].append(record)

    nodes = [
        {
            "node_id": f"concept:{concept}",
            "node_type": concept,
        }
        for concept in sorted(concepts)
    ]
    nodes.extend(
        {
            "node_id": f"action-class:{action_id}",
            "node_type": "action",
        }
        for action_id in range(1, 8)
    )
    rules: list[dict[str, object]] = []
    edges: list[dict[str, str]] = []
    for action_id in range(1, 8):
        action_records = tuple(by_action[action_id])
        if not action_records:
            raise ValueError(f"P-A action evidence missing: {action_id}")
        targets = tuple(_record_targets(record) for record in action_records)
        effect = _mean(item[0] for item in targets)
        progress = _mean(item[1] for item in targets)
        hazard = _mean(item[2] for item in targets)
        information = _mean(item[3] for item in targets)
        prior = _mean(item[4] for item in targets)
        uncertainty = _mean(item[5] for item in targets)
        support = sum(int(record.get("support", 1)) for record in action_records)
        contradiction = sum(
            int(record.get("support", 1))
            for record in action_records
            if record.get("category") == "contradictions"
        )
        confidence = _mean(float(record.get("confidence", 0.5)) for record in action_records)
        evidence_refs = sorted(
            {
                str(record["record_id"])
                for record in action_records
            }
        )[:64]
        rule_id = "rule:" + _decimal_digest(
            {
                "action": action_id,
                "targets": targets,
                "evidence": evidence_refs,
            },
            length=24,
        )
        predicted_effect = (
            "VISIBLE_STATE_CHANGE"
            if effect >= 0.5
            else "NO_VISIBLE_CHANGE"
        )
        rules.append(
            {
                "rule_id": rule_id,
                "action_id": action_id,
                "predicted_effects": [predicted_effect],
                "progress_likelihood": _bounded(progress),
                "hazard_likelihood": _bounded(hazard),
                "information_gain": _bounded(information),
                "candidate_prior": _bounded(prior),
                "uncertainty": _bounded(uncertainty),
                "support": support,
                "contradiction": contradiction,
                "confidence": _bounded(confidence),
                "preconditions": [
                    f"ACTION{action_id}_AVAILABLE",
                    "RENDERED_OBSERVATION_PRESENT",
                ],
                "falsification_conditions": [
                    "action unavailable",
                    "observed rendered effect contradicts prediction",
                    "repeated no-effect exceeds evidence support",
                ],
                "selectors": [
                    "available-action",
                    "rendered-structure",
                    "bounded-context",
                ],
                "evidence_refs": evidence_refs,
            }
        )
        edges.append(
            {
                "source": f"action-class:{action_id}",
                "relation": "predicts",
                "target": f"concept:{'effect' if 'effect' in concepts else 'transition'}",
            }
        )

    body_version = "p-a-symbolic-v1"
    base: dict[str, Any] = {
        "schema_version": INSTRUCTION_BODY_SCHEMA_VERSION,
        "format_id": SYMBOLIC_FORMAT_ID,
        "body_version": body_version,
        "content_digest": "",
        "runtime_identity_free": True,
        "provenance_digest": provenance_digest,
        "contract": _contract(
            format_id=SYMBOLIC_FORMAT_ID,
            body_version=body_version,
            provenance_digest=provenance_digest,
        ),
        "compile": {
            "compiler_version": INSTRUCTION_COMPILER_VERSION,
            "seed": FIXED_SEED,
            "dataset_digest": dataset_digest,
            "record_count": len(records),
            "method": "support-weighted-symbolic-rule-graph",
        },
        "payload": {
            "graph": {
                "nodes": nodes,
                "edges": edges,
            },
            "rules": rules,
            "control_profiles": _control_profiles(
                records,
                variant="symbolic",
            ),
        },
    }
    return seal_instruction_bundle(base)


def _compile_parametric(
    records: Sequence[Mapping[str, Any]],
    *,
    provenance_digest: str,
    dataset_digest: str,
) -> tuple[dict[str, Any], dict[str, float | int]]:
    examples = _training_examples(records)
    weights, metrics = _train_sigmoid_matrix(examples)
    body_version = "p-b-parametric-v1"
    training_record_ids = sorted(
        {
            item.record_id
            for item in examples
            if item.split == "train"
        }
    )
    holdout_record_ids = sorted(
        {
            item.record_id
            for item in examples
            if item.split == "holdout"
        }
    )
    parameter_digest = "parameter-matrix:" + _decimal_digest(
        weights,
        length=40,
    )
    base: dict[str, Any] = {
        "schema_version": INSTRUCTION_BODY_SCHEMA_VERSION,
        "format_id": PARAMETRIC_FORMAT_ID,
        "body_version": body_version,
        "content_digest": "",
        "runtime_identity_free": True,
        "provenance_digest": provenance_digest,
        "contract": _contract(
            format_id=PARAMETRIC_FORMAT_ID,
            body_version=body_version,
            provenance_digest=provenance_digest,
        ),
        "compile": {
            "compiler_version": INSTRUCTION_COMPILER_VERSION,
            "seed": FIXED_SEED,
            "dataset_digest": dataset_digest,
            "method": "full-batch-multi-head-sigmoid-gradient-descent",
            "training_record_digest": "training-records:"
            + _decimal_digest(training_record_ids, length=40),
            "holdout_record_digest": "holdout-records:"
            + _decimal_digest(holdout_record_ids, length=40),
            "metrics": metrics,
        },
        "payload": {
            "model": {
                "architecture": "identity-free-feature-vector-to-six-sigmoid-heads",
                "activation": "sigmoid",
                "feature_names": list(PARAMETRIC_FEATURES),
                "heads": list(PARAMETRIC_HEADS),
                "weights": [list(row) for row in weights],
                "parameter_count": sum(len(row) for row in weights),
                "parameter_digest": parameter_digest,
                "action_preconditions": [
                    "ACTION{action_id}_AVAILABLE",
                    "RENDERED_OBSERVATION_PRESENT",
                ],
                "action_falsification_conditions": [
                    "action unavailable",
                    "held-out rendered effect contradicts prediction",
                ],
                "training_record_count": len(training_record_ids),
                "holdout_record_count": len(holdout_record_ids),
            },
            "control_profiles": _control_profiles(
                records,
                variant="parametric",
            ),
        },
    }
    return seal_instruction_bundle(base), metrics


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as destination:
        destination.write(
            json.dumps(
                value,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )


def compile_instruction_bodies(
    *,
    dataset_dir: Path,
    dataset_manifest_path: Path,
    output_dir: Path,
    seed: int = FIXED_SEED,
) -> dict[str, Any]:
    """Compile and train both P implementations from P3 runtime material."""

    if seed != FIXED_SEED:
        raise ValueError("P4 instruction compiler seed is fixed at 0")
    manifest = _load_json(dataset_manifest_path)
    if manifest.get("runtime_identity_free") is not True:
        raise ValueError("P3 dataset identity audit did not pass")
    if int(manifest.get("source_parse_error_count", -1)) != 0:
        raise ValueError("P3 dataset contains parse errors")
    records = _load_records(dataset_dir)
    if len(records) != sum(
        int(manifest["category_counts"][category])
        for category in _CATEGORIES
    ):
        raise ValueError("P3 C fixture count mismatch")

    dataset_digest = "dataset:" + _decimal_digest(
        {
            "source_inventory_digest": manifest["source_inventory_digest"],
            "category_counts": manifest["category_counts"],
            "output_hashes": manifest["output_hashes"],
        },
        length=50,
    )
    provenance_digest = "evidence-provenance:" + _decimal_digest(
        manifest["source_inventory_digest"],
        length=50,
    )
    symbolic = _compile_symbolic(
        records,
        provenance_digest=provenance_digest,
        dataset_digest=dataset_digest,
    )
    parametric, metrics = _compile_parametric(
        records,
        provenance_digest=provenance_digest,
        dataset_digest=dataset_digest,
    )
    symbolic_path = output_dir / "p_a_symbolic_v1.json"
    parametric_path = output_dir / "p_b_parametric_v1.json"
    _write_json(symbolic_path, symbolic)
    _write_json(parametric_path, parametric)

    symbolic_body = instruction_body_from_mapping(symbolic)
    parametric_body = instruction_body_from_mapping(parametric)
    output_manifest: dict[str, Any] = {
        "schema_version": "arc3-p4-instruction-body-manifest-v1",
        "compiler_version": INSTRUCTION_COMPILER_VERSION,
        "seed": seed,
        "runtime_use": "BUNDLE_INDEX_ONLY",
        "dataset_digest": dataset_digest,
        "provenance_digest": provenance_digest,
        "source_record_count": len(records),
        "bundles": {
            "P-A": {
                "filename": symbolic_path.name,
                "format_id": symbolic_body.format_id,
                "body_version": symbolic_body.body_version,
                "content_digest": symbolic_body.digest(),
                "sha256": _file_digest(symbolic_path),
            },
            "P-B": {
                "filename": parametric_path.name,
                "format_id": parametric_body.format_id,
                "body_version": parametric_body.body_version,
                "content_digest": parametric_body.digest(),
                "sha256": _file_digest(parametric_path),
                "training_metrics": metrics,
            },
        },
    }
    manifest_path = output_dir / "manifest.json"
    _write_json(manifest_path, output_manifest)
    return output_manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compile P3 fixtures into P-A and trained P-B bundles."
    )
    parser.add_argument("--dataset-dir", type=Path, required=True)
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=FIXED_SEED)
    return parser


def main() -> int:
    args = _parser().parse_args()
    manifest = compile_instruction_bodies(
        dataset_dir=args.dataset_dir,
        dataset_manifest_path=args.dataset_manifest,
        output_dir=args.output_dir,
        seed=args.seed,
    )
    print(canonical_json(manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "FIXED_SEED",
    "INSTRUCTION_COMPILER_VERSION",
    "compile_instruction_bodies",
    "main",
]
