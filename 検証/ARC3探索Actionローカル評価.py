"""公開ARC3環境でHOLD・合法ランダム・観測駆動探索を比較する再現評価。"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
from pathlib import Path
import random
import sys
from typing import Any

from arc_agi import EnvironmentInfo, LocalEnvironmentWrapper
from arcengine import GameAction

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from 接続.ARC3境界 import 観測する
from 接続.観測駆動探索Action import 観測駆動探索方針


class _中間Frame差分no_op罰ablation(観測駆動探索方針):
    """中間grid差分を含む最終盤面不変Actionだけ罰を相殺する評価専用方針。"""

    def 応答を記録する(self, 作用前, action, 作用後):
        response = super().応答を記録する(作用前, action, 作用後)
        中間差分あり = any(frame != 作用後.最新盤面 for frame in 作用後.盤面列[:-1])
        if (
            作用前.最新盤面 == 作用後.最新盤面
            and max(0, 作用後.完了レベル数 - 作用前.完了レベル数) == 0
            and 中間差分あり
        ):
            self._報酬合計[action.作用番号] += 1.0
            if action.作用番号 == 6:
                色 = response["座標可視色"]
                if 色 is None:
                    raise RuntimeError("ACTION6の中間Frame ablationに選択色がない")
                self._色報酬合計[色] += 1.0
            response["公開応答報酬"] += 1.0
        return response


class _ACTION6座標ablation:
    """色UCBは本番方針と同一に保つ評価専用座標選択の共通処理。"""

    def _色候補を優先する(self, 盤面, 適格色):
        return 適格色

    def _色と未試行座標を得る(self, 盤面):
        if (
            not 盤面
            or len(盤面) > 64
            or any(not row or len(row) > 64 for row in 盤面)
            or any(len(row) != len(盤面[0]) for row in 盤面)
        ):
            return None
        色座標: dict[int, list[tuple[int, int]]] = {}
        for y, row in enumerate(盤面):
            for x, color in enumerate(row):
                色座標.setdefault(color, []).append((x, y))
        色候補 = sorted(色座標)
        試行済み = self._座標試行.setdefault(盤面, set())
        未試行色座標 = {
            color: [point for point in 色座標[color] if point not in 試行済み] for color in 色候補
        }
        適格色 = [color for color in 色候補 if 未試行色座標[color]]
        if not 適格色:
            return None
        適格色 = self._色候補を優先する(盤面, 適格色)

        未試行色 = [color for color in 適格色 if self._色回数.get(color, 0) == 0]
        if 未試行色:
            color = self._rng.choice(未試行色)
        else:
            total = max(2, sum(self._色回数.values()))
            values = {
                color: self._色報酬合計[color] / self._色回数[color]
                + self._色探索係数 * math.sqrt(math.log(total) / self._色回数[color])
                for color in 適格色
            }
            best = max(values.values())
            color = self._rng.choice([color for color in 適格色 if values[color] == best])
        return color, 未試行色座標[color], 試行済み


class _ACTION6中心距離順ablation(_ACTION6座標ablation, 観測駆動探索方針):
    """ACTION6の色選択を保ち、同色未試行座標だけ中心距離順にする評価専用方針。"""

    def _座標を選ぶ(self, 盤面):
        selected = self._色と未試行座標を得る(盤面)
        if selected is None:
            return None
        color, points, 試行済み = selected

        width = len(盤面[0])
        height = len(盤面)
        center_x = (width - 1) / 2
        center_y = (height - 1) / 2
        minimum_distance = min((x - center_x) ** 2 + (y - center_y) ** 2 for x, y in points)
        nearest = [
            point
            for point in points
            if (point[0] - center_x) ** 2 + (point[1] - center_y) ** 2 == minimum_distance
        ]
        point = self._rng.choice(nearest)
        試行済み.add(point)
        return point[0], point[1], color


class _ACTION6同色近傍ありablation(_ACTION6座標ablation, 観測駆動探索方針):
    """同色未試行座標に同色4近傍があればその集合を優先する評価専用方針。"""

    def _座標を選ぶ(self, 盤面):
        selected = self._色と未試行座標を得る(盤面)
        if selected is None:
            return None
        color, points, 試行済み = selected
        height, width = len(盤面), len(盤面[0])
        connected = [
            point
            for point in points
            if any(
                0 <= point[0] + dx < width
                and 0 <= point[1] + dy < height
                and 盤面[point[1] + dy][point[0] + dx] == color
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))
            )
        ]
        point = self._rng.choice(connected or points)
        試行済み.add(point)
        return point[0], point[1], color


class _ACTION6中間頻度色遅延ablation(_ACTION6座標ablation, 観測駆動探索方針):
    """他bucketに未試行色がある間だけ中間頻度色を候補から外す。"""

    def _色候補を優先する(self, 盤面, 適格色):
        counts: dict[int, int] = {}
        for row in 盤面:
            for color in row:
                counts[color] = counts.get(color, 0) + 1
        total = sum(counts.values())
        maximum = max(counts.values())
        preferred = [
            color for color in 適格色 if counts[color] == maximum or counts[color] / total < 0.10
        ]
        if preferred and len(preferred) < len(適格色):
            self._middle_frequency_color_deferrals = (
                getattr(self, "_middle_frequency_color_deferrals", 0) + 1
            )
        return preferred or 適格色


class _レベル進行時色統計resetablation(観測駆動探索方針):
    """正のlevel進行後にACTION6の色UCB統計だけを初期化する評価専用方針。"""

    def 応答を記録する(self, 作用前, action, 作用後):
        response = super().応答を記録する(作用前, action, 作用後)
        if 作用後.完了レベル数 > 作用前.完了レベル数:
            self._色回数.clear()
            self._色報酬合計.clear()
        return response


class _レベル進行時ActionUCB統計resetablation(観測駆動探索方針):
    """正のlevel進行後にAction番号別UCB統計だけを初期化する評価専用方針。"""

    def 応答を記録する(self, 作用前, action, 作用後):
        response = super().応答を記録する(作用前, action, 作用後)
        if 作用後.完了レベル数 > 作用前.完了レベル数:
            self._回数.clear()
            self._報酬合計.clear()
            self._総作用数 = 0
        return response


class _GAME_OVER罰ablation(観測駆動探索方針):
    """level進行なしでGAME_OVERとなったActionへ追加の-1.0報酬を与える評価専用方針。"""

    def 応答を記録する(self, 作用前, action, 作用後):
        response = super().応答を記録する(作用前, action, 作用後)
        if 作用後.状態 == "GAME_OVER" and 作用後.完了レベル数 <= 作用前.完了レベル数:
            self._報酬合計[action.作用番号] -= 1.0
            if action.作用番号 == 6:
                color = response["座標可視色"]
                if color is None:
                    raise RuntimeError("ACTION6のGAME_OVER ablationに選択色がない")
                self._色報酬合計[color] -= 1.0
            response["公開応答報酬"] -= 1.0
        return response


class _初期観測hashseedablation(観測駆動探索方針):
    """初回公開状態から一度だけ決定seedを導く評価専用方針。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._初期観測seed適用済み = False

    def 選ぶ(self, 現在):
        if not self._初期観測seed適用済み and 現在.状態 == "NOT_FINISHED":
            self._rng = random.Random(_初期公開観測seed(現在))
            self._初期観測seed適用済み = True
        return super().選ぶ(現在)


