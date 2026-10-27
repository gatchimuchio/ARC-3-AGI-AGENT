"""初回公開観測に対するHDS語彙別保留原因を匿名集計する。"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import logging
from pathlib import Path
import random
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "HDS/学習系統/v0.4.2"))

from arc_agi import EnvironmentInfo, LocalEnvironmentWrapper  # noqa: E402
from hds学習系統 import HDS学習系統  # noqa: E402
from 接続.ARC3境界 import 観測する  # noqa: E402
from 接続.共通観測経路 import 公開観測から候補を照会する  # noqa: E402
from 検証.ARC3探索Actionローカル評価 import _load_games  # noqa: E402

DEFAULT_OUTPUT = ROOT / "出力/ARC3-RUN-002-local/C3-004-initial-hold-reasons.json"
_SPLIT_SEED = 20261022
_ENVIRONMENT_SEED = 31
_VOCABULARIES = ("列展開", "複合配色", "根付き順序鎖", "形状目標対応")
_SAFE_STATES = {
    "NOT_PLAYED",
    "NOT_FINISHED",
    "GAME_OVER",
    "WIN",
    "開始前観測",
    "停止観測",
    "完了観測",
    "不明状態観測",
    "未確認",
    "HDS保留",
    "適用語彙なし",
    "条件付き候補",
    "候補保留",
    "複数整合解を保持",
    "目標充足候補",
}
_SAFE_APPLICABILITY = {"適用可能", "構造上不適用", "未確認"}
_SAFE_REASON_STAGES = {
    "状態境界",
    "観測境界",
    "知覚または接続契約",
    "内容HDS",
    "作用HDS",
    "内容",
    "作用",
    "実行方針",
}
_REASON_KEYS = {
    "未確認語彙",
    "複数の構造解釈",
    "作用契約",
    "代替経路契約",
    "状態境界",
    "観測境界",
    "段階",
    "例外",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _public_content_hash(root: Path) -> tuple[int, str]:
    hashes = sorted(_sha256(path) for path in root.rglob("*") if path.is_file())
    return len(hashes), hashlib.sha256("\n".join(hashes).encode("ascii")).hexdigest()


def _state_label(value: Any) -> str:
    return value if isinstance(value, str) and value in _SAFE_STATES else "その他"


def _applicability_label(value: Any) -> str:
    return value if isinstance(value, str) and value in _SAFE_APPLICABILITY else "その他"


def _reason_categories(values: Any) -> Counter[str]:
    categories: Counter[str] = Counter()
    if not isinstance(values, (list, tuple)):
        return categories
    for value in values:
        if isinstance(value, str):
            categories["定型文字列理由"] += 1
        elif isinstance(value, dict):
            if "段階" in value:
                stage = value.get("段階")
                categories[
                    f"段階:{stage}"
                    if isinstance(stage, str) and stage in _SAFE_REASON_STAGES
                    else "段階:その他"
                ] += 1
            known = _REASON_KEYS.intersection(value)
            if known - {"段階", "例外"}:
                categories["構造化理由"] += 1
            if "例外" in value:
                categories["例外理由"] += 1
            if not known:
                categories["その他構造化理由"] += 1
        else:
            categories["その他理由形式"] += 1
    return categories


def _empty_vocabulary_summary() -> dict[str, Any]:
    return {
        "照会件数": 0,
        "適用性状態": Counter(),
        "作用適用性状態": Counter(),
        "目標候補数合計": 0,
        "作用候補数合計": 0,
        "保留理由カテゴリ": Counter(),
        "規則不確実性カテゴリ": Counter(),
        "未採用理由カテゴリ": Counter(),
        "局所保留件数": 0,
        "規則不確実性件数": 0,
        "未採用理由件数": 0,
        "実行許可申告件数": 0,
    }


def _summarize_vocabulary(result: dict[str, Any]) -> dict[str, Any]:
    applicability = result.get("適用性", {})
    if not isinstance(applicability, dict):
        applicability = {}
    action_applicability = result.get("作用適用性", applicability)
    if not isinstance(action_applicability, dict):
        action_applicability = {}
    hold_reasons = result.get("保留理由群", [])
    hold_reasons = hold_reasons if isinstance(hold_reasons, list) else []
    hold_reason_categories = _reason_categories(hold_reasons)
    uncertainty = result.get("規則不確実性", [])
    uncertainty = uncertainty if isinstance(uncertainty, list) else []
    unadopted = result.get("未採用理由群", [])
    unadopted = unadopted if isinstance(unadopted, list) else []
    local_holds = result.get("局所保留群", [])
    goals = result.get("目標候補群", [])
    actions = result.get("作用候補群", [])
    return {
        "適用性状態": _applicability_label(applicability.get("状態")),
        "作用適用性状態": _applicability_label(action_applicability.get("状態")),
        "目標候補数": len(goals) if isinstance(goals, list) else 0,
        "作用候補数": len(actions) if isinstance(actions, list) else 0,
        "保留理由カテゴリ": hold_reason_categories,
        "規則不確実性カテゴリ": _reason_categories(uncertainty),
        "未採用理由カテゴリ": _reason_categories(unadopted),
        "局所保留件数": len(local_holds) if isinstance(local_holds, list) else 0,
        "規則不確実性件数": len(uncertainty),
        "未採用理由件数": len(unadopted),
        "実行許可申告": result.get("実行許可") is True,
    }


def _accumulate_vocabulary(target: dict[str, Any], summary: dict[str, Any]) -> None:
    target["照会件数"] += 1
    target["適用性状態"][summary["適用性状態"]] += 1
    target["作用適用性状態"][summary["作用適用性状態"]] += 1
    target["目標候補数合計"] += summary["目標候補数"]
    target["作用候補数合計"] += summary["作用候補数"]
    target["保留理由カテゴリ"].update(summary["保留理由カテゴリ"])
    target["規則不確実性カテゴリ"].update(summary["規則不確実性カテゴリ"])
    target["未採用理由カテゴリ"].update(summary["未採用理由カテゴリ"])
    target["局所保留件数"] += summary["局所保留件数"]
    target["規則不確実性件数"] += summary["規則不確実性件数"]
    target["未採用理由件数"] += summary["未採用理由件数"]
    target["実行許可申告件数"] += int(summary["実行許可申告"])


class _AuditedHDS(HDS学習系統):
    def __init__(self) -> None:
        super().__init__()
        self.learning_calls = 0

    def 処理する(self, 入力):
        self.learning_calls += 1
        return super().処理する(入力)


def _source_hashes() -> dict[str, str]:
    source_paths = {
        "evaluation": Path(__file__),
        "agent": ROOT / "接続/ARC3提出agent.py",
        "common_observation": ROOT / "接続/共通観測経路.py",
        "boundary": ROOT / "接続/ARC3境界.py",
        "column_vocabulary": ROOT / "接続/列図式規則.py",
        "composite_vocabulary": ROOT / "接続/図式許容集合.py",
        "additional_vocabulary": ROOT / "接続/追加語彙接続.py",
        "hds_core": ROOT / "HDS/学習系統/v0.4.2/hds学習系統/系統.py",
    }
    return {name: _sha256(path) for name, path in source_paths.items()}


def run_audit(output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite diagnostic output: {output}")
    games = _load_games(ROOT / "入力/Kaggle/environment_files")
    split = list(games)
    random.Random(_SPLIT_SEED).shuffle(split)
    development = split[:5]
    if len(development) != 5:
        raise RuntimeError("fixed development split does not contain five environments")

    observation_status_counts: Counter[str] = Counter()
    candidate_status_counts: Counter[str] = Counter()
    candidate_hold_reason_categories: Counter[str] = Counter()
    candidate_uncertainty_count = 0
    candidate_unadopted_count = 0
    candidate_next_action_count = 0
    summaries = {vocabulary: _empty_vocabulary_summary() for vocabulary in _VOCABULARIES}
    action_requests = 0
    learning_calls = 0
    read_only_ledger_stable = 0
    executable_candidate_declarations = 0
    initial_observations = 0
    started = time.perf_counter()

    for metadata, metadata_path in development:
        info = EnvironmentInfo(
            game_id=metadata["game_id"],
            class_name=metadata.get("class_name"),
            local_dir=str(metadata_path.parent),
        )
        environment = LocalEnvironmentWrapper(
            info,
            logging.getLogger("arc3-hds-initial-hold-audit"),
            "hds-initial-hold-audit",
            seed=_ENVIRONMENT_SEED,
        )
        observation = 観測する(environment.observation_space, 観測通番=0)
        observation_status_counts[_state_label(observation.状態)] += 1
        if observation.状態 != "NOT_FINISHED":
            continue

        initial_observations += 1
        hds = _AuditedHDS()
        before_ledger = hds.エンジン.台帳.件数("観測台帳")
        candidate = 公開観測から候補を照会する(hds, observation)
        after_ledger = hds.エンジン.台帳.件数("観測台帳")
        read_only_ledger_stable += int(before_ledger == after_ledger)
        learning_calls += hds.learning_calls
        executable_candidate_declarations += int(candidate.get("実行許可") is True)
        candidate_status_counts[_state_label(candidate.get("状態"))] += 1
        candidate_hold_reason_categories.update(_reason_categories(candidate.get("保留理由群", [])))
        candidate_uncertainties = candidate.get("規則不確実性", [])
        candidate_uncertainty_count += (
            len(candidate_uncertainties) if isinstance(candidate_uncertainties, list) else 0
        )
        candidate_unadopted = candidate.get("未採用理由群", [])
        candidate_unadopted_count += (
            len(candidate_unadopted) if isinstance(candidate_unadopted, list) else 0
        )
        next_actions = candidate.get("次作用候補群", [])
        candidate_next_action_count += len(next_actions) if isinstance(next_actions, list) else 0
        for vocabulary_record in candidate.get("語彙別結果", []):
            vocabulary = vocabulary_record.get("語彙")
            if vocabulary not in summaries:
                continue
            result = vocabulary_record.get("結果", {})
            if isinstance(result, dict):
                _accumulate_vocabulary(summaries[vocabulary], _summarize_vocabulary(result))

    input_count, input_hash = _public_content_hash(ROOT / "入力/Kaggle/environment_files")
    result = {
        "評価": "初回公開観測でのHDS語彙別保留理由分類",
        "範囲": "固定dev先頭5公開環境、environment seed 31、各1回照会",
        "splitSeed": _SPLIT_SEED,
        "環境seed": _ENVIRONMENT_SEED,
        "初期状態件数": dict(sorted(observation_status_counts.items())),
        "共通経路aggregate": {
            "候補状態件数": dict(sorted(candidate_status_counts.items())),
            "次作用候補数合計": candidate_next_action_count,
            "保留理由カテゴリ": dict(sorted(candidate_hold_reason_categories.items())),
            "規則不確実性件数": candidate_uncertainty_count,
            "未採用理由件数": candidate_unadopted_count,
        },
        "初回進行中観測件数": initial_observations,
        "語彙別aggregate": {
            vocabulary: {
                **{key: value for key, value in summary.items() if not isinstance(value, Counter)},
                "適用性状態": dict(sorted(summary["適用性状態"].items())),
                "作用適用性状態": dict(sorted(summary["作用適用性状態"].items())),
                "保留理由カテゴリ": dict(sorted(summary["保留理由カテゴリ"].items())),
                "規則不確実性カテゴリ": dict(sorted(summary["規則不確実性カテゴリ"].items())),
                "未採用理由カテゴリ": dict(sorted(summary["未採用理由カテゴリ"].items())),
            }
            for vocabulary, summary in summaries.items()
        },
        "安全境界": {
            "HDS学習呼出し": learning_calls,
            "action要求": action_requests,
            "readOnly照会後に観測台帳不変": read_only_ledger_stable,
            "候補の実行許可申告件数": executable_candidate_declarations,
            "語彙の実行許可申告件数": sum(
                summary["実行許可申告件数"] for summary in summaries.values()
            ),
        },
        "elapsedSeconds": round(time.perf_counter() - started, 6),
        "input": {
            "publicEnvironmentFileCount": input_count,
            "contentSetSha256": input_hash,
        },
        "source_sha256": _source_hashes(),
        "exclusion": [
            "game/level identifiers",
            "GUID and observation fingerprint",
            "raw board, color values and coordinates",
            "action arguments and trajectories",
            "hold reason text and candidate payload",
        ],
        "interpretation_boundary": (
            "initial public observations only; no action, learning, transfer, "
            "runtime or official-score claim"
        ),
    }
    if initial_observations != 5:
        raise RuntimeError("five initial NOT_FINISHED observations were not audited")
    if (
        learning_calls != 0
        or action_requests != 0
        or read_only_ledger_stable != 5
        or executable_candidate_declarations != 0
        or any(summary["実行許可申告件数"] for summary in summaries.values())
    ):
        raise RuntimeError("HDS query crossed the read-only or no-action boundary")
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    output.write_bytes(raw)
    result["output_sha256"] = hashlib.sha256(raw).hexdigest()
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(run_audit(args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
