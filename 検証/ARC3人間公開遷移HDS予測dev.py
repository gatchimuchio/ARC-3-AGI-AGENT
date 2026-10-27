#!/usr/bin/env python3
"""Evaluate ID-free HDS predictions from public human Action 6 transitions."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import random
import sys
from typing import Any
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "検証"))
sys.path.insert(0, str(ROOT / "HDS" / "学習系統" / "v0.4.2"))

from ARC3人間公開軌跡Action6事前学習評価 import (  # noqa: E402
    EXPECTED_DATASET_SHA256,
    _action_number,
    _available_actions,
    _changed_cells,
    _event_game_id,
    _integer_field,
    _latest_board,
    _recording_manifest,
    _sha256_file,
    _sha256_group_set,
)
from ARC3探索Actionローカル評価 import _load_games  # noqa: E402
from 接続.ARC3事前記憶 import VERSION as PRIOR_VERSION  # noqa: E402
from 接続.ARC3事前記憶 import 事前記憶をHDSへ供給する  # noqa: E402
from hds学習系統 import HDS学習系統  # noqa: E402
from hds学習系統.型 import 外部入力  # noqa: E402

BOUNDARY = "ARC3公開作用応答"
OUTCOMES = ("可視変化なし", "盤面変化", "レベル進行", "勝利")
RANK_TO_OUTCOME = dict(enumerate(OUTCOMES))
SPLIT_SEED = 20261027


def _json_hash(value: Any) -> str:
    data = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _source_tree_hash(path: Path) -> str:
    digest = hashlib.sha256()
    for source in sorted(path.rglob("*.py")):
        relative = source.relative_to(path).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(bytes.fromhex(_sha256_file(source)))
    return digest.hexdigest()


def _public_context(board: tuple[tuple[int, ...], ...], actions: set[int]) -> dict[str, Any]:
    """Mirror the ID-free public context in MyAgent._HDS作用前状態."""
    color_counts: Counter[int] = Counter(color for row in board for color in row)
    area = max(1, sum(len(row) for row in board))
    majority_share = max(color_counts.values(), default=0) / area
    occupancy_band = (
        "低"
        if majority_share < 0.25
        else "中低"
        if majority_share < 0.5
        else "中高"
        if majority_share < 0.75
        else "高"
    )
    return {
        "作用可能数": len(actions),
        "色種類数": len(color_counts),
        "最多色占有帯": occupancy_band,
    }


def _predicted_outcome_rank(result: Any) -> int | None:
    """Mirror MyAgent._HDS公開応答順位予測 without importing Kaggle's Agent base."""
    content = getattr(result, "内容", None)
    if not isinstance(content, dict) or getattr(result, "状態", None) not in (
        "出力",
        "断定保留",
    ):
        return None
    path = ("公開応答区分",)
    conflicts = content.get("競合群", ())
    if any(
        isinstance(item, dict) and tuple(item.get("結果経路", ())) == path
        for item in conflicts
    ):
        return None
    active_principles = {
        item.get("原理識別子")
        for item in content.get("有効原理群", ())
        if isinstance(item, dict)
        and tuple(item.get("結果経路", ())) == path
        and item.get("状態") == "適用範囲付き暫定原理"
        and item.get("採用状態") == "有効"
        and any(
            tuple(condition)[:1] == ("作用前公開状態",)
            for condition in item.get("条件経路群", ())
        )
        and any(
            tuple(condition) == ("作用", "番号")
            for condition in item.get("条件経路群", ())
        )
    }
    values = {
        item.get("予測値")
        for item in content.get("予測群", ())
        if isinstance(item, dict)
        and tuple(item.get("結果経路", ())) == path
        and item.get("原理参照") in active_principles
        and item.get("予測値") in OUTCOMES
    }
    if len(values) != 1:
        return None
    return OUTCOMES.index(next(iter(values)))