class _同一Action停滞上限ablation(観測駆動探索方針):
    """レベル未進行で同じ合法Actionを8回続けた後、別Actionがあれば切り替える。"""

    _連続上限 = 8

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._直前Action番号: int | None = None
        self._無進行連続数 = 0
        self._上限介入action位置: list[int] = []
        self._今回上限有効 = False

    def 選ぶ(self, 現在):
        合法 = tuple(sorted(a for a in 現在.作用可能番号 if 1 <= a <= 7))
        代替 = tuple(a for a in 合法 if a != self._直前Action番号)
        未試行代替 = any(self._回数.get(a, 0) == 0 for a in 代替)
        self._今回上限有効 = (
            self._無進行連続数 >= self._連続上限
            and self._直前Action番号 in 合法
            and bool(代替)
            and not 未試行代替
        )
        選択 = super().選ぶ(現在)
        if (
            self._今回上限有効
            and 選択 is not None
            and 選択.作用番号 != self._直前Action番号
        ):
            self._上限介入action位置.append(self._総作用数)
        return 選択

    def _追加行動価値(self, 現在, 作用番号: int) -> float:
        if self._今回上限有効 and 作用番号 == self._直前Action番号:
            return float("-inf")
        return super()._追加行動価値(現在, 作用番号)

    def 応答を記録する(self, 作用前, action, 作用後):
        response = super().応答を記録する(作用前, action, 作用後)
        進行 = 作用後.完了レベル数 > 作用前.完了レベル数
        if 進行 or 作用後.状態 in ("GAME_OVER", "WIN"):
            self._直前Action番号 = None
            self._無進行連続数 = 0
        elif action.作用番号 == self._直前Action番号:
            self._無進行連続数 += 1
        else:
            self._直前Action番号 = action.作用番号
            self._無進行連続数 = 1
        self._今回上限有効 = False
        return response


