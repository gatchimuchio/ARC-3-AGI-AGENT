"""C2-082: aggregate visible geometric effects in the verified C2-080 trace.

No learner is constructed or called. Exact same-color component correspondences
are geometry only, never inferred object identity, physics, HUD or score effects.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import time

import ARC3HDS視覚公開記録逐次比較 as replay

ROOT = replay.ROOT
BORDER_WIDTH = 2


def _components(board):
    """4-connected equal-color components; normalized exact shape stays in RAM."""
    height, width = len(board), len(board[0])
    visited, groups = set(), defaultdict(list)
    for y in range(height):
        for x in range(width):
            if (x, y) in visited:
                continue
            color, pending, cells = board[y][x], [(x, y)], set()
            visited.add((x, y))
            while pending:
                cx, cy = pending.pop()
                cells.add((cx, cy))
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in visited and board[ny][nx] == color:
                        visited.add((nx, ny))
                        pending.append((nx, ny))
            left, top = min(cx for cx, _ in cells), min(cy for _, cy in cells)
            normalized = tuple(sorted((cx - left, cy - top) for cx, cy in cells))
            groups[(color, normalized)].append((left, top, cells))
    return groups


def _translations(before, after):
    left, right = _components(before), _components(after)
    counts, deltas, areas, moved_pixels = Counter(), Counter(), Counter(), set()
    counts["before_components"] = sum(map(len, left.values()))
    counts["after_components"] = sum(map(len, right.values()))
    for signature in left.keys() | right.keys():
        previous, current = left.get(signature, ()), right.get(signature, ())
        if not previous or not current:
            counts["unmatched_before_components"] += len(previous)
            counts["unmatched_after_components"] += len(current)
        elif len(previous) != 1 or len(current) != 1:
            counts["ambiguous_shape_groups"] += 1
            counts["ambiguous_before_components"] += len(previous)
            counts["ambiguous_after_components"] += len(current)
        else:
            px, py, pcells = previous[0]
            cx, cy, ccells = current[0]
            dx, dy = cx - px, cy - py
            if dx == dy == 0:
                counts["unique_stationary_correspondences"] += 1
            else:
                counts["unique_translated_correspondences"] += 1
                counts["translated_component_area_sum"] += len(pcells)
                deltas[(dx, dy)] += 1
                areas[len(pcells)] += 1
                moved_pixels.update(pcells ^ ccells)
    return counts, deltas, areas, moved_pixels


def _effects(before, action, after):
    replay.base._require(len(before.board) == len(after.board) and len(before.board[0]) == len(after.board[0]), "effect_board_dimensions_changed")
    height, width = len(before.board), len(before.board[0])
    changed = {(x, y) for y in range(height) for x in range(width) if before.board[y][x] != after.board[y][x]}
    values = {"changed_pixels": len(changed)}
    if changed:
        bbox_width = max(x for x, _ in changed) - min(x for x, _ in changed) + 1
        bbox_height = max(y for _, y in changed) - min(y for _, y in changed) + 1
        border = sum(min(x, y, width - x - 1, height - y - 1) < BORDER_WIDTH for x, y in changed)
        source_colors = {before.board[y][x] for x, y in changed}
        destination_colors = {after.board[y][x] for x, y in changed}
        values.update({"bbox_width": bbox_width, "bbox_height": bbox_height,
                       "bbox_area": bbox_width * bbox_height, "bbox_changed_fill_share": len(changed) / (bbox_width * bbox_height),
                       "border_changed_pixels": border, "border_share_of_changes": border / len(changed),
                       "affected_source_color_count": len(source_colors), "affected_destination_color_count": len(destination_colors),
                       "affected_color_union_count": len(source_colors | destination_colors)})
    counts, deltas, areas, moved = _translations(before.board, after.board)
    counts["responses"] += 1
    counts["responses_with_unique_translation"] += int(counts["unique_translated_correspondences"] > 0)
    counts["responses_with_ambiguous_shape_matches"] += int(counts["ambiguous_shape_groups"] > 0)
    counts["border_only_changed_responses"] += int(bool(changed) and values["border_changed_pixels"] == len(changed))
    counts["full_width_changed_bbox_responses"] += int(bool(changed) and values["bbox_width"] == width)
    counts["full_height_changed_bbox_responses"] += int(bool(changed) and values["bbox_height"] == height)
    supported = len(changed & moved)
    values["changed_pixels_in_unique_translation_union"] = supported
    if changed:
        values["unique_translation_share_of_changes"] = supported / len(changed)
    if action.number == 6:
        counts["action6_responses"] += 1
        for size in (3, 7):
            radius = size // 2
            local = {(x, y) for y in range(max(0, action.y - radius), min(height, action.y + radius + 1))
                     for x in range(max(0, action.x - radius), min(width, action.x + radius + 1))}
            number = len(changed & local)
            values[f"target_local_{size}x{size}_changed_pixels"] = number
            values[f"target_local_{size}x{size}_available_pixels"] = len(local)
            if changed:
                values[f"target_local_{size}x{size}_share_of_all_changes"] = number / len(changed)
                counts[f"action6_global_change_without_{size}x{size}_local_change"] += int(number == 0)
    return values, counts, deltas, areas


def _summary(values):
    if not values:
        return {"n": 0, "min": None, "median": None, "mean": None, "max": None}
    return {"n": len(values), "min": min(values), "median": statistics.median(values),
            "mean": sum(values) / len(values), "max": max(values)}


class Aggregate:
    def __init__(self):
        self.values, self.counts = defaultdict(list), Counter()
        self.deltas, self.areas, self.changed_histogram = Counter(), Counter(), Counter()

    def add(self, effects):
        values, counts, deltas, areas = effects
        for name, value in values.items():
            self.values[name].append(value)
        self.counts.update(counts)
        self.deltas.update(deltas)
        self.areas.update(areas)
        self.changed_histogram[values["changed_pixels"]] += 1

    def report(self):
        return {"counts": dict(sorted(self.counts.items())),
                "measurements": {key: _summary(values) for key, values in sorted(self.values.items())},
                "changed_pixel_count_histogram": [{"pixels": number, "responses": count} for number, count in sorted(self.changed_histogram.items())],
                "relative_translation_delta_histogram": [{"dx": dx, "dy": dy, "correspondences": count} for (dx, dy), count in sorted(self.deltas.items())],
                "translated_component_area_histogram": [{"area": area, "correspondences": count} for area, count in sorted(self.areas.items())]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    replay.base._require(not output.exists(), "refusing_output_overwrite")
    started, errors, source = time.perf_counter(), [], {}
    groups = {label: Aggregate() for label in ("all", "progress", "noop", "other")}
    software_paths = [Path(__file__), Path(replay.__file__), Path(replay.integrity.__file__)]
    software = {path.relative_to(ROOT).as_posix(): replay.base._sha(path) for path in software_paths}
    try:
        replay.base._require(replay.base._sha(Path(replay.__file__)) == "4d917e5007c88eb510664b872535dc016417d9b7d728113242f612f2b7cdee37", "frozen_c2_080_loader_source")
        build = json.loads((replay.SOURCE_BUILD / "build-manifest.json").read_text(encoding="utf-8"))
        replay.base._require(replay.base._sha(replay.SOURCE_BUILD / "submission.ipynb") == build["output_notebook_sha256"], "actual_source_notebook_hash")
        replay.base._require(replay.base._sha(replay.SOURCE_BUILD / "kernel-metadata.json") == build["kernel_metadata_sha256"], "actual_source_metadata_hash")
        with replay.base._frozen_api() as (_, api, _, _):
            streams, source = replay._load_inputs(api)
            for transitions in streams:
                for before, action, after in transitions:
                    if action.number == 0:
                        continue
                    outcome = api._observed_outcome(before, after)
                    label = "progress" if outcome == "レベル進行" else "noop" if outcome == "可視変化なし" else "other"
                    effects = _effects(before, action, after)
                    groups["all"].add(effects)
                    groups[label].add(effects)
        replay.base._require(groups["all"].counts["responses"] == 239, "all_public_effects_once")
        replay.base._require(all(replay.base._sha(ROOT / name) == sha for name, sha in software.items()), "effect_diagnostic_source_drift")
    except Exception as exc:
        errors.append({"type": type(exc).__name__, "contract": str(exc)[:160]})
    report = {
        "schema": "arc3-verified-public-trace-pixel-effect-diagnostic.v1", "run_id": output.stem,
        "observed_at": datetime.now(timezone.utc).isoformat(), "result": "FAIL" if errors else "OBSERVATIONAL_ONLY",
        "software_sha256": software, "source": source,
        "actual_source_notebook_and_metadata_hashes_asserted": True,
        "border_band_width_pixels": BORDER_WIDTH,
        "component_method": "same-color 4-connectivity; exact normalized shape; only one-before/one-after signatures matched; duplicate signatures UNKNOWN, without spatial tie resolution",
        "translation_interpretation": "geometric correspondence only; creation/destruction cannot be excluded; no inferred physical identity or HUD semantics",
        "shape_change_and_unmatched_components": "UNKNOWN mechanical cause; not evidence that no motion occurred",
        "local_windows": "3x3 and 7x7 centered on actual PRE-action Action6 target, clipped to visible board bounds",
        "strata": {label: aggregate.report() for label, aggregate in groups.items()},
        "native_HDS_learners_constructed": 0, "native_HDS_query_update_calls": 0,
        "no_gpu_model_sdk_kaggle_or_game_internals": True,
        "no_runtime_native_or_protected_files_changed": True,
        "no_raw_boards_absolute_coordinates_game_ids_or_action_sequences_persisted": True,
        "relative_displacements_are_aggregate_not_absolute_coordinates": True,
        "not_learned_feature_adoption_or_performance_proof": True,
        "all_public_games_reused": True,
        "errors": errors, "wall_seconds": round(time.perf_counter() - started, 6),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"output": output.relative_to(ROOT).as_posix(), "sha256": replay.base._sha(output), "result": report["result"], "wall_seconds": report["wall_seconds"], "errors": errors}, ensure_ascii=False))
    return 2 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