def _action6_examples(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    expected_game_id: str,
) -> tuple[list[tuple[dict[str, Any], str]], bool, Counter[str]]:
    examples: list[tuple[dict[str, Any], str]] = []
    counts: Counter[str] = Counter()
    seen_game_ids: set[str] = set()
    previous: dict[str, Any] | None = None
    version_matches = True

    with archive.open(info) as stream:
        for line in stream:
            wrapper = json.loads(line)
            event = wrapper.get("data") if isinstance(wrapper, dict) else None
            if not isinstance(event, dict):
                counts["invalid_events"] += 1
                previous = None
                continue

            observed_game_id = _event_game_id(event)
            if observed_game_id is not None:
                seen_game_ids.add(observed_game_id)
                if observed_game_id != expected_game_id:
                    version_matches = False

            board_after = _latest_board(event)
            action_input = event.get("action_input")
            action_number = (
                _action_number(action_input.get("id"))
                if isinstance(action_input, dict)
                else None
            )

            if action_number == 0:
                previous = event
                continue

            if previous is not None and action_number == 6:
                counts["action6_transitions"] += 1
                board_before = _latest_board(previous)
                payload = action_input.get("data") if isinstance(action_input, dict) else None
                x = payload.get("x") if isinstance(payload, dict) else None
                y = payload.get("y") if isinstance(payload, dict) else None
                if (
                    board_before is None
                    or board_after is None
                    or not isinstance(payload, dict)
                    or type(x) is not int
                    or type(y) is not int
                    or not (0 <= x < len(board_before[0]) and 0 <= y < len(board_before))
                    or 6 not in _available_actions(previous)
                    or previous.get("state") != "NOT_FINISHED"
                ):
                    counts["invalid_action6_transitions"] += 1
                else:
                    public_context = _public_context(board_before, _available_actions(previous))
                    if event.get("state") == "WIN":
                        outcome = "勝利"
                    elif _integer_field(event, "levels_completed") > _integer_field(
                        previous, "levels_completed"
                    ):
                        outcome = "レベル進行"
                    elif board_before != board_after:
                        outcome = "盤面変化"
                    else:
                        outcome = "可視変化なし"
                    content = {
                        "作用前公開状態": public_context,
                        "作用": {"番号": 6, "引数あり": True},
                        "公開応答区分": outcome,
                    }
                    examples.append((content, outcome))
                    counts["usable_action6_transitions"] += 1

            previous = event

    if seen_game_ids != {expected_game_id}:
        version_matches = False
    return examples, version_matches, counts


