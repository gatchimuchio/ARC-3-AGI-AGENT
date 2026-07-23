"""Compile ARC3 analysis evidence into identity-free C/J/M fixture material."""

from __future__ import annotations

import argparse
import functools
import hashlib
import json
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

COMPILER_VERSION = "arc3-evidence-compiler-v1"
EVIDENCE_SCHEMA_VERSION = "arc3-identity-free-evidence-v1"

CATEGORIES = (
    "observations",
    "transitions",
    "effects",
    "hazards",
    "progress",
    "contradictions",
    "hds_frames",
    "memory_lifecycles",
)

_SENSITIVE_KEYS = frozenset(
    {
        "answer",
        "answeractions",
        "answermap",
        "baselineactions",
        "coordinate",
        "coordinates",
        "date",
        "datedownloaded",
        "filename",
        "filepath",
        "fixedactionsequence",
        "gameid",
        "hiddenstate",
        "levelid",
        "levelnumber",
        "literalcoordinate",
        "literalcoordinates",
        "localdir",
        "replay",
        "replayactions",
        "replayindex",
        "samplereplayrecords",
        "sourcestate",
        "taskid",
        "taskname",
        "title",
    }
)
_SENSITIVE_KEY_FRAGMENTS = (
    "answermap",
    "baselineaction",
    "fixedactionsequence",
    "gameid",
    "hiddenstate",
    "levelid",
    "levelnumber",
    "literalcoordinate",
    "localdir",
    "replayindex",
    "sourcestate",
    "taskid",
    "taskname",
)

_SEMANTIC_WORDS = frozenset(
    {
        "accept",
        "action",
        "active",
        "adjacent",
        "after",
        "archive",
        "available",
        "before",
        "boundary",
        "budget",
        "candidate",
        "change",
        "closed",
        "color",
        "commit",
        "completed",
        "confidence",
        "conflict",
        "contradiction",
        "counter",
        "decision",
        "delay",
        "delayed",
        "delta",
        "effect",
        "emit",
        "evidence",
        "failure",
        "falsifier",
        "frame",
        "gameover",
        "goal",
        "hazard",
        "hds",
        "hold",
        "hypothesis",
        "information",
        "invalidate",
        "lifecycle",
        "memory",
        "merge",
        "motion",
        "negative",
        "noeffect",
        "object",
        "observation",
        "open",
        "outcome",
        "pass",
        "positive",
        "prediction",
        "precondition",
        "progress",
        "proposed",
        "purpose",
        "query",
        "recovery",
        "reject",
        "relation",
        "replace",
        "reset",
        "revise",
        "risk",
        "rollback",
        "running",
        "safe",
        "split",
        "state",
        "stop",
        "structure",
        "success",
        "support",
        "suspend",
        "terminal",
        "transition",
        "uncertainty",
        "unknown",
        "unsafe",
        "version",
        "visible",
        "veto",
        "win",
        "write",
    }
)
_CAMEL_BOUNDARY = re.compile(r"([a-z])([A-Z])")
_ALPHA_TOKEN = re.compile(r"[a-zA-Z]+")
_SEMANTIC_PATTERN = re.compile(
    "|".join(
        sorted(
            (re.escape(word) for word in _SEMANTIC_WORDS),
            key=len,
            reverse=True,
        )
    ),
    re.IGNORECASE,
)

_CATEGORY_MARKERS = {
    "observations": frozenset(
        {"frame", "observation", "object", "relation", "structure", "visible"}
    ),
    "transitions": frozenset(
        {"action", "after", "before", "change", "delayed", "delta", "transition"}
    ),
    "effects": frozenset({"change", "effect", "noeffect", "outcome", "visible"}),
    "hazards": frozenset(
        {"failure", "gameover", "hazard", "recovery", "risk", "rollback", "unsafe"}
    ),
    "progress": frozenset(
        {"completed", "goal", "progress", "success", "terminal", "win"}
    ),
    "contradictions": frozenset(
        {"conflict", "contradiction", "counter", "falsifier", "negative", "reject"}
    ),
    "hds_frames": frozenset(
        {
            "boundary",
            "budget",
            "candidate",
            "decision",
            "evidence",
            "hds",
            "purpose",
            "stop",
            "suspend",
            "veto",
        }
    ),
    "memory_lifecycles": frozenset(
        {
            "active",
            "archive",
            "hypothesis",
            "invalidate",
            "lifecycle",
            "memory",
            "merge",
            "replace",
            "revise",
            "rollback",
            "split",
            "support",
            "version",
        }
    ),
}

