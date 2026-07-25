"""Compile legacy ARC3 evidence into development-only P10 analysis memory.

This module deliberately sits outside the runtime instruction-body path.  It
retains task identity and source relationships for development accounting,
while every emitted artifact is marked as forbidden runtime input.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .schema import digest_object

DEVELOPMENT_ANALYSIS_SCHEMA_VERSION = "arc3-p10-development-analysis-v1"
RUNTIME_USE = "FORBIDDEN"

LEDGER_FILENAME = "LEGACY_LEVEL_ANALYSIS_LEDGER.json"
RECONCILIATION_FILENAME = "ANALYSIS_RECONCILIATION_MATRIX.json"
COVERAGE_FILENAME = "CAPABILITY_COVERAGE_MATRIX.json"
QUEUE_FILENAME = "CAPABILITY_BUILD_QUEUE.json"

CORE_LEGACY_SOURCES = {
    "strict_ledger": "analysis/arc3_strict_level_analysis_ledger_latest.json",
    "mechanics_inventory": (
        "analysis/arc3_full_task_mechanics_inventory_latest.json"
    ),
    "capability_clusters": (
        "analysis/arc3_full_task_capability_cluster_matrix_latest.json"
    ),
    "frontier_atlas": (
        "analysis/arc3_current_frontier_mechanics_atlas_latest.json"
    ),
    "level_atlas": "analysis/arc3_level_atlas.json",
}

DEFAULT_CURRENT_REPORTS = (
    "evidence/p10/ft09_hybrid_active_compact.json",
    "evidence/p10/lp85_hybrid_compact.json",
    "evidence/p10/tr87_hybrid_compact.json",
    (
        "evidence/p10/p_update/iteration_14_regression/"
        "p10_active_post_promotion_su15.json"
    ),
    (
        "evidence/p10/p_update/iteration_21_regression/"
        "p10_active_post_promotion_ka59.json"
    ),
)

REQUIRED_LEDGER_FIELDS = (
    "game_id",
    "level",
    "frontier",
    "mechanics_id",
    "operation_type",
    "state_variables",
    "local_effect_classes",
    "failure_signature",
    "required_capabilities",
    "recommended_components",
    "progress_blocker",
    "hazard_blocker",
    "promotion_blocker",
    "evidence_refs",
    "legacy_confidence",
    "current_validation_status",
)

VALID_RECONCILIATION_STATUSES = (
    "CONFIRMED",
    "PARTIALLY_CONFIRMED",
    "CONTRADICTED",
    "STALE",
    "UNOBSERVED",
)

PROMOTION_TIERS = ("LOCAL_PROBE", "CLUSTER_STABLE", "COMPOSABLE")


class LegacySourceDriftError(ValueError):
    """Raised when a legacy source no longer matches the frozen P3 manifest."""


def _json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _legacy_source_path(
    legacy_repository_root: Path,
    relative_path: str,
) -> Path:
    root = legacy_repository_root.resolve()
    path = (root / relative_path).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise LegacySourceDriftError(
            f"LEGACY_SOURCE_PATH_ESCAPE:{relative_path}"
        ) from error
    return path


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _content_bound(
    artifact_type: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    body = dict(payload)
    body["artifact_type"] = artifact_type
    body["development_only"] = True
    body["runtime_use"] = RUNTIME_USE
    body["schema_version"] = DEVELOPMENT_ANALYSIS_SCHEMA_VERSION
    return {
        **body,
        "content_digest": (
            f"{artifact_type}:" + digest_object(body)
        ),
    }


def _source_index(
    provenance: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    raw_sources = provenance.get("sources")
    if not isinstance(raw_sources, Sequence) or isinstance(
        raw_sources,
        (str, bytes, bytearray),
    ):
        raise TypeError("provenance sources must be an array")
    sources: dict[str, Mapping[str, Any]] = {}
    for raw in raw_sources:
        if not isinstance(raw, Mapping):
            raise TypeError("provenance source must be an object")
        path = str(raw.get("path", ""))
        if not path or path in sources:
            raise ValueError("PROVENANCE_SOURCE_PATH_INVALID_OR_DUPLICATE")
        sources[path] = raw
    return sources


def _verified_legacy_json(
    *,
    legacy_repository_root: Path,
    relative_path: str,
    source_index: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    expected = source_index.get(relative_path)
    if expected is None:
        raise LegacySourceDriftError(
            f"LEGACY_SOURCE_NOT_FROZEN:{relative_path}"
        )
    path = _legacy_source_path(legacy_repository_root, relative_path)
    if not path.is_file():
        raise FileNotFoundError(path)
    actual_digest = _file_digest(path)
    expected_digest = str(expected.get("sha256", ""))
    if actual_digest != expected_digest:
        raise LegacySourceDriftError(
            "LEGACY_SOURCE_DIGEST_DRIFT:"
            f"{relative_path}:{expected_digest}:{actual_digest}"
        )
    return _json_object(path)


def _verified_analysis_source_descriptors(
    *,
    legacy_repository_root: Path,
    source_index: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Verify every P3-accounted analysis source before compiling relations."""

    descriptors: list[dict[str, Any]] = []
    for relative_path, source in source_index.items():
        if str(source.get("kind", "")) != "analysis":
            continue
        parse_status = str(source.get("parse_status", ""))
        extraction_status = str(source.get("extraction_status", ""))
        if parse_status != "PARSED" or extraction_status != "MATERIALIZED":
            raise LegacySourceDriftError(
                "LEGACY_ANALYSIS_SOURCE_NOT_MATERIALIZED:"
                f"{relative_path}:{parse_status}:{extraction_status}"
            )
        path = _legacy_source_path(
            legacy_repository_root,
            relative_path,
        )
        if not path.is_file():
            raise LegacySourceDriftError(
                f"LEGACY_ANALYSIS_SOURCE_MISSING:{relative_path}"
            )
        expected_bytes = int(source.get("bytes", -1))
        actual_bytes = path.stat().st_size
        if actual_bytes != expected_bytes:
            raise LegacySourceDriftError(
                "LEGACY_ANALYSIS_SOURCE_SIZE_DRIFT:"
                f"{relative_path}:{expected_bytes}:{actual_bytes}"
            )
        expected_digest = str(source.get("sha256", ""))
        actual_digest = _file_digest(path)
        if actual_digest != expected_digest:
            raise LegacySourceDriftError(
                "LEGACY_ANALYSIS_SOURCE_DIGEST_DRIFT:"
                f"{relative_path}:{expected_digest}:{actual_digest}"
            )
        descriptors.append(
            {
                "path": relative_path,
                "sha256": expected_digest,
                "bytes": expected_bytes,
                "parse_status": parse_status,
                "extraction_status": extraction_status,
            }
        )
    descriptors.sort(key=lambda source: source["path"])
    if len(descriptors) != 705:
        raise LegacySourceDriftError(
            "FROZEN_ANALYSIS_SOURCE_COUNT_MUST_BE_705"
        )
    return descriptors