def _read_dataset(
    archive_path: Path,
    environment_dir: Path,
    split_seed: int,
    train_groups_count: int,
    dev_groups_count: int,
) -> tuple[
    dict[str, list[tuple[dict[str, Any], str]]],
    dict[str, list[tuple[dict[str, Any], str]]],
    dict[str, Any],
]:
    current_game_ids: dict[str, str] = {}
    for metadata, metadata_path in _load_games(environment_dir):
        group = metadata_path.parent.parent.name
        if group in current_game_ids:
            raise RuntimeError("more than one current environment metadata file per group")
        current_game_ids[group] = str(metadata["game_id"])
    if len(current_game_ids) != 25:
        raise RuntimeError("expected all 25 current public environment groups")

    with zipfile.ZipFile(archive_path) as archive:
        exact_by_group, source_counts = _recording_manifest(archive, current_game_ids)
        groups = sorted(exact_by_group)
        if len(groups) != 10 or train_groups_count + dev_groups_count != len(groups):
            raise RuntimeError("current-version human data group count differs from reviewed split")
        random.Random(split_seed).shuffle(groups)
        train_groups = groups[:train_groups_count]
        dev_groups = groups[train_groups_count : train_groups_count + dev_groups_count]
        train: dict[str, list[tuple[dict[str, Any], str]]] = {}
        dev: dict[str, list[tuple[dict[str, Any], str]]] = {}
        extraction_counts: Counter[str] = Counter()

        for role, selected_groups, destination in (
            ("train", train_groups, train),
            ("dev", dev_groups, dev),
        ):
            for group in sorted(selected_groups):
                examples: list[tuple[dict[str, Any], str]] = []
                for info in sorted(exact_by_group[group], key=lambda item: item.filename):
                    rows, version_matches, counts = _action6_examples(
                        archive, info, current_game_ids[group]
                    )
                    extraction_counts.update(counts)
                    if version_matches:
                        examples.extend(rows)
                    else:
                        extraction_counts["recordings_rejected_for_version_conflict"] += 1
                destination[group] = examples
                print(
                    f"PROGRESS role={role} group={len(destination)}/{len(selected_groups)} "
                    f"usable_action6={len(examples)}",
                    flush=True,
                )

    if _sha256_group_set(sorted(train)) != "7efd0d9e8b1f552b4582211c4227458129f1fbf27d12abf7a6e372d8e2261e9c":
        raise RuntimeError("train split differs from C2-093 reviewed environment split")
    if _sha256_group_set(sorted(dev)) != "cb5aa32cd1a3847478e2f46c119bb1a8dc1b1ae1009bccb4b739a9f9bb568f93":
        raise RuntimeError("dev split differs from C2-093 reviewed environment split")

    metadata = {
        "source_counts": dict(source_counts),
        "extraction_counts": dict(extraction_counts),
        "current_version_environment_groups": len(groups),
        "train_groups": len(train),
        "dev_groups": len(dev),
        "train_group_digest": _sha256_group_set(sorted(train)),
        "dev_group_digest": _sha256_group_set(sorted(dev)),
        "train_groups_with_action6": sum(bool(rows) for rows in train.values()),
        "dev_groups_with_action6": sum(bool(rows) for rows in dev.values()),
    }
    return train, dev, metadata


def _train_sample(
    train_groups: dict[str, list[tuple[dict[str, Any], str]]],
    per_group_limit: int,
    seed: int,
) -> list[tuple[dict[str, Any], str]]:
    rng = random.Random(seed ^ 0xA6C3)
    selected: list[tuple[dict[str, Any], str]] = []
    for group in sorted(train_groups):
        rows = train_groups[group]
        if not rows:
            continue
        sample = rows if len(rows) <= per_group_limit else rng.sample(rows, per_group_limit)
        selected.extend(sample)
    return selected


def _dev_sample(
    dev_groups: dict[str, list[tuple[dict[str, Any], str]]],
    per_group_limit: int,
    seed: int,
) -> list[tuple[dict[str, Any], str]]:
    rng = random.Random(seed ^ 0xD3C3)
    selected: list[tuple[dict[str, Any], str]] = []
    for group in sorted(dev_groups):
        rows = dev_groups[group]
        if not rows:
            continue
        selected.extend(rows if len(rows) <= per_group_limit else rng.sample(rows, per_group_limit))
    return selected