_POSITIVE_WORDS = frozenset({"accept", "closed", "pass", "positive", "progress", "success", "win"})
_NEGATIVE_WORDS = frozenset(
    {"conflict", "contradiction", "failure", "gameover", "hazard", "negative", "reject", "unsafe"}
)
_RUNTIME_STRING_FORBIDDEN = (
    re.compile(r"(?i)(?:^|[^a-z0-9])[a-z]{1,3}\d{2}(?:-[0-9a-f]{8})?(?:$|[^a-z0-9])"),
    re.compile(r"(?i)(?:^|[^a-z0-9])(?:game|task|level)[-_ ]?(?:id|\d+)"),
    re.compile(r"(?i)(?:/mnt/|[a-z]:\\|environment_files/|\.json\b|\.py\b)"),
)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _opaque_digest(value: object, *, length: int = 24) -> str:
    """Return a decimal-only digest so task-like alphanumerics cannot appear."""

    decimal = str(int(_digest(value), 16)).zfill(78)
    return decimal[:length]


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


@functools.lru_cache(maxsize=65_536)
def _normalized_key_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _normalized_key(value: object) -> str:
    text = str(value)
    if len(text) <= 256:
        return _normalized_key_text(text)
    return re.sub(r"[^a-z0-9]", "", text.casefold())


def _extract_words(text: str) -> tuple[str, ...]:
    text = _CAMEL_BOUNDARY.sub(r"\1_\2", text)
    raw = _ALPHA_TOKEN.findall(text.casefold())
    combined = "".join(raw)
    output = set(raw) & _SEMANTIC_WORDS
    output.update(
        match.group(0).casefold()
        for match in _SEMANTIC_PATTERN.finditer(combined)
    )
    return tuple(sorted(output))


@functools.lru_cache(maxsize=65_536)
def _cached_words(value: str) -> tuple[str, ...]:
    return _extract_words(value)


def _words(value: object) -> tuple[str, ...]:
    text = str(value)
    if len(text) <= 256:
        return _cached_words(text)
    return _extract_words(text)


def _sensitive_key(key: object) -> bool:
    normalized = _normalized_key(key)
    return normalized in _SENSITIVE_KEYS or any(
        fragment in normalized for fragment in _SENSITIVE_KEY_FRAGMENTS
    )


def _bucket_number(value: int | float) -> str:
    numeric = float(value)
    if not math.isfinite(numeric):
        return "nonfinite"
    if numeric < 0.0:
        return "negative"
    if numeric == 0.0:
        return "zero"
    if numeric <= 0.25:
        return "low"
    if numeric <= 0.75:
        return "mid"
    if numeric <= 1.0:
        return "high"
    if numeric <= 8.0:
        return "small-positive"
    if numeric <= 64.0:
        return "medium-positive"
    return "large-positive"


def _dimension_bucket(value: int) -> str:
    if value <= 4:
        return "tiny"
    if value <= 12:
        return "small"
    if value <= 32:
        return "medium"
    return "large"


def _matrix_summary(value: Sequence[object]) -> tuple[str, ...] | None:
    if not value:
        return None
    rows: list[list[object]] = []
    for row in value:
        if not isinstance(row, Sequence) or isinstance(
            row, (str, bytes, bytearray)
        ):
            return None
        rows.append(list(row))
    if not rows or not all(
        all(isinstance(cell, (int, float)) and not isinstance(cell, bool) for cell in row)
        for row in rows
    ):
        return None
    widths = {len(row) for row in rows}
    if len(widths) != 1:
        return ("structure:ragged-grid",)
    width = next(iter(widths), 0)
    sample = [cell for row in rows[:64] for cell in row[:64]]
    palette = len(set(sample))
    return (
        "observation:rendered-frame",
        f"structure:height-{_dimension_bucket(len(rows))}",
        f"structure:width-{_dimension_bucket(width)}",
        f"structure:palette-{_dimension_bucket(palette)}",
    )


@dataclass(slots=True)
class _SignalAccumulator:
    signals: set[str]
    words: set[str]
    actions: set[str]
    sensitive_paths: list[str]
    truncated_collections: int = 0