def _初期公開観測seed(現在) -> int:
    material = json.dumps(
        {
            "state": 現在.状態,
            "board": 現在.最新盤面,
            "available_actions": sorted(現在.作用可能番号),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256(material).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


def _盤面差分(before, after) -> int:
    old, new = before.最新盤面, after.最新盤面
    if not old or not new or len(old) != len(new):
        return int(old != new)
    return sum(
        1
        for old_row, new_row in zip(old, new)
        for x in range(max(len(old_row), len(new_row)))
        if x >= len(old_row) or x >= len(new_row) or old_row[x] != new_row[x]
    )


def _policy_seed(environment_seed: int, configured_policy_seed: int | None) -> int:
    """未指定時は従来動作を保ち、指定時だけpolicy RNGを分離する。"""
    return environment_seed if configured_policy_seed is None else configured_policy_seed


def _run_game(
    metadata: dict[str, Any],
    metadata_path: Path,
    policy_name: str,
    *,
    seed: int,
    policy_seed: int | None = None,
    max_actions: int,
    retry_game_over: bool = False,
    reset_policy_each_level: bool = False,
    visible_change_coefficient: float = 0.25,
    level_progress_reward: float = 4.0,
    exploration_coefficient: float = 0.8,
    coordinate_color_exploration_coefficient: float | None = None,
    avoid_same_board_noop_action: bool = False,
    prioritize_coordinate_action_first: bool = False,
    exempt_intermediate_frame_noop_penalty: bool = False,
    prioritize_center_distance_action6: bool = False,
    reset_coordinate_color_stats_each_level: bool = False,
    reset_action_ucb_stats_each_level: bool = False,
    prefer_connected_action6: bool = False,
    defer_middle_frequency_action6_color: bool = False,
    penalize_game_over_action: bool = False,
    hash_seed_from_initial_observation: bool = False,
    policy_type_override: type[観測駆動探索方針] | None = None,
) -> dict[str, Any]:
    info = EnvironmentInfo(
        game_id=metadata["game_id"],
        class_name=metadata.get("class_name"),
        local_dir=str(metadata_path.parent),
    )
    env = LocalEnvironmentWrapper(
        info,
        logging.getLogger("arc3-local-evaluation"),
        f"local-{policy_name}",
        seed=seed,
    )
    enabled_ablations = sum(
        (
            exempt_intermediate_frame_noop_penalty,
            prioritize_center_distance_action6,
            reset_coordinate_color_stats_each_level,
            reset_action_ucb_stats_each_level,
            prefer_connected_action6,
            defer_middle_frequency_action6_color,
            penalize_game_over_action,
            hash_seed_from_initial_observation,
            reset_policy_each_level,
        )
    )
    if enabled_ablations > 1:
        raise ValueError("評価専用ablationは同時に1つだけ指定できます")
    if policy_type_override is not None and enabled_ablations:
        raise ValueError("policy type overrideと既存ablationは併用できません")
    policy_type = policy_type_override or (
        _中間Frame差分no_op罰ablation
        if exempt_intermediate_frame_noop_penalty
        else _ACTION6中心距離順ablation
        if prioritize_center_distance_action6
        else _レベル進行時色統計resetablation
        if reset_coordinate_color_stats_each_level
        else _レベル進行時ActionUCB統計resetablation
        if reset_action_ucb_stats_each_level
        else _ACTION6同色近傍ありablation
        if prefer_connected_action6
        else _ACTION6中間頻度色遅延ablation
        if defer_middle_frequency_action6_color
        else _GAME_OVER罰ablation
        if penalize_game_over_action
        else _初期観測hashseedablation
        if hash_seed_from_initial_observation
        else 観測駆動探索方針
    )
    policy = (
        policy_type(
            乱数種=_policy_seed(seed, policy_seed),
            探索係数=exploration_coefficient,
            色探索係数=coordinate_color_exploration_coefficient,
            可視変化係数=visible_change_coefficient,
            レベル進行報酬=level_progress_reward,
            座標Action初手優先=prioritize_coordinate_action_first,
            同盤無変化Action回避=avoid_same_board_noop_action,
        )
        if policy_name == "exploration"
        else None
    )
    rng = random.Random(seed)
    raw = env.observation_space
    records: list[dict[str, Any]] = []
    seen_boards: set[tuple[tuple[int, ...], ...]] = set()
    no_op = 0
    observation_no = 0
    duplicate_observations = 0
    illegal_actions = 0
    reset_actions = 0
    game_over_events = 0
    best_levels_completed = 0
    last_signature = None
    action_signatures_on_board: set[tuple[int, tuple[tuple[str, int], ...]]] = set()
    tracked_board = current_board = None
    acted_observations: set[str] = set()
    current = 観測する(raw, 観測通番=observation_no)
    initial = current
    current_board = current.最新盤面
    tracked_board = current_board
    seen_boards.add(current.最新盤面)
    stop_reason = "action_limit"

    for _ in range(max_actions):
        choice = None
        if current.状態 == "WIN":
            stop_reason = "WIN"
            break
        if current.状態 == "GAME_OVER":
            if not retry_game_over:
                stop_reason = "GAME_OVER"
                break
            if policy is not None:
                choice = policy.選ぶ(current)
                if choice is None or choice.作用番号 != 0 or choice.出所 != "SDKリセット":
                    stop_reason = "reset_unavailable"
                    break
                action_id, data, source = choice.作用番号, dict(choice.引数), choice.出所
            else:
                action_id, data, source = 0, {}, "SDKリセット"
        elif current.状態 != "NOT_FINISHED":
            stop_reason = f"state:{current.状態}"
            break
        else:
            legal = [a for a in current.作用可能番号 if 1 <= a <= 7]
            if not legal:
                stop_reason = "no_legal_non_reset_action"
                break
            if policy is not None:
                choice = policy.選ぶ(current)
                if choice is None:
                    stop_reason = "exploration_hold"
                    break
                action_id, data = choice.作用番号, dict(choice.引数)
                source = choice.出所
            else:
                action_id = rng.choice(legal)
                data = {"x": rng.randrange(64), "y": rng.randrange(64)} if action_id == 6 else {}
                source = "uniform_random"

        is_reset = action_id == 0
        reset_allowed = retry_game_over and current.状態 == "GAME_OVER"
        if is_reset and not (reset_allowed and source == "SDKリセット" and not data):
            illegal_actions += 1
            raise RuntimeError("RESET was emitted outside the GAME_OVER lifecycle")
        if not is_reset and action_id not in current.作用可能番号:
            illegal_actions += 1
            raise RuntimeError("policy emitted an Action outside the current legal set")
        if current.指紋 in acted_observations:
            duplicate_observations += 1
            raise RuntimeError("policy attempted two steps on the same SDK observation")
        acted_observations.add(current.指紋)
        if current_board != tracked_board:
            tracked_board = current_board
            action_signatures_on_board.clear()
        if is_reset:
            signature = None
            same_board_repeat = False
            consecutive_repeat = False
            reset_actions += 1
            last_signature = None
        else:
            signature = (action_id, tuple(sorted(data.items())))
            same_board_repeat = signature in action_signatures_on_board
            consecutive_repeat = signature == last_signature
            action_signatures_on_board.add(signature)
            last_signature = signature
        response = env.step(
            GameAction.from_id(action_id),
            data=data,
            reasoning={"local_policy": source},
        )
        if response is None:
            stop_reason = "missing_sdk_response"
            break
        observation_no += 1
        after = 観測する(response, 観測通番=observation_no)
        changes = _盤面差分(current, after)
        novel = bool(after.最新盤面) and after.最新盤面 not in seen_boards
        progress = after.完了レベル数 - current.完了レベル数
        if not is_reset:
            no_op += int(changes == 0 and progress == 0)
        best_levels_completed = max(best_levels_completed, after.完了レベル数)
        game_over_events += int(after.状態 == "GAME_OVER")
        record = {
            "source": source,
            "action_id": action_id,
            "data": data,
            "before_state": current.状態,
            "after_state": after.状態,
            "level_delta": progress,
            "changed_cells": changes,
            "new_visible_board": novel,
            "same_visible_board_action_repeat": same_board_repeat,
            "consecutive_exact_action_repeat": consecutive_repeat,
            "lifecycle_action": is_reset,
        }
        if policy is not None and not is_reset:
            record["policy_response"] = policy.応答を記録する(current, choice, after)
            if reset_policy_each_level and progress > 0:
                rng_state = policy._rng.getstate()
                policy = 観測駆動探索方針(
                    乱数種=seed,
                    可視変化係数=visible_change_coefficient,
                    レベル進行報酬=level_progress_reward,
                    座標Action初手優先=prioritize_coordinate_action_first,
                )
                policy._rng.setstate(rng_state)
        records.append(record)
        current = after
        current_board = current.最新盤面
        if current.最新盤面:
            seen_boards.add(current.最新盤面)
        if current.状態 == "WIN":
            stop_reason = "WIN"
            break
        if current.状態 == "GAME_OVER" and not retry_game_over:
            stop_reason = "GAME_OVER"
            break

    return {
        "game_id": metadata["game_id"],
        "policy": policy_name,
        "seed": seed,
        "max_actions": max_actions,
        "initial_state": initial.状態,
        "initial_levels_completed": initial.完了レベル数,
        "initial_available_actions": list(initial.作用可能番号),
        "initial_board": initial.最新盤面,
        "final_state": current.状態,
        "levels_completed": best_levels_completed,
        "final_levels_completed": current.完了レベル数,
        "actions": len(records),
        "gameplay_actions": len(records) - reset_actions,
        "reset_actions": reset_actions,
        "attempts": reset_actions + 1,
        "game_over_events": game_over_events,
        "visible_unique_boards": len(seen_boards),
        "no_op_actions": no_op,
        "same_visible_board_action_repeats": sum(
            r["same_visible_board_action_repeat"] for r in records
        ),
        "consecutive_exact_action_repeats": sum(
            r["consecutive_exact_action_repeat"] for r in records
        ),
        "duplicate_observation_steps": duplicate_observations,
        "illegal_action_attempts": illegal_actions,
        "stop_reason": stop_reason,
        "action_responses": records,
        "policy_action_stats": policy.統計() if policy is not None else {},
        "policy_diagnostics": {
            "same_action_streak_cap": getattr(policy, "_連続上限", None),
            "same_action_streak_cap_intervention_positions": getattr(
                policy, "_上限介入action位置", []
            ),
        }
        if policy is not None
        else {},
        "middle_frequency_color_deferrals": (
            int(getattr(policy, "_middle_frequency_color_deferrals", 0))
            if policy is not None
            else 0
        ),
    }


def _load_games(environment_dir: Path) -> list[tuple[dict[str, Any], Path]]:
    result = []
    for path in sorted(environment_dir.rglob("metadata.json")):
        metadata = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(metadata, dict) and isinstance(metadata.get("game_id"), str):
            result.append((metadata, path))
    if not result:
        raise RuntimeError(f"No public environment metadata found under {environment_dir}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--environment-dir",
        type=Path,
        default=ROOT / "入力/Kaggle/environment_files",
    )
    parser.add_argument("--stage", choices=("dev", "holdout", "all"), default="dev")
    parser.add_argument("--split-seed", type=int, default=20261022)
    parser.add_argument("--seed", type=int, default=31)
    parser.add_argument(
        "--policy-seed",
        type=int,
        default=None,
        help="optional RNG seed for the exploration policy; defaults to --seed",
    )
    parser.add_argument("--max-actions", type=int, default=80)
    parser.add_argument("--retry-game-over", action="store_true")
    parser.add_argument(
        "--ablate-level-transfer",
        action="store_true",
        help="also compare exploration with per-level action statistics reset",
    )
    parser.add_argument(
        "--exploration-coefficient",
        type=float,
        default=0.8,
        help="UCB exploration weight",
    )
    parser.add_argument(
        "--visible-change-coefficient",
        type=float,
        default=0.25,
        help="reward weight for normalized visible board change",
    )
    parser.add_argument(
        "--level-progress-reward",
        type=float,
        default=4.0,
        help="reward weight for completing a level",
    )
    parser.add_argument(
        "--coordinate-color-exploration-coefficient",
        type=float,
        default=None,
        help="optional UCB exploration weight for visible color selection within Action 6",
    )
    parser.add_argument(
        "--avoid-same-board-noop-action",
        action="store_true",
        help="avoid a discrete action that was a no-op on the same visible board when alternatives exist",
    )
    parser.add_argument(
        "--prioritize-coordinate-action-first",
        action="store_true",
        help="try the coordinate Action first when it is legal and untried",
    )
    parser.add_argument(
        "--exempt-intermediate-frame-noop-penalty",
        action="store_true",
        help="local ablation: cancel the no-op penalty when an intermediate grid differs from the unchanged final grid",
    )
    parser.add_argument(
        "--prioritize-center-distance-action6",
        action="store_true",
        help="local ablation: choose a nearest-to-center untried coordinate after existing Action 6 color selection",
    )
    parser.add_argument(
        "--reset-coordinate-color-stats-each-level",
        action="store_true",
        help="local ablation: reset only Action 6 color UCB counts/rewards after level progress",
    )
    parser.add_argument(
        "--reset-action-ucb-stats-each-level",
        action="store_true",
        help="local ablation: reset only action-number UCB counts/rewards after level progress",
    )
    parser.add_argument(
        "--prefer-connected-action6",
        action="store_true",
        help="local ablation: prefer untried Action 6 cells with at least one same-color orthogonal neighbor",
    )
    parser.add_argument(
        "--defer-middle-frequency-action6-color",
        action="store_true",
        help="local ablation: defer Action 6 colors in the 10-50%% non-dominant frequency bucket when alternatives remain",
    )
    parser.add_argument(
        "--penalize-game-over-action",
        action="store_true",
        help="local ablation: subtract 1.0 from Action/color reward after GAME_OVER without level progress",
    )
    parser.add_argument(
        "--hash-seed-from-initial-observation",
        action="store_true",
        help="local ablation: seed exploration RNG from the first public board and legal Action set",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "出力/ARC3-RUN-002-local/C2-evaluation.json",
    )
    args = parser.parse_args()
    if args.max_actions < 1:
        parser.error("--max-actions must be positive")
    games = _load_games(args.environment_dir)
    split = list(games)
    random.Random(args.split_seed).shuffle(split)
    dev = split[:5]
    holdout = split[5:]
    selected = dev if args.stage == "dev" else holdout if args.stage == "holdout" else split
    output_games = []

    policy_names = ["random", "exploration"]
    if args.ablate_level_transfer:
        policy_names.append("exploration_level_reset")
    if args.reset_action_ucb_stats_each_level:
        policy_names.append("exploration_action_stats_reset")

    for metadata, metadata_path in selected:
        outcomes = {}
        for name in policy_names:
            outcomes[name] = _run_game(
                metadata,
                metadata_path,
                "exploration"
                if name in ("exploration_level_reset", "exploration_action_stats_reset")
                else name,
                seed=args.seed,
                policy_seed=args.policy_seed,
                max_actions=args.max_actions,
                retry_game_over=args.retry_game_over,
                reset_policy_each_level=name == "exploration_level_reset",
                reset_action_ucb_stats_each_level=name == "exploration_action_stats_reset",
                exploration_coefficient=args.exploration_coefficient,
                coordinate_color_exploration_coefficient=(
                    args.coordinate_color_exploration_coefficient
                ),
                avoid_same_board_noop_action=args.avoid_same_board_noop_action,
                visible_change_coefficient=args.visible_change_coefficient,
                level_progress_reward=args.level_progress_reward,
                prioritize_coordinate_action_first=args.prioritize_coordinate_action_first,
                exempt_intermediate_frame_noop_penalty=(
                    args.exempt_intermediate_frame_noop_penalty
                ),
                prioritize_center_distance_action6=args.prioritize_center_distance_action6,
                reset_coordinate_color_stats_each_level=(
                    args.reset_coordinate_color_stats_each_level
                ),
                prefer_connected_action6=args.prefer_connected_action6,
                defer_middle_frequency_action6_color=(args.defer_middle_frequency_action6_color),
                penalize_game_over_action=args.penalize_game_over_action,
                hash_seed_from_initial_observation=args.hash_seed_from_initial_observation,
            )
        same_start = (
            outcomes["random"]["initial_board"] == outcomes["exploration"]["initial_board"]
            and outcomes["random"]["initial_available_actions"]
            == outcomes["exploration"]["initial_available_actions"]
        )
        same_action_ucb_reset_start = None
        if "exploration_action_stats_reset" in outcomes:
            baseline_start = outcomes["exploration"]
            reset_start = outcomes["exploration_action_stats_reset"]
            same_action_ucb_reset_start = (
                baseline_start["initial_state"] == reset_start["initial_state"]
                and baseline_start["initial_levels_completed"]
                == reset_start["initial_levels_completed"]
                and baseline_start["initial_available_actions"]
                == reset_start["initial_available_actions"]
                and baseline_start["initial_board"] == reset_start["initial_board"]
            )
        game_result = {
            "game_id": metadata["game_id"],
            "same_public_start": same_start,
            "same_action_ucb_reset_start": same_action_ucb_reset_start,
            **outcomes,
            "hold_candidate": {
                "actions": 0,
                "levels_completed": outcomes["random"]["initial_levels_completed"],
                "state": outcomes["random"]["initial_state"],
            },
        }
        output_games.append(game_result)
    for game in output_games:
        for name in policy_names:
            game[name].pop("initial_board", None)
    report = {
        "evaluation": "public_local_environment_action_response",
        "stage": args.stage,
        "split_seed": args.split_seed,
        "action_seed": args.seed,
        "environment_seed": args.seed,
        "policy_seed": _policy_seed(args.seed, args.policy_seed),
        "max_actions_per_policy": args.max_actions,
        "retry_game_over": args.retry_game_over,
        "level_transfer_ablation": args.ablate_level_transfer,
        "exploration_coefficient": args.exploration_coefficient,
        "coordinate_color_exploration_coefficient": (args.coordinate_color_exploration_coefficient),
        "avoid_same_board_noop_action": args.avoid_same_board_noop_action,
        "visible_change_coefficient": args.visible_change_coefficient,
        "level_progress_reward": args.level_progress_reward,
        "prioritize_coordinate_action_first": args.prioritize_coordinate_action_first,
        "exempt_intermediate_frame_noop_penalty": (args.exempt_intermediate_frame_noop_penalty),
        "prioritize_center_distance_action6": args.prioritize_center_distance_action6,
        "reset_coordinate_color_stats_each_level": args.reset_coordinate_color_stats_each_level,
        "reset_action_ucb_stats_each_level": args.reset_action_ucb_stats_each_level,
        "prefer_connected_action6": args.prefer_connected_action6,
        "defer_middle_frequency_action6_color": (args.defer_middle_frequency_action6_color),
        "penalize_game_over_action": args.penalize_game_over_action,
        "hash_seed_from_initial_observation": args.hash_seed_from_initial_observation,
        "development_game_ids": [m["game_id"] for m, _ in dev],
        "holdout_game_ids": [m["game_id"] for m, _ in holdout],
        "selected_game_ids": [game["game_id"] for game in output_games],
        "aggregate": {
            name: {
                "games": len(output_games),
                "actions": sum(game[name]["actions"] for game in output_games),
                "gameplay_actions": sum(game[name]["gameplay_actions"] for game in output_games),
                "reset_actions": sum(game[name]["reset_actions"] for game in output_games),
                "attempts": sum(game[name]["attempts"] for game in output_games),
                "game_over_events": sum(game[name]["game_over_events"] for game in output_games),
                "levels_completed": sum(game[name]["levels_completed"] for game in output_games),
                "wins": sum(game[name]["final_state"] == "WIN" for game in output_games),
                "game_over": sum(game[name]["final_state"] == "GAME_OVER" for game in output_games),
                "no_op_actions": sum(game[name]["no_op_actions"] for game in output_games),
                "visible_unique_boards": sum(
                    game[name]["visible_unique_boards"] for game in output_games
                ),
                "same_visible_board_action_repeats": sum(
                    game[name]["same_visible_board_action_repeats"] for game in output_games
                ),
                "consecutive_exact_action_repeats": sum(
                    game[name]["consecutive_exact_action_repeats"] for game in output_games
                ),
                "duplicate_observation_steps": sum(
                    game[name]["duplicate_observation_steps"] for game in output_games
                ),
                "illegal_action_attempts": sum(
                    game[name]["illegal_action_attempts"] for game in output_games
                ),
                "policy_holds": sum(
                    game[name]["stop_reason"] == "exploration_hold" for game in output_games
                )
                if name.startswith("exploration")
                else None,
            }
            for name in policy_names
        },
        "games": output_games,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "stage": args.stage,
                "games": len(output_games),
                "same_public_starts": sum(g["same_public_start"] for g in output_games),
                "output": str(args.output),
                "summary": [
                    {
                        "game_id": g["game_id"],
                        "random_levels": g["random"]["levels_completed"],
                        "exploration_levels": g["exploration"]["levels_completed"],
                        "random_win": g["random"]["final_state"] == "WIN",
                        "exploration_win": g["exploration"]["final_state"] == "WIN",
                        "random_actions": g["random"]["actions"],
                        "exploration_actions": g["exploration"]["actions"],
                        "exploration_no_ops": g["exploration"]["no_op_actions"],
                        "same_board_action_repeats": {
                            "random": g["random"]["same_visible_board_action_repeats"],
                            "exploration": g["exploration"]["same_visible_board_action_repeats"],
                        },
                    }
                    for g in output_games
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