def _fit_and_query(
    training: list[tuple[dict[str, Any], str]],
    development: list[tuple[dict[str, Any], str]],
) -> dict[str, Any]:
    hds = HDS学習系統()
    prior_report = 事前記憶をHDSへ供給する(hds)
    learning_states: Counter[str] = Counter()
    for index, (content, _) in enumerate(training, start=1):
        result = hds.処理する(
            外部入力(
                content,
                BOUNDARY,
                主体="ARC3 public human demonstration transition",
                目的="学習評価用の公開観測遷移。因果確定・Action認可には使わない",
            )
        )
        learning_states[str(result.状態)] += 1
        if index % 16 == 0:
            print(f"PROGRESS hds_update={index}/{len(training)}", flush=True)

    majority = Counter(label for _, label in training).most_common(1)[0][0]
    hds_predictions: list[str | None] = []
    query_states: Counter[str] = Counter()
    predicted_outcomes: Counter[str] = Counter()
    for index, (content, _) in enumerate(development, start=1):
        result = hds.照会する(
            外部入力(
                {key: value for key, value in content.items() if key != "公開応答区分"},
                BOUNDARY,
                主体="ARC3 held-out public human transition",
                目的="未見環境の公開応答区分予測。追加学習なし",
            )
        )
        query_states[str(result.状態)] += 1
        rank = _predicted_outcome_rank(result)
        predicted = RANK_TO_OUTCOME.get(rank) if rank is not None else None
        hds_predictions.append(predicted)
        if predicted is not None:
            predicted_outcomes[predicted] += 1
        if index % 64 == 0:
            print(f"PROGRESS hds_query={index}/{len(development)}", flush=True)

    truth = [label for _, label in development]
    hds_covered = [predicted is not None for predicted in hds_predictions]
    covered_count = sum(hds_covered)
    covered_correct = sum(
        predicted == actual
        for predicted, actual in zip(hds_predictions, truth)
        if predicted is not None
    )
    baseline_correct = sum(majority == actual for actual in truth)
    fallback_predictions = [
        predicted if predicted is not None else majority for predicted in hds_predictions
    ]
    fallback_correct = sum(
        predicted == actual for predicted, actual in zip(fallback_predictions, truth)
    )
    predictions_digest = _json_hash(
        {"truth": truth, "hds_predictions": hds_predictions, "fallback": fallback_predictions}
    )
    return {
        "prior_memory": prior_report,
        "trained_state_version": hds.エンジン.状態.現在版,
        "training_examples": len(training),
        "training_outcome_counts": dict(Counter(label for _, label in training)),
        "learning_state_counts": dict(learning_states),
        "development_examples": len(development),
        "development_outcome_counts": dict(Counter(truth)),
        "hds_query_state_counts": dict(query_states),
        "hds_prediction_counts": dict(predicted_outcomes),
        "hds_coverage": covered_count / max(1, len(development)),
        "hds_covered_accuracy": covered_correct / max(1, covered_count),
        "majority_baseline_label": majority,
        "majority_baseline_accuracy": baseline_correct / max(1, len(development)),
        "hds_with_majority_fallback_accuracy": fallback_correct / max(1, len(development)),
        "fallback_accuracy_delta": (fallback_correct - baseline_correct)
        / max(1, len(development)),
        "prediction_digest_sha256": predictions_digest,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--human-archive", type=Path, required=True)
    parser.add_argument("--expected-archive-sha256", required=True)
    parser.add_argument(
        "--environment-dir", type=Path, default=ROOT / "入力/Kaggle/environment_files"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split-seed", type=int, default=SPLIT_SEED)
    parser.add_argument("--train-per-group", type=int, default=32)
    parser.add_argument("--dev-per-group", type=int, default=100)
    parser.add_argument("--minimum-fallback-delta", type=float, default=0.05)
    parser.add_argument("--minimum-coverage", type=float, default=0.10)
    args = parser.parse_args()

    if args.expected_archive_sha256 != EXPECTED_DATASET_SHA256:
        raise ValueError("requested archive hash is not the reviewed dataset snapshot")
    if min(args.train_per_group, args.dev_per_group) < 1:
        raise ValueError("sample limits must be positive")
    started = datetime.now(timezone.utc)
    archive_sha = _sha256_file(args.human_archive)
    if archive_sha != args.expected_archive_sha256:
        raise ValueError("human dataset archive SHA-256 mismatch")

    train_groups, dev_groups, source = _read_dataset(
        args.human_archive,
        args.environment_dir,
        args.split_seed,
        train_groups_count=7,
        dev_groups_count=3,
    )
    training = _train_sample(train_groups, args.train_per_group, args.split_seed)
    development = _dev_sample(dev_groups, args.dev_per_group, args.split_seed)
    if len(training) < 12 or not development:
        raise RuntimeError("too few ID-free human transitions for a bounded HDS evaluation")
    if any(
        "game_id" in json.dumps(content, ensure_ascii=True)
        or '"x"' in json.dumps(content, ensure_ascii=True)
        or '"y"' in json.dumps(content, ensure_ascii=True)
        for content, _ in training + development
    ):
        raise RuntimeError("identifier or raw coordinate reached an HDS input")

    first = _fit_and_query(training, development)
    repeat = _fit_and_query(training, development)
    reproduced = (
        first["prediction_digest_sha256"] == repeat["prediction_digest_sha256"]
        and first["hds_with_majority_fallback_accuracy"]
        == repeat["hds_with_majority_fallback_accuracy"]
        and first["hds_coverage"] == repeat["hds_coverage"]
    )
    gate = (
        first["fallback_accuracy_delta"] >= args.minimum_fallback_delta
        and first["hds_coverage"] >= args.minimum_coverage
        and reproduced
    )
    output = {
        "schema": "arc3-human-action6-hds-prediction-dev.v1",
        "run_id": "C2-094_human-public-demo-action6-hds-prediction-dev",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": {
            "archive_sha256": archive_sha,
            "archive_bytes": args.human_archive.stat().st_size,
            "kaggle_license_label": "other",
            "official_article_replays": 342,
            "mirror_recording_files": source["source_counts"].get("recording_files"),
            "current_version_recordings": source["source_counts"].get(
                "current_version_recordings"
            ),
            "stale_version_recordings_excluded": source["source_counts"].get(
                "stale_version_recordings"
            ),
            "human_reasoning_used": False,
            "game_and_session_ids_used_as_features": False,
            "raw_coordinates_used_as_features": False,
        },
        "split": {
            "seed": args.split_seed,
            "train_groups": source["train_groups"],
            "dev_groups": source["dev_groups"],
            "train_group_digest": source["train_group_digest"],
            "dev_group_digest": source["dev_group_digest"],
            "train_groups_with_action6": source["train_groups_with_action6"],
            "dev_groups_with_action6": source["dev_groups_with_action6"],
        },
        "features": [
            "legal_action_count",
            "distinct_color_count",
            "dominant_color_occupancy_band",
            "action_number_6",
            "has_action_arguments",
        ],
        "hds": {
            "version": "HDS/学習系統/v0.4.2",
            "prior_memory_version": PRIOR_VERSION,
            "source_tree_sha256": _source_tree_hash(ROOT / "HDS" / "学習系統" / "v0.4.2"),
            "agent_sha256": _sha256_file(ROOT / "接続" / "ARC3提出agent.py"),
            "minimum_support": 3,
            "maximum_conditions": 2,
            "training_per_group_limit": args.train_per_group,
            "development_per_group_limit": args.dev_per_group,
            "training_input_digest_sha256": _json_hash(training),
            "training_examples_total": len(training),
            "development_examples_total": len(development),
            "no_development_updates": True,
        },
        "evaluation": {
            "baseline_and_candidate": "train-majority outcome versus HDS prediction with majority fallback",
            "baseline": first,
            "repeat": repeat,
            "same_run_reproduced": reproduced,
            "minimum_fallback_delta": args.minimum_fallback_delta,
            "minimum_hds_coverage": args.minimum_coverage,
            "gate_passed": gate,
            "decision": "ADVANCE_TO_PUBLIC_GAME_SCORE_EVAL" if gate else "REJECT_HDS_PRIOR",
            "elapsed_seconds": round(
                (datetime.now(timezone.utc) - started).total_seconds(), 3
            ),
        },
        "source_counts": source,
        "official_submission_made": False,
        "notebook_or_kernel_changed": False,
        "limitations": [
            "Predicting human public Action 6 outcome categories is a diagnostic, not an ARC3 game score.",
            "The Kaggle dataset mirror has 340 recordings while the official article reports 342; the gap is unresolved.",
            "The Kaggle mirror license label is other; the learned HDS state is local-only and is not packaged for competition.",
        ],
    }

    serialized = json.dumps(output, ensure_ascii=True, sort_keys=True)
    forbidden = ('"game_id"', '"level_id"', '"session_id"', '"x"', '"y"')
    if any(token in serialized for token in forbidden):
        raise RuntimeError("identifier or coordinate key leaked into the persisted scorecard")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"decision": output["evaluation"]["decision"], "scorecard": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