def _collect_signals(
    value: object,
    accumulator: _SignalAccumulator,
    *,
    path: tuple[str, ...] = (),
    depth: int = 0,
) -> None:
    if depth > 24:
        accumulator.truncated_collections += 1
        return

    if isinstance(value, Mapping):
        keys = sorted(value, key=lambda item: str(item))
        limit = min(len(keys), 512)
        if len(keys) > limit:
            accumulator.truncated_collections += 1
            accumulator.signals.add("collection:bounded-summary")
        for raw_key in keys[:limit]:
            key = str(raw_key)
            child_path = (*path, key)
            if _sensitive_key(key):
                accumulator.sensitive_paths.append(".".join(child_path))
                continue
            key_words = _words(key)
            accumulator.words.update(key_words)
            accumulator.signals.update(f"key:{word}" for word in key_words)
            _collect_signals(
                value[raw_key],
                accumulator,
                path=child_path,
                depth=depth + 1,
            )
        return

    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        matrix = _matrix_summary(value)
        if matrix is not None:
            accumulator.signals.update(matrix)
            accumulator.words.update(("frame", "observation", "structure"))
            return
        limit = min(len(value), 128)
        if len(value) > limit:
            accumulator.truncated_collections += 1
            accumulator.signals.add("collection:bounded-summary")
        for index, item in enumerate(value[:limit]):
            _collect_signals(
                item,
                accumulator,
                path=(*path, f"item-{index}"),
                depth=depth + 1,
            )
        return

    leaf_words = set(_words(path[-1] if path else ""))
    if isinstance(value, bool):
        for word in leaf_words:
            accumulator.signals.add(f"flag:{word}:{str(value).casefold()}")
        return
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "action" in leaf_words and isinstance(value, int) and 1 <= value <= 7:
            action = f"action:{value}"
            accumulator.actions.add(action)
            accumulator.signals.add(action)
        for word in leaf_words & {
            "budget",
            "completed",
            "confidence",
            "count",
            "evidence",
            "progress",
            "risk",
            "support",
            "uncertainty",
            "version",
        }:
            accumulator.signals.add(f"numeric:{word}:{_bucket_number(value)}")
        return
    if isinstance(value, str):
        value_words = _words(value)
        accumulator.words.update(value_words)
        accumulator.signals.update(f"value:{word}" for word in value_words)


def _family_hint(relative_path: str, value: object) -> str:
    if isinstance(value, Mapping):
        game_id = value.get("game_id")
        if isinstance(game_id, str) and game_id.strip():
            return game_id.casefold()
    matches = re.findall(r"(?i)(?:^|[_/.-])([a-z]{1,3}\d{2})(?:[_/.-]|$)", relative_path)
    if matches:
        return str(matches[0]).casefold()
    if relative_path.startswith("environment_metadata/"):
        return relative_path.split("/", maxsplit=2)[1]
    return "cross-family-analysis"


def _split(group_id: str) -> str:
    bucket = int(hashlib.sha256(group_id.encode("utf-8")).hexdigest()[:8], 16) % 100
    if bucket < 70:
        return "train"
    if bucket < 85:
        return "validation"
    return "holdout"


def _polarity(words: set[str]) -> str:
    positive = bool(words & _POSITIVE_WORDS)
    negative = bool(words & _NEGATIVE_WORDS)
    if positive and negative:
        return "mixed"
    if positive:
        return "positive"
    if negative:
        return "negative"
    return "unknown"


def _signal_classes(signals: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({signal.split(":", maxsplit=1)[0] for signal in signals}))


