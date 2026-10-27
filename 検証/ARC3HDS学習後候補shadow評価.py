"""同じ公開観測に対し、空HDSとAction応答学習後HDSの候補差を測る。"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "HDS/学習系統/v0.4.2"))

from hds学習系統 import HDS学習系統
from 接続.共通観測経路 import 公開観測から候補を照会する
from 検証 import ARC3探索Actionローカル評価 as 評価器
from 検証.ARC3HDS公開遷移shadow評価 import _入力

DEFAULT_OUTPUT = ROOT / "出力/ARC3-RUN-003-local/C2-036-HDS-action-candidate-shadow.json"
_ACTIVE_AUDIT: "_環境監査 | None" = None


def _候補signatureを読む(結果: dict[str, Any], 利用可能作用: set[int]) -> set[tuple[int, str]]:
    """候補の正確な同一性はメモリ内比較だけに使い、呼出元はsignatureを保存しない。"""
    if 結果.get("実行許可") is not False:
        raise RuntimeError("共通候補経路が実行許可をFalseに保っていない")
    群 = 結果.get("次作用候補群", [])
    if not isinstance(群, list):
        raise RuntimeError("次作用候補群の形式が不正")
    signatures: set[tuple[int, str]] = set()
    for 項目 in 群:
        if not isinstance(項目, dict) or 項目.get("実行許可") is not False:
            raise RuntimeError("候補単位の実行許可がFalseではない")
        候補 = 項目.get("候補")
        if not isinstance(候補, dict) or 候補.get("実行許可") is not False:
            raise RuntimeError("正規化Action候補の実行許可がFalseではない")
        作用番号 = 候補.get("作用番号")
        if type(作用番号) is not int or 作用番号 not in 利用可能作用:
            raise RuntimeError("Action候補が現観測のlegal Actionに含まれない")
        引数 = 候補.get("引数", {})
        if not isinstance(引数, dict):
            raise RuntimeError("Action候補引数の形式が不正")
        # 座標を含むsignatureはarm間比較後に破棄し、出力へ書かない。
        引数鍵 = json.dumps(引数, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        signatures.add((作用番号, 引数鍵))
    return signatures


def _anonymous_summary(signatures: set[tuple[int, str]]) -> dict[str, Any]:
    counts = Counter(作用番号 for 作用番号, _ in signatures)
    return {
        "候補数": len(signatures),
        "Action番号別候補数": {str(key): counts[key] for key in sorted(counts)},
    }


def _input_is_id_free(入力: Any) -> bool:
    return (
        set(入力.内容) == {"条件", "結果"}
        and set(入力.内容["条件"]) == {"Action番号"}
        and set(入力.内容["結果"]) == {"可視変化あり", "level進行あり", "新規盤面あり"}
    )


class _環境監査:
    def __init__(self) -> None:
        self.learned = HDS学習系統()
        self.control = HDS学習系統()
        self.learning_calls = 0
        self.query_pairs = 0
        self.read_only_checks = 0
        self.state_version_changes = 0
        self.last_state_version = 0
        self.previous_candidates = 0
        self.current_candidates = 0
        self.added_candidates = 0
        self.removed_candidates = 0
        self.changed_observations = 0
        self.previous_action_counts: Counter[int] = Counter()
        self.current_action_counts: Counter[int] = Counter()
        self.permission_violations = 0
        self.illegal_candidate_count = 0

    @staticmethod
    def _query(hds: HDS学習系統, observation) -> tuple[set[tuple[int, str]], bool]:
        before = hds.エンジン.台帳.件数("観測台帳")
        result = 公開観測から候補を照会する(hds, observation)
        after = hds.エンジン.台帳.件数("観測台帳")
        signatures = _候補signatureを読む(result, set(observation.作用可能番号))
        return signatures, before == after

    def transition(self, action, observation, receipt: dict[str, Any]) -> None:
        global _ACTIVE_AUDIT
        summary = {
            "action_id": action.作用番号,
            "changed_cells": receipt["可視変化セル数"],
            "level_delta": receipt["完了レベル増分"],
            "new_visible_board": receipt["盤面新規性"],
        }
        hds_input = _入力(summary, 結果を含む=True)
        if not _input_is_id_free(hds_input):
            raise RuntimeError("Action応答のHDS入力にID-free以外のfieldがある")
        learned_result = self.learned.処理する(hds_input)
        self.learning_calls += 1
        current_version = learned_result.内容.get("現在状態版", self.last_state_version)
        self.state_version_changes += int(current_version != self.last_state_version)
        self.last_state_version = current_version

        control_signatures, control_stable = self._query(self.control, observation)
        learned_signatures, learned_stable = self._query(self.learned, observation)
        self.query_pairs += 1
        self.read_only_checks += int(control_stable) + int(learned_stable)
        self.previous_candidates += len(control_signatures)
        self.current_candidates += len(learned_signatures)
        self.added_candidates += len(learned_signatures - control_signatures)
        self.removed_candidates += len(control_signatures - learned_signatures)
        self.changed_observations += int(learned_signatures != control_signatures)
        self.previous_action_counts.update(number for number, _ in control_signatures)
        self.current_action_counts.update(number for number, _ in learned_signatures)
        self.permission_violations += int(not control_stable) + int(not learned_stable)

    def summary(self) -> dict[str, Any]:
        previous = {
            "候補数": self.previous_candidates,
            "Action番号別候補数": {
                str(key): self.previous_action_counts[key]
                for key in sorted(self.previous_action_counts)
            },
        }
        current = {
            "候補数": self.current_candidates,
            "Action番号別候補数": {
                str(key): self.current_action_counts[key]
                for key in sorted(self.current_action_counts)
            },
        }
        return {"empty_control": previous, "learned_HDS": current}


class _HDSshadow探索方針(評価器.観測駆動探索方針):
    def 応答を記録する(self, 作用前, action, 作用後):
        receipt = super().応答を記録する(作用前, action, 作用後)
        if _ACTIVE_AUDIT is None:
            raise RuntimeError("HDS shadow監査コンテキストが未設定")
        if action.作用番号 == 0:
            raise RuntimeError("RESETが探索Action応答hookへ入った")
        _ACTIVE_AUDIT.transition(action, 作用後, receipt)
        return receipt


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _public_input_hash(root: Path) -> tuple[int, str]:
    hashes = sorted(_sha256(path) for path in root.rglob("*") if path.is_file())
    return len(hashes), hashlib.sha256("\n".join(hashes).encode("ascii")).hexdigest()


def _source_hashes() -> dict[str, str]:
    paths = {
        "evaluator": Path(__file__),
        "local_policy_evaluator": ROOT / "検証/ARC3探索Actionローカル評価.py",
        "policy": ROOT / "接続/観測駆動探索Action.py",
        "candidate_router": ROOT / "接続/共通観測経路.py",
        "boundary": ROOT / "接続/ARC3境界.py",
        "hds_learning_evaluator": ROOT / "検証/ARC3HDS公開遷移shadow評価.py",
        "hds_core": ROOT / "HDS/学習系統/v0.4.2/hds学習系統/系統.py",
    }
    return {name: _sha256(path) for name, path in paths.items()}


def run(output: Path, environment_dir: Path) -> dict[str, Any]:
    global _ACTIVE_AUDIT
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite diagnostic output: {output}")
    games = 評価器._load_games(environment_dir)
    split = list(games)
    random.Random(20261022).shuffle(split)
    development = split[:5]
    if len(development) != 5:
        raise RuntimeError("fixed development split does not contain five environments")

    policy_type_before = 評価器.観測駆動探索方針
    評価器.観測駆動探索方針 = _HDSshadow探索方針
    audits: list[_環境監査] = []
    local_actions = 0
    local_gameplay_actions = 0
    local_resets = 0
    local_levels = 0
    local_wins = 0
    local_illegal = 0
    local_no_ops = 0
    local_failed_starts = 0
    started = time.perf_counter()
    try:
        for metadata, metadata_path in development:
            audit = _環境監査()
            _ACTIVE_AUDIT = audit
            result = 評価器._run_game(
                metadata,
                metadata_path,
                "exploration",
                seed=31,
                policy_seed=31,
                max_actions=80,
                retry_game_over=True,
            )
            audits.append(audit)
            local_actions += result["actions"]
            local_gameplay_actions += result["gameplay_actions"]
            local_resets += result["reset_actions"]
            local_levels += result["levels_completed"]
            local_wins += int(result["final_state"] == "WIN")
            local_illegal += result["illegal_action_attempts"]
            local_no_ops += result["no_op_actions"]
            local_failed_starts += int(result["initial_state"] != "NOT_FINISHED")
            if audit.learning_calls != result["gameplay_actions"]:
                raise RuntimeError("RESET以外Action数とHDS処理呼出数が一致しない")
            if audit.query_pairs != audit.learning_calls:
                raise RuntimeError("同一次観測へのcandidate query数が学習Action数と一致しない")
            if audit.read_only_checks != audit.query_pairs * 2:
                raise RuntimeError("候補照会がHDS観測台帳を変更した")
            if len(result["action_responses"]) != result["actions"]:
                raise RuntimeError("local evaluation response数がAction数と一致しない")
            for response in result["action_responses"]:
                if response["action_id"] != 0 and response.get("policy_response") is None:
                    raise RuntimeError("live policyが応答を記録していない")
                if response["action_id"] == 0 and "policy_response" in response:
                    raise RuntimeError("RESETに探索policy応答が誤帰属した")
    finally:
        _ACTIVE_AUDIT = None
        評価器.観測駆動探索方針 = policy_type_before

    input_count, input_hash = _public_input_hash(environment_dir)
    queries = sum(a.query_pairs for a in audits)
    previous_candidates = sum(a.previous_candidates for a in audits)
    current_candidates = sum(a.current_candidates for a in audits)
    previous_action_counts: Counter[str] = Counter()
    current_action_counts: Counter[str] = Counter()
    for audit in audits:
        previous_action_counts.update({str(k): v for k, v in audit.previous_action_counts.items()})
        current_action_counts.update({str(k): v for k, v in audit.current_action_counts.items()})
    result = {
        "評価": "公開Action応答後のHDS学習有無によるAction候補shadow比較",
        "範囲": "公開dev split 5環境、固定split/environment/policy seed 20261022/31/31、最大80 Action、live policy生成。HDS候補はpolicyへ未接続。",
        "公開入力": {"ファイル数": input_count, "content_set_SHA256": input_hash},
        "source_SHA256": _source_hashes(),
        "条件": {
            "development_games": 5,
            "environment_seed": 31,
            "policy_seed": 31,
            "max_actions": 80,
            "retry_game_over": True,
            "trajectory_replay": False,
            "HDS_input_fields": [
                "条件.Action番号",
                "結果.可視変化あり",
                "結果.level進行あり",
                "結果.新規盤面あり",
            ],
        },
        "公開探索Action結果": {
            "Action要求": local_actions,
            "non_RESET_Action": local_gameplay_actions,
            "RESET": local_resets,
            "完了level合計": local_levels,
            "WIN": local_wins,
            "illegal_Action": local_illegal,
            "no_op": local_no_ops,
            "NOT_FINISHED以外の開始": local_failed_starts,
        },
        "HDS_shadow": {
            "learned処理呼出数": sum(a.learning_calls for a in audits),
            "empty_control処理呼出数": 0,
            "学習呼出後に状態版が変化した回数": sum(a.state_version_changes for a in audits),
            "同一観測paired_query数": queries,
            "query後の観測台帳安定確認数": sum(a.read_only_checks for a in audits),
            "previous_empty_control": {
                "候補数": previous_candidates,
                "Action番号別候補数": {
                    k: previous_action_counts[k] for k in sorted(previous_action_counts)
                },
            },
            "current_learned_HDS": {
                "候補数": current_candidates,
                "Action番号別候補数": {
                    k: current_action_counts[k] for k in sorted(current_action_counts)
                },
            },
            "delta_candidates": current_candidates - previous_candidates,
            "learned_only_candidate_count": sum(a.added_candidates for a in audits),
            "control_only_candidate_count": sum(a.removed_candidates for a in audits),
            "paired_observations_with_changed_candidate_set": sum(
                a.changed_observations for a in audits
            ),
            "candidate_permission_or_legality_violations": sum(
                a.permission_violations + a.illegal_candidate_count for a in audits
            ),
        },
        "経過秒": round(time.perf_counter() - started, 3),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8")
    output.write_bytes(raw)
    return {
        "output": str(output),
        "output_sha256": hashlib.sha256(raw).hexdigest(),
        "summary": result,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--environment-dir", type=Path, default=ROOT / "入力/Kaggle/environment_files"
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.environment_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