def _as_mapping_list(value: object, field: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(
        value,
        (str, bytes, bytearray),
    ):
        raise TypeError(f"{field} must be an array")
    output: list[Mapping[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise TypeError(f"{field} rows must be objects")
        output.append(item)
    return output


def _string_list(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(
        value,
        (str, bytes, bytearray),
    ):
        return []
    return sorted({str(item) for item in value if str(item)})


def _level_key(row: Mapping[str, Any]) -> tuple[str, int]:
    return (str(row["game_id"]), int(row["level_number"]))


def _frontier_class(scope: object) -> str:
    value = str(scope)
    if value in {"current_frontier", "current_stop_frame"}:
        return "CURRENT_FRONTIER"
    if value == "blocked_behind_current_frontier":
        return "BLOCKED"
    if value == "not_unresolved":
        return "CLOSED_LEGACY"
    return "UNKNOWN"


def _legacy_confidence(strict_status: str) -> str:
    if strict_status == "EVIDENCE_CLOSED":
        return "LEGACY_BOUNDARY_CLOSED"
    if strict_status == "BOUNDED_SUSPEND_CURRENT_FRONTIER_ANALYZED":
        return "LEGACY_CURRENT_FRONTIER_BOUNDED"
    if strict_status == "BOUNDED_SUSPEND_BLOCKED_LEVEL_ANALYZED":
        return "LEGACY_INHERITED_BOUNDED"
    return "LEGACY_STATUS_UNKNOWN"


def _extract_run(value: Mapping[str, Any]) -> Mapping[str, Any]:
    compact = value.get("compact_run")
    if compact is None:
        return value
    if not isinstance(compact, Mapping):
        raise TypeError("compact_run must be an object")
    return compact


def _current_game_index(
    repository_root: Path,
    report_paths: Sequence[str],
) -> tuple[
    dict[str, dict[str, Any]],
    list[dict[str, Any]],
]:
    current: dict[str, dict[str, Any]] = {}
    report_sources: list[dict[str, Any]] = []
    for relative_path in report_paths:
        path = repository_root / relative_path
        if not path.is_file():
            raise FileNotFoundError(path)
        value = _json_object(path)
        run = _extract_run(value)
        if str(run.get("operation_mode", "")).casefold() != "offline":
            raise ValueError(f"CURRENT_REPORT_NOT_OFFLINE:{relative_path}")
        lifecycle = run.get("instruction_lifecycle")
        if (
            lifecycle is not None
            and str(lifecycle).casefold() != "active"
        ):
            raise ValueError(f"CURRENT_REPORT_NOT_ACTIVE:{relative_path}")
        errors = int(run.get("error_count", 0))
        if errors:
            raise ValueError(f"CURRENT_REPORT_HAS_ERRORS:{relative_path}")
        reports = _as_mapping_list(run.get("reports"), "reports")
        source = {
            "path": relative_path,
            "sha256": _file_digest(path),
            "completed_levels": int(run.get("completed_levels", 0)),
            "environment_count": int(run.get("environment_count", 0)),
            "error_count": errors,
        }
        report_sources.append(source)
        for report in reports:
            game_id = str(report.get("game_id", ""))
            if not game_id:
                raise ValueError(f"CURRENT_REPORT_GAME_ID_MISSING:{relative_path}")
            completed = int(report.get("levels_completed", 0))
            win_levels = int(report.get("win_levels", 0))
            if completed < 0 or win_levels < 1 or completed > win_levels:
                raise ValueError(
                    f"CURRENT_REPORT_LEVEL_COUNT_INVALID:{relative_path}:{game_id}"
                )
            candidate = {
                "game_id": game_id,
                "completed_levels": completed,
                "win_levels": win_levels,
                "complete": bool(report.get("complete", False)),
                "max_action_exhausted": bool(
                    report.get("max_action_exhausted", False)
                ),
                "evidence_refs": [relative_path],
            }
            previous = current.get(game_id)
            if previous is None or completed > int(
                previous["completed_levels"]
            ):
                current[game_id] = candidate
            elif completed == int(previous["completed_levels"]):
                previous["evidence_refs"] = sorted(
                    set(previous["evidence_refs"]) | {relative_path}
                )
    return current, sorted(report_sources, key=lambda item: item["path"])


def _reconciliation_status(
    *,
    strict_status: str,
    level_number: int,
    current: Mapping[str, Any] | None,
) -> tuple[str, str]:
    if current is None:
        return (
            "UNOBSERVED",
            "No retained active-runtime report currently reaches this game.",
        )
    completed = int(current["completed_levels"])
    win_levels = int(current["win_levels"])
    if level_number <= completed:
        if strict_status == "EVIDENCE_CLOSED":
            return (
                "CONFIRMED",
                "Current rendered runtime completion agrees with a legacy "
                "boundary-closed row.",
            )
        return (
            "STALE",
            "Current rendered runtime completes this level, but the retained "
            "legacy row still records a bounded suspend.",
        )
    if level_number == completed + 1 and completed < win_levels:
        return (
            "PARTIALLY_CONFIRMED",
            "Current runtime directly reaches this next level but does not "
            "close its boundary within the retained run.",
        )
    return (
        "UNOBSERVED",
        "The retained active-runtime report does not directly reach this level.",
    )


def _mechanics_index(
    rows: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, int], Mapping[str, Any]]:
    output: dict[tuple[str, int], Mapping[str, Any]] = {}
    for row in rows:
        key = _level_key(row)
        if key in output:
            raise ValueError(f"DUPLICATE_FRONTIER_MECHANICS:{key}")
        output[key] = row
        for blocked in _as_mapping_list(
            row.get("blocked_inherited_levels", ()),
            "blocked_inherited_levels",
        ):
            blocked_key = (
                str(row["game_id"]),
                int(blocked["level_number"]),
            )
            if blocked_key in output:
                raise ValueError(
                    f"DUPLICATE_BLOCKED_MECHANICS_OWNER:{blocked_key}"
                )
            output[blocked_key] = row
    return output


def _closed_mechanics_id(atlas: Mapping[str, Any]) -> str:
    generator = str(atlas.get("primary_generator_class", "")).strip()
    operation = str(atlas.get("operation_type", "")).strip()
    if not generator:
        generator = "legacy_closed_transition"
    return f"closed_policy::{generator}::{operation or 'unknown'}"


def _recommended_components(
    mechanics: Mapping[str, Any] | None,
    atlas: Mapping[str, Any],
) -> list[str]:
    if mechanics is not None:
        components = _string_list(mechanics.get("specific_component_ids"))
        if components:
            return components
    primitive = atlas.get("necessary_primitive")
    if not isinstance(primitive, Mapping):
        return []
    return sorted(
        set(_string_list(primitive.get("component_types")))
        | set(_string_list(primitive.get("primitive_ids")))
    )


def _build_reconciliation(
    *,
    strict_rows: Sequence[Mapping[str, Any]],
    current_games: Mapping[str, Mapping[str, Any]],
    report_sources: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[tuple[str, int], str]]:
    rows: list[dict[str, Any]] = []
    statuses: dict[tuple[str, int], str] = {}
    for strict in strict_rows:
        key = _level_key(strict)
        current = current_games.get(key[0])
        status, reason = _reconciliation_status(
            strict_status=str(strict.get("strict_status", "")),
            level_number=key[1],
            current=current,
        )
        statuses[key] = status
        rows.append(
            {
                "game_id": key[0],
                "level": key[1],
                "legacy_strict_status": str(
                    strict.get("strict_status", "")
                ),
                "legacy_frontier_scope": str(
                    strict.get("frontier_evidence_scope", "")
                ),
                "current_completed_levels": (
                    int(current["completed_levels"])
                    if current is not None
                    else None
                ),
                "current_directly_reached": (
                    current is not None
                    and key[1] <= int(current["completed_levels"]) + 1
                ),
                "current_validation_status": status,
                "reason": reason,
                "current_evidence_refs": (
                    list(current["evidence_refs"])
                    if current is not None
                    else []
                ),
            }
        )
    counts = Counter(row["current_validation_status"] for row in rows)
    summary = {
        "total_levels": len(rows),
        "current_completed_levels": sum(
            int(game["completed_levels"]) for game in current_games.values()
        ),
        "current_game_count": len(current_games),
        "status_counts": {
            status: counts.get(status, 0)
            for status in VALID_RECONCILIATION_STATUSES
        },
    }
    return (
        _content_bound(
            "arc3_p10_analysis_reconciliation_matrix",
            {
                "scope": "retained OFFLINE rendered-runtime evidence only",
                "report_sources": list(report_sources),
                "current_games": sorted(
                    (dict(game) for game in current_games.values()),
                    key=lambda item: item["game_id"],
                ),
                "summary": summary,
                "rows": rows,
                "hds_judgment": {
                    "status": "HOLD",
                    "reason": (
                        "35/183 current completions do not satisfy the P10 "
                        "183/183 release gate."
                    ),
                    "runtime_p_promotion_authorized": False,
                },
            },
        ),
        statuses,
    )


def _build_ledger(
    *,
    strict_rows: Sequence[Mapping[str, Any]],
    atlas_rows: Sequence[Mapping[str, Any]],
    mechanics_rows: Sequence[Mapping[str, Any]],
    statuses: Mapping[tuple[str, int], str],
    current_games: Mapping[str, Mapping[str, Any]],
    analysis_sources: Sequence[Mapping[str, Any]],
    source_revision: str,
    source_inventory_digest: str,
) -> dict[str, Any]:
    atlas_index = {_level_key(row): row for row in atlas_rows}
    mechanics_index = _mechanics_index(mechanics_rows)
    if len(atlas_index) != 183:
        raise ValueError("LEVEL_ATLAS_MUST_HAVE_183_UNIQUE_LEVELS")
    rows: list[dict[str, Any]] = []
    for strict in strict_rows:
        key = _level_key(strict)
        atlas = atlas_index.get(key)
        if atlas is None:
            raise ValueError(f"LEVEL_ATLAS_ROW_MISSING:{key}")
        mechanics = mechanics_index.get(key)
        strict_status = str(strict.get("strict_status", ""))
        evidence_refs = set(_string_list(strict.get("analysis_artifacts")))
        if mechanics is not None:
            evidence_refs.update(
                _string_list(mechanics.get("analysis_artifacts"))
            )
        current = current_games.get(key[0])
        if current is not None:
            evidence_refs.update(current["evidence_refs"])
        state_variables = (
            _string_list(mechanics.get("state_variables"))
            if mechanics is not None
            else _string_list(atlas.get("state_variables"))
        )
        mechanics_id = (
            str(mechanics["mechanics_id"])
            if mechanics is not None
            else _closed_mechanics_id(atlas)
        )
        local_effect_classes = (
            _string_list(mechanics.get("local_effect_classes"))
            if mechanics is not None
            else ["closed_boundary_effect"]
        )
        failure_signature = (
            str(mechanics.get("refined_failure_signature_id", ""))
            if mechanics is not None
            else str(
                atlas.get(
                    "failure_signature_contract",
                    "not_applicable_public_policy_boundary_reached",
                )
            )
        )
        required_capabilities = (
            _string_list(mechanics.get("required_agent_capability_ids"))
            if mechanics is not None
            else []
        )
        row = {
            "game_id": key[0],
            "level": key[1],
            "level_id": str(strict.get("level_id", "")),
            "title": str(strict.get("title", "")),
            "frontier": _frontier_class(
                strict.get("frontier_evidence_scope")
            ),
            "mechanics_id": mechanics_id,
            "mechanics_id_basis": (
                "full_task_mechanics_inventory"
                if mechanics is not None
                else "closed_level_atlas_generator"
            ),
            "operation_type": str(strict.get("operation_type", "")),
            "state_variables": state_variables,
            "local_effect_classes": local_effect_classes,
            "failure_signature": failure_signature,
            "required_capabilities": required_capabilities,
            "recommended_components": _recommended_components(
                mechanics,
                atlas,
            ),
            "progress_blocker": (
                str(mechanics.get("progress_blocker", ""))
                if mechanics is not None
                else "none_currently_recorded_for_closed_legacy_boundary"
            ),
            "hazard_blocker": (
                str(mechanics.get("hazard_blocker", ""))
                if mechanics is not None
                else "none_currently_recorded_for_closed_legacy_boundary"
            ),
            "promotion_blocker": (
                str(mechanics.get("promotion_blocker", ""))
                if mechanics is not None
                else "current rendered evidence must revalidate before reuse"
            ),
            "evidence_refs": sorted(evidence_refs),
            "legacy_confidence": _legacy_confidence(strict_status),
            "current_validation_status": statuses[key],
            "legacy_strict_status": strict_status,
            "legacy_transition_relation": str(
                atlas.get("transition_type", "")
            ),
            "legacy_progress_condition": str(
                atlas.get("progress_condition", "")
            ),
            "legacy_hazard_condition": str(
                atlas.get("hazard_condition", "")
            ),
        }
        missing = [field for field in REQUIRED_LEDGER_FIELDS if field not in row]
        if missing:
            raise ValueError(
                f"DEVELOPMENT_LEDGER_REQUIRED_FIELDS_MISSING:{key}:{missing}"
            )
        rows.append(row)
    row_keys = {
        (str(row["game_id"]), int(row["level"]))
        for row in rows
    }
    if len(rows) != 183 or len(row_keys) != 183:
        raise ValueError("DEVELOPMENT_LEDGER_MUST_HAVE_183_UNIQUE_LEVELS")
    game_count = len({row["game_id"] for row in rows})
    if game_count != 25:
        raise ValueError("DEVELOPMENT_LEDGER_MUST_HAVE_25_GAMES")
    return _content_bound(
        "arc3_p10_legacy_level_analysis_ledger",
        {
            "source_snapshot": {
                "source_revision": source_revision,
                "source_inventory_digest": source_inventory_digest,
                "analysis_source_count": len(analysis_sources),
                "sources": list(analysis_sources),
            },
            "field_policy": {
                "retained_for_development": [
                    "game/task/level identity",
                    "mechanics and cross-level relationships",
                    "failure signatures and blockers",
                    "source and evidence references",
                ],
                "retained_by_frozen_reference_only": [
                    "literal coordinates",
                    "source-state details",
                    "replay and fixed action material",
                ],
                "discarded_as_authority": [
                    "stale score claims",
                    "legacy promotion decisions",
                    "legacy next-task directives",
                ],
                "runtime_subtraction_boundary": (
                    "Identity and source-linked fields are removed only when "
                    "COMPOSABLE capability material is compiled into Runtime P."
                ),
                "file_wide_quarantine": False,
            },
            "summary": {
                "game_count": game_count,
                "level_count": len(rows),
                "current_completed_levels": sum(
                    int(game["completed_levels"])
                    for game in current_games.values()
                ),
                "frontier_counts": dict(
                    sorted(Counter(row["frontier"] for row in rows).items())
                ),
                "validation_status_counts": dict(
                    sorted(
                        Counter(
                            row["current_validation_status"] for row in rows
                        ).items()
                    )
                ),
            },
            "required_row_fields": list(REQUIRED_LEDGER_FIELDS),
            "rows": rows,
        },
    )


def _level_ref(game_id: str, level_number: int) -> dict[str, Any]:
    return {"game_id": game_id, "level": level_number}


def _build_coverage(
    *,
    clusters: Sequence[Mapping[str, Any]],
    mechanics_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    mechanics_by_owner = {
        _level_key(row): row
        for row in mechanics_rows
    }
    rows: list[dict[str, Any]] = []
    for cluster in clusters:
        capability_id = str(cluster["capability_id"])
        frontier_refs: list[dict[str, Any]] = []
        blocked_refs: list[dict[str, Any]] = []
        for raw in _as_mapping_list(
            cluster.get("frontier_refs", ()),
            "frontier_refs",
        ):
            owner_key = _level_key(raw)
            frontier_refs.append(_level_ref(*owner_key))
            mechanics = mechanics_by_owner.get(owner_key)
            if mechanics is None:
                raise ValueError(
                    f"CAPABILITY_OWNER_MECHANICS_MISSING:{owner_key}"
                )
            if capability_id not in _string_list(
                mechanics.get("required_agent_capability_ids")
            ):
                raise ValueError(
                    f"CAPABILITY_OWNER_LINK_MISSING:{capability_id}:{owner_key}"
                )
            for blocked in _as_mapping_list(
                mechanics.get("blocked_inherited_levels", ()),
                "blocked_inherited_levels",
            ):
                blocked_refs.append(
                    _level_ref(
                        owner_key[0],
                        int(blocked["level_number"]),
                    )
                )
        frontier_refs.sort(key=lambda item: (item["game_id"], item["level"]))
        blocked_refs.sort(key=lambda item: (item["game_id"], item["level"]))
        expected_frontier = int(cluster.get("frontier_count", -1))
        expected_blocked = int(
            cluster.get("blocked_inherited_level_count", -1)
        )
        if len(frontier_refs) != expected_frontier:
            raise ValueError(
                f"CAPABILITY_FRONTIER_COUNT_MISMATCH:{capability_id}"
            )
        if len(blocked_refs) != expected_blocked:
            raise ValueError(
                f"CAPABILITY_BLOCKED_COUNT_MISMATCH:{capability_id}"
            )
        current_status = {
            "C2_visible_effect_transition_model": (
                "POST_ACTION_OBSERVER_CLUSTER_STABLE"
            ),
            "C3_commit_boundary_predictor": (
                "NON_CIRCULAR_PREDICTOR_LOCAL_PROBE_HOLD"
            ),
            "C10_phase_timer_unlock_model": (
                "ONE_STEP_VISIBLE_CAUSAL_CONTEXT_COMPOSABLE_"
                "RUNTIME_INTERVENTION_REJECTED"
            ),
            "C7_target_contact_boundary_verifier": (
                "LOCAL_PROBE_CLOSED_NEGATIVE_NEGATIVE_ONLY"
            ),
            "C12_layout_mode_commit_discriminator": (
                "LOCAL_PROBE_CLOSED_NEGATIVE_NEGATIVE_ONLY"
            ),
            "C5_stale_settle_frame_controller": (
                "BOUNDED_OLD_ACTION_REPLAY_LOCAL_PROBE_REJECTED"
            ),
        }.get(capability_id, "NOT_CLUSTER_VALIDATED")
        rows.append(
            {
                "capability_id": capability_id,
                "capability_label": str(
                    cluster.get("capability_label", "")
                ),
                "frontier_count": len(frontier_refs),
                "blocked_inherited_level_count": len(blocked_refs),
                "total_link_count": len(frontier_refs) + len(blocked_refs),
                "frontier_refs": frontier_refs,
                "blocked_refs": blocked_refs,
                "state_variable_counts": dict(
                    cluster.get("state_variable_counts", {})
                ),
                "local_effect_class_counts": dict(
                    cluster.get("local_effect_class_counts", {})
                ),
                "failure_signature_counts": dict(
                    cluster.get("refined_failure_signature_counts", {})
                ),
                "component_library_context": dict(
                    cluster.get("component_library_context", {})
                ),
                "current_implementation_status": current_status,
                "runtime_promotion_authorized": False,
            }
        )
    rows.sort(
        key=lambda row: (
            -int(row["blocked_inherited_level_count"]),
            -int(row["frontier_count"]),
            str(row["capability_id"]),
        )
    )
    return _content_bound(
        "arc3_p10_capability_coverage_matrix",
        {
            "coverage_semantics": (
                "Counts are development links and overlap across capabilities; "
                "they must never be added as distinct solvable levels."
            ),
            "summary": {
                "capability_count": len(rows),
                "frontier_level_count": len(
                    {
                        (ref["game_id"], ref["level"])
                        for row in rows
                        for ref in row["frontier_refs"]
                    }
                ),
                "blocked_level_count": len(
                    {
                        (ref["game_id"], ref["level"])
                        for row in rows
                        for ref in row["blocked_refs"]
                    }
                ),
                "top_priority_capabilities": [
                    "C2_visible_effect_transition_model",
                    "C3_commit_boundary_predictor",
                    "C10_phase_timer_unlock_model",
                ],
            },
            "rows": rows,
        },
    )


def _ref_key(ref: Mapping[str, Any]) -> tuple[str, int]:
    return (str(ref["game_id"]), int(ref["level"]))


def _build_queue(coverage: Mapping[str, Any]) -> dict[str, Any]:
    coverage_rows = _as_mapping_list(coverage.get("rows"), "coverage rows")
    by_id = {str(row["capability_id"]): row for row in coverage_rows}
    c2 = by_id["C2_visible_effect_transition_model"]
    c3 = by_id["C3_commit_boundary_predictor"]
    c2_refs = {
        _ref_key(ref)
        for ref in [
            *_as_mapping_list(c2["frontier_refs"], "frontier_refs"),
            *_as_mapping_list(c2["blocked_refs"], "blocked_refs"),
        ]
    }
    c3_refs = {
        _ref_key(ref)
        for ref in [
            *_as_mapping_list(c3["frontier_refs"], "frontier_refs"),
            *_as_mapping_list(c3["blocked_refs"], "blocked_refs"),
        ]
    }
    queue: list[dict[str, Any]] = [
        {
            "rank": 1,
            "work_block_id": "WB-C2-C3-VISIBLE-EFFECT-COMMIT",
            "capability_ids": [
                "C2_visible_effect_transition_model",
                "C3_commit_boundary_predictor",
            ],
            "selection_basis": "maximum cross-game structural coverage",
            "coverage": {
                "c2_link_count": len(c2_refs),
                "c3_link_count": len(c3_refs),
                "overlap_count": len(c2_refs & c3_refs),
                "union_level_count": len(c2_refs | c3_refs),
                "union_level_refs": [
                    _level_ref(game_id, level)
                    for game_id, level in sorted(c2_refs | c3_refs)
                ],
            },
            "required_contracts": [
                "rendered pre/post state abstraction",
                "visible local-effect classification",
                "positive/negative transition contrast",
                "progress/commit/hazard boundary prediction",
                "HDS reobserve and rollback obligations",
            ],
            "candidate_tiers": list(PROMOTION_TIERS),
            "current_tier": "LOCAL_PROBE",
            "implementation_evidence": {
                "code": (
                    "ARC-AGI-3-Agents/arc3_agi_agent/"
                    "cross_cutting_transition.py"
                ),
                "tests": (
                    "ARC-AGI-3-Agents/tests/unit/"
                    "test_cross_cutting_transition_p10.py"
                ),
                "shadow_report_field": "development_transition_probe",
                "predictive_audit": (
                    "evidence/p10/development/"
                    "c2_c3_transition_all25_max450_v2/"
                    "C2_C3_PREDICTIVE_CLUSTER_AUDIT.json"
                ),
                "capability_tiers": {
                    "C2_visible_effect_transition_model": (
                        "CLUSTER_STABLE"
                    ),
                    "C3_commit_boundary_predictor": "LOCAL_PROBE",
                },
                "c3_hds_status": "HOLD",
                "action_selection_influence": False,
                "runtime_p_promotion_authorized": False,
            },
            "promotion_gate": (
                "No Runtime P compile before cross-game CLUSTER_STABLE "
                "evidence and identity-free COMPOSABLE verification."
            ),
            "dedicated_level_operator_allowed": False,
        }
    ]
    remaining = [
        row
        for row in coverage_rows
        if str(row["capability_id"])
        not in {
            "C2_visible_effect_transition_model",
            "C3_commit_boundary_predictor",
        }
    ]
    remaining.sort(
        key=lambda row: (
            -int(row["blocked_inherited_level_count"]),
            -int(row["frontier_count"]),
            str(row["capability_id"]),
        )
    )
    for rank, row in enumerate(remaining, start=2):
        capability_id = str(row["capability_id"])
        current_tier = (
            "COMPOSABLE"
            if capability_id == "C10_phase_timer_unlock_model"
            else (
                "LOCAL_PROBE"
                if capability_id
                in {
                    "C7_target_contact_boundary_verifier",
                    "C12_layout_mode_commit_discriminator",
                    "C5_stale_settle_frame_controller",
                }
                else "NOT_STARTED"
            )
        )
        implementation_evidence: dict[str, Any] | None = None
        work_status = "PENDING"
        if capability_id == "C10_phase_timer_unlock_model":
            work_status = "RUNTIME_INTERVENTION_REJECTED"
            implementation_evidence = {
                "audit": (
                    "evidence/p10/development/"
                    "c2_c3_transition_all25_max450_v2/"
                    "C10_TEMPORAL_CAUSAL_CONTRAST_AUDIT.json"
                ),
                "composition_audit": (
                    "evidence/p10/development/"
                    "c2_c3_transition_all25_max450_v2/"
                    "C2_C10_COMPOSITION_REMOVAL_AUDIT.json"
                ),
                "candidate_intervention_audit": (
                    "evidence/p10/development/"
                    "c2_c10_candidate_intervention_v1/"
                    "C2_C10_CANDIDATE_INTERVENTION_AUDIT.json"
                ),
                "materially_new_observable_variable": (
                    "previous visible action prototype plus coarse visible "
                    "outcome causal context"
                ),
                "cluster_stable_status": "PASS",
                "composable_status": "PASS",
                "candidate_intervention_status": "REJECT",
                "candidate_target_completion_delta": 0,
                "active_manifest_changed": False,
                "runtime_p_promotion_authorized": False,
            }
        elif capability_id == "C7_target_contact_boundary_verifier":
            work_status = "CLOSED_NEGATIVE"
            implementation_evidence = {
                "admission_audit": (
                    "evidence/p10/development/"
                    "c7_target_contact_closed_negative_v1/"
                    "C7_CLOSED_NEGATIVE_ADMISSION_AUDIT.json"
                ),
                "retained_legacy_source": (
                    "evidence/p10/development/"
                    "c7_target_contact_closed_negative_v1/"
                    "LEGACY_C7_TARGET_CONTACT_BOUNDARY_CAPABILITY.json"
                ),
                "retained_source_sha256": (
                    "cf52951e7bc4c85aa29a2bff217f298b558fc5d3dad6312"
                    "c3bde1c8575883032"
                ),
                "target_count": 7,
                "total_probe_count": 288,
                "changed_probe_count": 228,
                "contact_gain_probe_count": 63,
                "progress_separator_variable_count": 0,
                "hazard_separator_variable_count": 0,
                "promotion_eligible_variable_count": 0,
                "negative_only": True,
                "same_surface_retry_authorized": False,
                "runtime_p_promotion_authorized": False,
            }
        elif capability_id == "C12_layout_mode_commit_discriminator":
            work_status = "CLOSED_NEGATIVE"
            implementation_evidence = {
                "admission_audit": (
                    "evidence/p10/development/"
                    "c12_layout_mode_closed_negative_v1/"
                    "C12_CLOSED_NEGATIVE_ADMISSION_AUDIT.json"
                ),
                "retained_primary_legacy_source": (
                    "evidence/p10/development/"
                    "c12_layout_mode_closed_negative_v1/"
                    "LEGACY_C12_LAYOUT_MODE_COMMIT_"
                    "DISCRIMINATOR_CAPABILITY.json"
                ),
                "retained_primary_source_sha256": (
                    "3ca11339393f4c4410974e676cf163099a2da36030d86"
                    "9dd10c45d5c4364df40"
                ),
                "retained_auxiliary_legacy_source": (
                    "evidence/p10/development/"
                    "c12_layout_mode_closed_negative_v1/"
                    "LEGACY_LAYOUT_MODE_DISCRIMINATOR_HARNESS.json"
                ),
                "retained_auxiliary_source_sha256": (
                    "bb9ce326f52709ad9395c1a7db959c520f8b634750265"
                    "f735db5edda827479fd"
                ),
                "primary_target_count": 5,
                "primary_total_probe_count": 212,
                "primary_changed_probe_count": 140,
                "primary_layout_mode_changed_probe_count": 104,
                "auxiliary_target_count": 5,
                "auxiliary_total_probe_count": 176,
                "auxiliary_changed_probe_count": 86,
                "combined_probe_count": 388,
                "combined_changed_probe_count": 226,
                "combined_progress_count": 0,
                "combined_game_over_count": 0,
                "progress_separator_variable_count": 0,
                "hazard_separator_variable_count": 0,
                "promotion_eligible_variable_count": 0,
                "negative_only": True,
                "legacy_contract_spec_mismatch_quarantined": True,
                "auxiliary_public_replay_bootstrap_quarantined": True,
                "same_surface_retry_authorized": False,
                "runtime_p_promotion_authorized": False,
            }
        elif capability_id == "C5_stale_settle_frame_controller":
            work_status = "LOCAL_AXIS_CLOSED_NEGATIVE"
            implementation_evidence = {
                "candidate_intervention_audit": (
                    "evidence/p10/development/"
                    "directional_settle_composition_v1/"
                    "DIRECTIONAL_SETTLE_CANDIDATE_INTERVENTION_AUDIT.json"
                ),
                "failure_audit": (
                    "evidence/p10/development/"
                    "directional_settle_composition_v1/"
                    "DIRECTIONAL_SETTLE_FAILURE_AUDIT.json"
                ),
                "candidate_intervention_status": "REJECT",
                "bounded_old_action_replay_count": 8,
                "target_completion_delta": 0,
                "same_axis_retry_authorized": False,
                "active_manifest_changed": False,
                "runtime_p_promotion_authorized": False,
            }
        queue.append(
            {
                "rank": rank,
                "work_block_id": f"WB-{capability_id}",
                "capability_ids": [capability_id],
                "selection_basis": "remaining capability coverage",
                "coverage": {
                    "frontier_count": int(row["frontier_count"]),
                    "blocked_inherited_level_count": int(
                        row["blocked_inherited_level_count"]
                    ),
                    "total_link_count": int(row["total_link_count"]),
                },
                "candidate_tiers": list(PROMOTION_TIERS),
                "current_tier": current_tier,
                "work_status": work_status,
                **(
                    {"implementation_evidence": implementation_evidence}
                    if implementation_evidence is not None
                    else {}
                ),
                "promotion_gate": (
                    "Require reusable positive/negative evidence and "
                    "identity-free composition before Runtime P compile."
                ),
                "dedicated_level_operator_allowed": False,
            }
        )
    return _content_bound(
        "arc3_p10_capability_build_queue",
        {
            "selection_policy": {
                "primary": "coverage before next-level order",
                "next_unembedded_work_block": (
                    "WB-C1_rendered_affordance_objectizer"
                ),
                "forbidden": [
                    "one Python operator per unresolved level",
                    "operator count as progress",
                    "stale-score file-wide rejection",
                    "KA59-only tunnel vision",
                    "runtime identity before output compilation",
                ],
                "runtime_compile_boundary": (
                    "Only a COMPOSABLE candidate may be horizontally "
                    "subtracted into identity-free Runtime P."
                ),
            },
            "queue": queue,
            "composition_tests": [
                {
                    "test_id": "COMPOSE-KA59-REMAINING-BOUNDARY",
                    "game_id": "ka59-38d34dbb",
                    "level": 7,
                    "purpose": (
                        "Test composition of existing multi-actor, "
                        "directional-force, and obligation capabilities."
                    ),
                    "new_dedicated_operator_allowed": False,
                    "runtime_promotion_authorized": False,
                    "current_status": "CLOSED_NEGATIVE_AXIS",
                    "failure_audit": (
                        "evidence/p10/development/"
                        "directional_settle_composition_v1/"
                        "DIRECTIONAL_SETTLE_FAILURE_AUDIT.json"
                    ),
                    "same_axis_retry_authorized": False,
                    "required_next_variable": (
                        "parseable visible successor obligation state, "
                        "not predecessor action replay"
                    ),
                }
            ],
            "hds_gate": {
                "status": "HOLD",
                "reason": (
                    "Queue construction authorizes development probes, not "
                    "runtime promotion or a score claim."
                ),
                "next_work_block_id": (
                    "WB-C1_rendered_affordance_objectizer"
                ),
                "closed_negative_work_blocks": [
                    "WB-C7_target_contact_boundary_verifier",
                    "WB-C12_layout_mode_commit_discriminator",
                    "WB-C5_stale_settle_frame_controller:"
                    "bounded-old-action-replay-axis",
                ],
            },
        },
    )


def compile_development_analysis(
    *,
    legacy_repository_root: Path,
    repository_root: Path,
    current_report_paths: Sequence[str] = DEFAULT_CURRENT_REPORTS,
) -> dict[str, dict[str, Any]]:
    """Compile the four canonical development-only P10 artifacts."""

    legacy_repository_root = legacy_repository_root.resolve()
    repository_root = repository_root.resolve()
    provenance = _json_object(
        repository_root / "manifests" / "provenance_manifest.json"
    )
    dataset_manifest = _json_object(
        repository_root / "manifests" / "dataset_manifest.json"
    )
    source_index = _source_index(provenance)
    analysis_sources = _verified_analysis_source_descriptors(
        legacy_repository_root=legacy_repository_root,
        source_index=source_index,
    )

    loaded = {
        name: _verified_legacy_json(
            legacy_repository_root=legacy_repository_root,
            relative_path=relative_path,
            source_index=source_index,
        )
        for name, relative_path in CORE_LEGACY_SOURCES.items()
    }
    strict_rows = _as_mapping_list(
        loaded["strict_ledger"].get("rows"),
        "strict ledger rows",
    )
    atlas_rows = _as_mapping_list(
        loaded["level_atlas"].get("levels"),
        "level atlas rows",
    )
    mechanics_rows = _as_mapping_list(
        loaded["mechanics_inventory"].get("mechanics_inventory"),
        "mechanics inventory",
    )
    clusters = _as_mapping_list(
        loaded["capability_clusters"].get("capability_clusters"),
        "capability clusters",
    )
    if len(strict_rows) != 183:
        raise ValueError("STRICT_LEDGER_MUST_HAVE_183_LEVELS")
    if len(mechanics_rows) != 21:
        raise ValueError("MECHANICS_INVENTORY_MUST_HAVE_21_FRONTIERS")
    if len(clusters) != 14:
        raise ValueError("CAPABILITY_MATRIX_MUST_HAVE_14_CLUSTERS")

    current_games, report_sources = _current_game_index(
        repository_root,
        current_report_paths,
    )
    reconciliation, statuses = _build_reconciliation(
        strict_rows=strict_rows,
        current_games=current_games,
        report_sources=report_sources,
    )
    ledger = _build_ledger(
        strict_rows=strict_rows,
        atlas_rows=atlas_rows,
        mechanics_rows=mechanics_rows,
        statuses=statuses,
        current_games=current_games,
        analysis_sources=analysis_sources,
        source_revision=str(provenance.get("source_revision", "")),
        source_inventory_digest=str(
            dataset_manifest.get("source_inventory_digest", "")
        ),
    )
    coverage = _build_coverage(
        clusters=clusters,
        mechanics_rows=mechanics_rows,
    )
    queue = _build_queue(coverage)
    return {
        LEDGER_FILENAME: ledger,
        RECONCILIATION_FILENAME: reconciliation,
        COVERAGE_FILENAME: coverage,
        QUEUE_FILENAME: queue,
    }


def write_development_analysis(
    artifacts: Mapping[str, Mapping[str, Any]],
    output_dir: Path,
) -> dict[str, str]:
    """Write canonical artifacts and return their byte digests."""

    output_dir.mkdir(parents=True, exist_ok=True)
    digests: dict[str, str] = {}
    for filename in (
        LEDGER_FILENAME,
        RECONCILIATION_FILENAME,
        COVERAGE_FILENAME,
        QUEUE_FILENAME,
    ):
        artifact = artifacts.get(filename)
        if artifact is None:
            raise ValueError(f"DEVELOPMENT_ARTIFACT_MISSING:{filename}")
        encoded = _canonical_bytes(artifact)
        path = output_dir / filename
        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_bytes(encoded)
        temporary.replace(path)
        digests[filename] = hashlib.sha256(encoded).hexdigest()
    return digests


def _parser() -> argparse.ArgumentParser:
    repository_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(
        description=(
            "Compile frozen legacy ARC3 analysis into development-only P10 "
            "memory; generated files are forbidden runtime input."
        )
    )
    parser.add_argument(
        "--legacy-repository-root",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=repository_root,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=repository_root / "analysis" / "development",
    )
    parser.add_argument(
        "--current-report",
        action="append",
        dest="current_reports",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    artifacts = compile_development_analysis(
        legacy_repository_root=args.legacy_repository_root,
        repository_root=args.repository_root,
        current_report_paths=(
            tuple(args.current_reports)
            if args.current_reports
            else DEFAULT_CURRENT_REPORTS
        ),
    )
    digests = write_development_analysis(artifacts, args.output_dir)
    print(
        json.dumps(
            {
                "output_dir": str(args.output_dir.resolve()),
                "artifact_digests": digests,
                "runtime_use": RUNTIME_USE,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