def _body_for_category(
    category: str,
    *,
    signals: tuple[str, ...],
    words: set[str],
    actions: tuple[str, ...],
) -> dict[str, object]:
    semantic_signature = "semantic:" + _opaque_digest(signals, length=20)
    selectors: dict[str, object] = {
        "semantic_signature": semantic_signature,
        "signal_classes": _signal_classes(signals),
        "action_classes": actions,
    }
    if category == "hds_frames":
        counter_evidence = tuple(
            signal
            for signal in signals
            if any(word in signal for word in _NEGATIVE_WORDS)
        )
        return {
            "category": category,
            "selectors": selectors,
            "payload": {
                "purpose": "evaluate-observed-evidence",
                "x": {
                    "observation_scope": _signal_classes(signals),
                    "candidate_families": actions,
                },
                "r": {
                    "evidence": signals,
                    "counter_evidence": counter_evidence,
                },
                "mc": {
                    "identity": semantic_signature,
                    "boundary": "rendered-and-admitted-evidence-only",
                    "judgment_states": (
                        "PASS",
                        "REJECT",
                        "REOBSERVE",
                        "SUSPEND",
                        "STOP",
                        "ROLLBACK",
                    ),
                    "stop_on": (
                        "observed-hazard",
                        "budget-exhaustion",
                        "unclosed-evidence",
                    ),
                },
                "unknowns": ("unobserved-mechanic",)
                if "unknown" in words
                else (),
            },
        }
    if category == "memory_lifecycles":
        operations = {"ADD", "MERGE"}
        if words & {"conflict", "contradiction", "counter", "falsifier"}:
            operations.update(("SPLIT", "INVALIDATE"))
        if words & {"failure", "hazard", "negative"}:
            operations.update(("REVISE", "ARCHIVE"))
        if words & {"recovery", "rollback", "version"}:
            operations.update(("REPLACE", "ROLLBACK", "REINDEX"))
        return {
            "category": category,
            "selectors": selectors,
            "payload": {
                "operation_candidates": tuple(sorted(operations)),
                "lifecycle": "PROPOSED",
                "evidence": signals,
                "version_policy": "compare-and-swap",
                "archive_policy": "non-authoritative-unless-reactivated",
            },
        }
    return {
        "category": category,
        "selectors": selectors,
        "payload": {
            "signals": signals,
            "evidence_polarity": _polarity(words),
            "falsification_required": category
            in {"transitions", "hazards", "progress", "contradictions"},
        },
    }


def _record_categories(words: set[str]) -> tuple[str, ...]:
    return tuple(
        category
        for category in CATEGORIES
        if words & _CATEGORY_MARKERS[category]
    )


def _runtime_identity_failures(
    value: object,
    path: str = "$",
    *,
    forbidden_tokens: frozenset[str] = frozenset(),
) -> list[str]:
    failures: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            child = f"{path}.{key}"
            if _sensitive_key(key):
                failures.append(child)
            failures.extend(
                _runtime_identity_failures(
                    item,
                    child,
                    forbidden_tokens=forbidden_tokens,
                )
            )
    elif isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        for index, item in enumerate(value):
            failures.extend(
                _runtime_identity_failures(
                    item,
                    f"{path}[{index}]",
                    forbidden_tokens=forbidden_tokens,
                )
            )
    elif isinstance(value, str):
        folded = value.casefold()
        if any(pattern.search(value) for pattern in _RUNTIME_STRING_FORBIDDEN) or any(
            token in folded for token in forbidden_tokens
        ):
            failures.append(path)
    return failures


@dataclass(frozen=True, slots=True)
class SourceFile:
    kind: str
    path: Path
    relative_path: str


class _Aggregate(TypedDict):
    body: dict[str, object]
    support: int
    source_indices: list[int]
    family_split: str
    structure_split: str
    mechanism_split: str


def source_files(
    analysis_dir: Path,
    environment_dir: Path,
) -> tuple[SourceFile, ...]:
    analysis = tuple(
        SourceFile("analysis", path, f"analysis/{path.relative_to(analysis_dir).as_posix()}")
        for path in sorted(analysis_dir.rglob("*.json"))
        if path.is_file()
    )
    metadata = tuple(
        SourceFile(
            "environment_metadata",
            path,
            "environment_metadata/"
            + path.parent.parent.name
            + "/"
            + path.parent.name
            + "/metadata.json",
        )
        for path in sorted(environment_dir.glob("*/*/metadata.json"))
        if path.is_file()
    )
    return tuple(sorted((*analysis, *metadata), key=lambda item: item.relative_path))


def _environment_identity_tokens(
    sources: Sequence[SourceFile],
) -> frozenset[str]:
    tokens: set[str] = set()
    for source in sources:
        if source.kind != "environment_metadata":
            continue
        parts = source.relative_path.split("/")
        if len(parts) < 4:
            continue
        family = parts[1].casefold()
        revision = parts[2].casefold()
        tokens.update((family, revision, f"{family}-{revision}"))
    return frozenset(token for token in tokens if len(token) >= 4)


def _memory_operation_templates() -> tuple[dict[str, object], ...]:
    operations = (
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
    )
    return tuple(
        {
            "category": "memory_lifecycles",
            "selectors": {
                "semantic_signature": "memory-operation:" + operation.casefold(),
                "signal_classes": ("memory-operation",),
                "action_classes": (),
            },
            "payload": {
                "operation_candidates": (operation,),
                "lifecycle": "PROPOSED",
                "evidence": ("compiler:operation-contract",),
                "version_policy": "compare-and-swap",
                "archive_policy": "non-authoritative-unless-reactivated",
            },
        }
        for operation in operations
    )


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, values: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = "".join(_canonical_json(value) + "\n" for value in values)
    path.write_text(encoded, encoding="utf-8")


def compile_evidence(
    *,
    analysis_dir: Path,
    environment_dir: Path,
    output_dir: Path,
    manifest_dir: Path | None = None,
    source_revision: str,
    seed: int = 0,
) -> dict[str, object]:
    """Compile every source JSON into bounded identity-free evidence records."""

    if seed != 0:
        raise ValueError("P3 compiler seed is fixed at 0")
    if not analysis_dir.is_dir():
        raise FileNotFoundError(f"analysis directory not found: {analysis_dir}")
    if not environment_dir.is_dir():
        raise FileNotFoundError(f"environment directory not found: {environment_dir}")
    resolved_manifest_dir = (
        manifest_dir if manifest_dir is not None else output_dir / "manifests"
    )

    sources = source_files(analysis_dir.resolve(), environment_dir.resolve())
    if not sources:
        raise ValueError("no source JSON files found")
    forbidden_identity_tokens = _environment_identity_tokens(sources)

    aggregates: dict[tuple[str, str, str, str, str], _Aggregate] = {}
    provenance_sources: list[dict[str, object]] = []
    family_assignments: dict[str, str] = {}
    structure_assignments: dict[str, str] = {}
    mechanism_assignments: dict[str, str] = {}
    parse_error_count = 0

    for source_index, source in enumerate(sources):
        raw = source.path.read_bytes()
        source_sha = hashlib.sha256(raw).hexdigest()
        fallback_family_id = "family:" + _opaque_digest(
            _family_hint(source.relative_path, {}),
            length=16,
        )
        try:
            value = json.loads(raw.decode("utf-8-sig"))
            parse_status = "PARSED"
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            parse_error_count += 1
            family_assignments[fallback_family_id] = _split(fallback_family_id)
            provenance_sources.append(
                {
                    "source_index": source_index,
                    "kind": source.kind,
                    "path": source.relative_path,
                    "sha256": source_sha,
                    "bytes": len(raw),
                    "parse_status": "ERROR",
                    "error_type": type(error).__name__,
                    "record_ids": [],
                    "sensitive_path_count": 0,
                    "family_group": fallback_family_id,
                    "family_split": _split(fallback_family_id),
                }
            )
            continue

        accumulator = _SignalAccumulator(set(), set(), set(), [])
        _collect_signals(value, accumulator)
        signals = tuple(sorted(accumulator.signals))[:384]
        actions = tuple(sorted(accumulator.actions))
        categories = _record_categories(accumulator.words)
        family_id = "family:" + _opaque_digest(
            _family_hint(source.relative_path, value),
            length=16,
        )
        family_split = _split(family_id)
        family_assignments[family_id] = family_split
        for category in categories:
            body = _body_for_category(
                category,
                signals=signals,
                words=accumulator.words,
                actions=actions,
            )
            body_digest = _digest(body)
            structure_id = "structure:" + _opaque_digest(
                body["selectors"],
                length=16,
            )
            mechanism_id = "mechanism:" + _opaque_digest(
                actions or ("none",),
                length=16,
            )
            structure_split = _split(structure_id)
            mechanism_split = _split(mechanism_id)
            structure_assignments[structure_id] = structure_split
            mechanism_assignments[mechanism_id] = mechanism_split
            key = (
                category,
                body_digest,
                family_split,
                structure_split,
                mechanism_split,
            )
            if key not in aggregates:
                aggregates[key] = _Aggregate(
                    body=body,
                    support=0,
                    source_indices=[],
                    family_split=family_split,
                    structure_split=structure_split,
                    mechanism_split=mechanism_split,
                )
            aggregate = aggregates[key]
            aggregate["support"] += 1
            source_indices = aggregate["source_indices"]
            source_indices.append(source_index)

        provenance_sources.append(
            {
                "source_index": source_index,
                "kind": source.kind,
                "path": source.relative_path,
                "sha256": source_sha,
                "bytes": len(raw),
                "parse_status": parse_status,
                "record_ids": [],
                "sensitive_path_count": len(set(accumulator.sensitive_paths)),
                "truncated_collection_count": accumulator.truncated_collections,
                "family_group": family_id,
                "family_split": family_split,
            }
        )

    for template in _memory_operation_templates():
        body_digest = _digest(template)
        structure_id = "structure:" + _opaque_digest(
            template["selectors"],
            length=16,
        )
        mechanism_id = "mechanism:" + _opaque_digest(("none",), length=16)
        key = (
            "memory_lifecycles",
            body_digest,
            "train",
            _split(structure_id),
            _split(mechanism_id),
        )
        structure_assignments[structure_id] = _split(structure_id)
        mechanism_assignments[mechanism_id] = _split(mechanism_id)
        aggregates[key] = _Aggregate(
            body=template,
            support=1,
            source_indices=[],
            family_split="train",
            structure_split=_split(structure_id),
            mechanism_split=_split(mechanism_id),
        )

    records_by_category: dict[str, list[dict[str, object]]] = {
        category: [] for category in CATEGORIES
    }
    provenance_records: list[dict[str, object]] = []
    for key in sorted(aggregates):
        category, body_digest, family_split, structure_split, mechanism_split = key
        aggregate = aggregates[key]
        body = aggregate["body"]
        support = aggregate["support"]
        selectors = body.get("selectors")
        if not isinstance(selectors, Mapping):
            raise TypeError("evidence selectors must be a mapping")
        action_classes = selectors.get("action_classes", ())
        if not isinstance(action_classes, Sequence) or isinstance(
            action_classes, (str, bytes, bytearray)
        ):
            raise TypeError("action classes must be a sequence")
        structure_group = "structure:" + _opaque_digest(
            selectors,
            length=16,
        )
        mechanism_group = "mechanism:" + _opaque_digest(
            tuple(action_classes) or ("none",),
            length=16,
        )
        record_id = "evidence:" + _opaque_digest(
            {
                "body_digest": body_digest,
                "family_split": family_split,
                "structure_split": structure_split,
                "mechanism_split": mechanism_split,
            },
            length=24,
        )
        record = {
            "schema_version": EVIDENCE_SCHEMA_VERSION,
            "record_id": record_id,
            **dict(body),
            "support": support,
            "confidence": round(min(0.99, 0.5 + 0.05 * math.log2(max(support, 1))), 6),
            "split": {
                "family": family_split,
                "structure": structure_split,
                "action_mechanism": mechanism_split,
            },
            "split_groups": {
                "structure": structure_group,
                "action_mechanism": mechanism_group,
            },
            "runtime_identity_free": True,
        }
        failures = _runtime_identity_failures(
            record,
            forbidden_tokens=forbidden_identity_tokens,
        )
        if failures:
            raise ValueError(
                f"runtime identity violation in {record_id}: {';'.join(failures)}"
            )
        records_by_category[category].append(record)
        source_indices = sorted(set(aggregate["source_indices"]))
        provenance_records.append(
            {
                "record_id": record_id,
                "source_indices": source_indices,
                "body_digest": body_digest,
                "split": {
                    "family": family_split,
                    "structure": structure_split,
                    "action_mechanism": mechanism_split,
                },
            }
        )
        for source_index in source_indices:
            source_record_ids_value = provenance_sources[source_index]["record_ids"]
            if not isinstance(source_record_ids_value, list):
                raise TypeError("source record_ids must be a list")
            source_record_ids_value.append(record_id)

    for provenance_source in provenance_sources:
        record_ids = provenance_source["record_ids"]
        if not isinstance(record_ids, list):
            raise TypeError("source record_ids must be a list")
        provenance_source["record_ids"] = sorted(
            set(str(item) for item in record_ids)
        )
        provenance_source["extraction_status"] = (
            "MATERIALIZED"
            if provenance_source["record_ids"]
            else "ACCOUNTED_NO_RUNTIME_MATERIAL"
        )

    output_hashes: dict[str, str] = {}
    category_counts: dict[str, int] = {}
    for category in CATEGORIES:
        records = sorted(
            records_by_category[category],
            key=lambda item: str(item["record_id"]),
        )
        relative = f"{category}/records.jsonl"
        destination = output_dir / relative
        _write_jsonl(destination, records)
        output_hashes[f"datasets/{relative}"] = _file_digest(destination)
        category_counts[category] = len(records)

    holdout_manifest = {
        "schema_version": "arc3-holdout-manifest-v1",
        "runtime_use": "TRAINING_EVALUATION_ONLY",
        "family_groups": dict(sorted(family_assignments.items())),
        "structure_groups": dict(sorted(structure_assignments.items())),
        "action_mechanism_groups": dict(sorted(mechanism_assignments.items())),
        "perturbations": {
            "layout": "required",
            "color": "required",
            "position": "required",
        },
        "contamination_rule": "each opaque group maps to exactly one split",
    }
    holdout_path = output_dir / "holdout_families" / "manifest.json"
    _write_json(holdout_path, holdout_manifest)
    output_hashes["datasets/holdout_families/manifest.json"] = _file_digest(
        holdout_path
    )

    provenance_manifest = {
        "schema_version": "arc3-evidence-provenance-v1",
        "runtime_use": "FORBIDDEN",
        "source_revision": source_revision,
        "sources": provenance_sources,
        "records": sorted(provenance_records, key=lambda item: str(item["record_id"])),
    }
    provenance_path = resolved_manifest_dir / "provenance_manifest.json"
    _write_json(provenance_path, provenance_manifest)

    runtime_failures: list[str] = []
    for category in CATEGORIES:
        for record in records_by_category[category]:
            runtime_failures.extend(
                _runtime_identity_failures(
                    record,
                    forbidden_tokens=forbidden_identity_tokens,
                )
            )
    identity_audit = {
        "schema_version": "arc3-identity-free-audit-v1",
        "checked_categories": CATEGORIES,
        "checked_record_count": sum(category_counts.values()),
        "forbidden_path_count": len(runtime_failures),
        "forbidden_paths": sorted(set(runtime_failures)),
        "forbidden_identity_token_count": len(forbidden_identity_tokens),
        "forbidden_identity_token_digest": _digest(
            sorted(forbidden_identity_tokens)
        ),
        "provenance_manifest_excluded_from_runtime": True,
        "runtime_identity_free": not runtime_failures,
    }
    identity_path = resolved_manifest_dir / "identity_free_audit.json"
    _write_json(identity_path, identity_audit)
    output_hashes["manifests/identity_free_audit.json"] = _file_digest(identity_path)

    source_inventory_digest = _digest(
        [
            {
                "kind": item["kind"],
                "path": item["path"],
                "sha256": item["sha256"],
                "bytes": item["bytes"],
            }
            for item in provenance_sources
        ]
    )
    dataset_manifest = {
        "schema_version": "arc3-evidence-dataset-manifest-v1",
        "compiler_version": COMPILER_VERSION,
        "compiler_seed": seed,
        "source_revision": source_revision,
        "source_inventory_digest": source_inventory_digest,
        "source_file_count": len(sources),
        "source_parse_error_count": parse_error_count,
        "source_accounted_count": len(provenance_sources),
        "source_materialized_count": sum(
            item["extraction_status"] == "MATERIALIZED"
            for item in provenance_sources
        ),
        "source_no_runtime_material_count": sum(
            item["extraction_status"] == "ACCOUNTED_NO_RUNTIME_MATERIAL"
            for item in provenance_sources
        ),
        "category_counts": category_counts,
        "runtime_record_count": sum(category_counts.values()),
        "fixture_sets": {
            "C": (
                "observations",
                "transitions",
                "effects",
                "hazards",
                "progress",
                "contradictions",
            ),
            "J": ("hds_frames",),
            "M": ("memory_lifecycles",),
        },
        "output_hashes": dict(sorted(output_hashes.items())),
        "runtime_identity_free": not runtime_failures,
        "provenance_runtime_use": "FORBIDDEN",
    }
    manifest_path = resolved_manifest_dir / "dataset_manifest.json"
    _write_json(manifest_path, dataset_manifest)
    return dataset_manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compile ARC3 analysis and sample metadata into identity-free fixtures."
    )
    parser.add_argument("--analysis-dir", type=Path, required=True)
    parser.add_argument("--environment-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--manifest-dir", type=Path)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--seed", type=int, default=0)
    return parser


def main() -> int:
    args = _parser().parse_args()
    manifest = compile_evidence(
        analysis_dir=args.analysis_dir,
        environment_dir=args.environment_dir,
        output_dir=args.output_dir,
        manifest_dir=args.manifest_dir,
        source_revision=args.source_revision,
        seed=args.seed,
    )
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CATEGORIES",
    "COMPILER_VERSION",
    "EVIDENCE_SCHEMA_VERSION",
    "SourceFile",
    "compile_evidence",
    "main",
    "source_files",
]
