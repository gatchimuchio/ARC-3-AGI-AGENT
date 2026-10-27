"""固定R3のHDS対象予測を、公開SDKの無作為な実行済み一手で逐次照合する。"""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path, PurePosixPath
import random
import sys
import tempfile
import time
import traceback
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "出力/ARC3-RUN-003-local/C2-078/shadow-r3"
REFERENCE = ROOT / "出力/ARC3-RUN-002-local/C2-027-kaggle-output/v5/benchmark.json"
ENVIRONMENTS = ROOT / "入力/Kaggle/environment_files"
EXPECTED_BUNDLE = "ed0c13e329c948e774424ebc738eaf2a8c3bb83c0bcdbcf71945a0ac3c5f3766"
EXPECTED_RUNTIME = "2499e1d42c9176e8cd5c1096d0ebef9374a806ff067dae63d43ae5d5638a2701"
EXPECTED_BRIDGE = "1a1c48ad03a3c38668e8b8eba85ef61d8fb86a50143c80c221ba586c22d08617"
SEED = 2701
CALLS_PER_GAME = 80
MAJORITY_ORDER = ("可視変化なし", "盤面変化", "レベル進行", "GAME_OVER", "勝利")


class ContractError(ValueError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ContractError(code)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _input_manifest() -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in ENVIRONMENTS.rglob("*") if item.is_file()):
        relative = path.relative_to(ENVIRONMENTS).as_posix().encode("utf-8")
        data = path.read_bytes()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(hashlib.sha256(data).digest())
    return digest.hexdigest()


@contextmanager
def _frozen_api():
    manifest = json.loads((BUILD / "build-manifest.json").read_text(encoding="utf-8"))
    archive = BUILD / "visual-hds-source.zip"
    _require(_sha(archive) == manifest["bundle_sha256"] == EXPECTED_BUNDLE, "r3_bundle_hash")
    _require(manifest["runtime_adapter_sha256"] == EXPECTED_RUNTIME, "r3_runtime_hash")
    _require(manifest["bridge_sha256"] == EXPECTED_BRIDGE, "r3_bridge_hash")
    _require(
        _sha(BUILD / "submission.ipynb") == manifest["output_notebook_sha256"], "r3_notebook_hash"
    )
    notebook = json.loads((BUILD / "submission.ipynb").read_text(encoding="utf-8"))
    declarations = [
        line.strip()
        for cell in notebook["cells"]
        for line in "".join(cell.get("source", ())).splitlines()
        if line.strip().startswith("demo_excluded_games =")
    ]
    _require(
        declarations == ["demo_excluded_games = [] if TRUE_SUBMISSION else []"], "demo_exclusions"
    )
    with tempfile.TemporaryDirectory(prefix="arc3-r3-public-prequential-") as directory:
        destination = Path(directory).resolve()
        _require(
            destination.is_relative_to(Path(tempfile.gettempdir()).resolve()), "temporary_root"
        )
        with zipfile.ZipFile(archive) as zipped:
            for row in manifest["bundle_manifest"]["files"]:
                relative = PurePosixPath(row["path"])
                _require(
                    not relative.is_absolute() and ".." not in relative.parts, "bundle_member_path"
                )
                target = destination.joinpath(*relative.parts)
                _require(target.resolve().is_relative_to(destination), "bundle_member_escape")
                data = zipped.read(row["path"])
                _require(hashlib.sha256(data).hexdigest() == row["sha256"], "bundle_member_hash")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
        sys.path[:0] = [
            str(destination / "検証"),
            str(destination / "HDS/学習系統/v0.4.2"),
            str(destination),
            str(ROOT),
        ]
        spec = importlib.util.spec_from_file_location(
            "arc3_r3_frozen_prequential", destination / "arc3_visual_hds_runtime.py"
        )
        runtime = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runtime)
        api = runtime._api()
        _require(_sha(Path(api.__file__)) == EXPECTED_BRIDGE, "loaded_bridge_hash")
        _require(_sha(Path(runtime.__file__)) == EXPECTED_RUNTIME, "loaded_runtime_hash")
        yield runtime, api, manifest, destination


def _majority(previous: Counter[str]) -> tuple[str | None, bool]:
    if not previous:
        return None, False
    maximum = max(previous.values())
    tied = [value for value in MAJORITY_ORDER if previous[value] == maximum]
    return tied[0], len(tied) > 1


def _record_response(
    previous: Counter[str],
    forecast: set[str],
    blocked: str | None,
    outcome: str,
    counts: Counter[str],
) -> None:
    """多数派を現在ラベル追加前に固定し、両予測を同じcovered stepで照合する。"""
    majority, tie = _majority(previous)
    counts["nonreset_public_responses"] += 1
    counts["outcome:" + outcome] += 1
    if blocked is not None:
        counts["forecast_blocked:" + blocked] += 1
    elif len(forecast) == 1:
        counts["target_qualified_unique_forecasts"] += 1
        matched = outcome in forecast
        counts["target_unique_matches"] += int(matched)
        counts["forecasted_outcome:" + next(iter(forecast))] += 1
        if majority is None:
            counts["forecast_covered_without_previous_majority"] += 1
        else:
            counts["same_covered_steps_with_majority"] += 1
            counts["target_matches_on_majority_comparable_steps"] += int(matched)
            counts["majority_matches_on_same_covered_steps"] += int(majority == outcome)
            counts["majority_ties_on_same_covered_steps"] += int(tie)
    else:
        counts["target_qualified_multiple_values"] += 1
    previous[outcome] += 1


def _selection(arcade) -> tuple[list[str], dict]:
    available = [row.game_id for row in arcade.available_environments]
    _require(len(available) == 25 and len(set(available)) == 25, "expected_25_public_games")
    first_local = available[:3]
    selected = first_local
    provenance = {
        "method": "local SDK available_environments list order first three",
        "notebook_algorithm": "available_environments list order; empty demo exclusions; first three",
        "remote_current_pilot_order_verified": False,
    }
    if REFERENCE.is_file():
        reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
        identities = [row["game_id"] for row in reference["game_runs"][:3]]
        _require(len(identities) == 3 and len(set(identities)) == 3, "historical_selection_shape")
        if all(identity in available for identity in identities):
            selected = identities
            provenance["method"] = "historical public v5 benchmark first three game_runs"
            provenance["reference_path"] = REFERENCE.relative_to(ROOT).as_posix()
            provenance["reference_sha256"] = _sha(REFERENCE)
            provenance["matches_local_notebook_first_three"] = selected == first_local
        else:
            provenance["historical_reference_selection_available_locally"] = False
    return selected, provenance


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    if output.exists():
        parser.error(f"refusing to overwrite result: {output}")
    started = time.perf_counter()
    counts: Counter[str] = Counter()
    hds_totals: Counter[str] = Counter()
    prior_counts: Counter[str] = Counter()
    sdk_call_histogram: Counter[int] = Counter()
    errors = []
    selection = {}
    source = {}
    budget_flags: Counter[str] = Counter()
    versions = {name: importlib.metadata.version(name) for name in ("arc-agi", "arcengine")}
    try:
        _require(versions == {"arc-agi": "0.9.8", "arcengine": "0.9.3"}, "pinned_sdk_versions")
        with _frozen_api() as (runtime, api, manifest, temporary):
            from arc_agi import Arcade, OperationMode
            from arcengine import GameAction
            from 接続.ARC3境界 import 観測する

            def public_frame(raw, number):
                observed = 観測する(raw, 観測通番=number)
                return api.PublicFrame(
                    observed.最新盤面, observed.状態, observed.完了レベル数, observed.作用可能番号
                )

            source = {
                "bundle_sha256": EXPECTED_BUNDLE,
                "runtime_adapter_sha256": EXPECTED_RUNTIME,
                "bridge_sha256": EXPECTED_BRIDGE,
                "build_manifest_sha256": _sha(BUILD / "build-manifest.json"),
                "notebook_sha256": manifest["output_notebook_sha256"],
                "prior_loader_sha256": _sha(temporary / "接続/ARC3事前記憶.py"),
                "public_frame_validator_sha256": _sha(ROOT / "接続/ARC3境界.py"),
            }
            arcade = Arcade(
                operation_mode=OperationMode.OFFLINE,
                environments_dir=str(ENVIRONMENTS),
                recordings_dir=str(temporary / "disabled-recordings"),
            )
            selected, selection = _selection(arcade)
            for ordinal, identity in enumerate(selected, start=1):
                bridge = api.VisualHDSBridge(
                    update_budget=80, query_budget=80, hds_seconds_budget=120.0
                )
                previous: Counter[str] = Counter()
                rng = random.Random(SEED)
                game_calls = 0
                forecasts_before = counts["target_qualified_unique_forecasts"]
                try:
                    counts["games_started"] += 1
                    _require(bridge.prior_report["loaded_count"] == 5, "prior_load_five")
                    prior_counts[bridge.prior_report["load_status"]] += 1
                    env = arcade.make(
                        identity, seed=SEED, save_recording=False, include_frame_data=True
                    )
                    _require(env is not None, "offline_environment_missing")
                    while game_calls < CALLS_PER_GAME:
                        before = public_frame(env.observation_space, game_calls)
                        if before.state == "WIN":
                            counts["games_stopped_at_win"] += 1
                            break
                        reset = before.state in {"NOT_PLAYED", "GAME_OVER"}
                        query = None
                        if reset:
                            action = api.PublicAction(0)
                        else:
                            legal = sorted(
                                number for number in before.available_actions if 1 <= number <= 7
                            )
                            _require(bool(legal), "no_legal_public_nonreset_action")
                            number = rng.choice(legal)
                            action = (
                                api.PublicAction(
                                    6,
                                    x=rng.randrange(len(before.board[0])),
                                    y=rng.randrange(len(before.board)),
                                )
                                if number == 6
                                else api.PublicAction(number)
                            )
                            query = bridge.query(before, action)
                            _require(query["authorization"] is False, "query_authorization")
                            _require(query["continue_visual_solver"] is True, "query_solver_stop")
                            _require(
                                query["bridge_status"] in {"queried", "budget_exhausted"},
                                "query_contract_status",
                            )
                            counts["query_status:" + query["bridge_status"]] += 1
                            counts[
                                "native_query_status:" + str(query.get("native_status", "missing"))
                            ] += 1
                            for reason in query.get("native_hold_reasons", ()):
                                counts["native_hold_reason:" + reason] += 1
                            _require(
                                public_frame(env.observation_space, game_calls) == before,
                                "query_changed_public_state",
                            )
                        data = {"x": action.x, "y": action.y} if action.number == 6 else {}
                        game_calls += 1
                        counts["sdk_calls_attempted"] += 1
                        response = env.step(GameAction.from_id(action.number), data=data)
                        _require(response is not None, "missing_public_sdk_response")
                        counts["sdk_responses_received"] += 1
                        after = public_frame(response, game_calls)
                        if reset:
                            counts["reset_sdk_calls"] += 1
                            continue
                        outcome = api._observed_outcome(before, after)
                        blocked, forecast = runtime._target_forecast(query)
                        _require(
                            isinstance(forecast, set) and forecast <= api._OUTCOMES,
                            "qualification_contract",
                        )
                        _require(blocked is not None or bool(forecast), "empty_qualified_forecast")
                        _record_response(previous, forecast, blocked, outcome, counts)
                        if blocked is None and len(forecast) == 1:
                            counts["qualified_unique_native_status:" + query["native_status"]] += 1
                        counts["rendered_hint_steps"] += int(bool(api.render_hint(query)))
                        update = bridge.update(before, action, after)
                        _require(update["authorization"] is False, "update_authorization")
                        _require(update["continue_visual_solver"] is True, "update_solver_stop")
                        _require(
                            update["bridge_status"] in {"updated", "budget_exhausted"},
                            "update_contract_status",
                        )
                        counts["update_status:" + update["bridge_status"]] += 1
                    counts["games_completed_without_contract_error"] += 1
                    print(
                        f"PROGRESS completed_public_games={ordinal}/3 sdk_calls={game_calls}",
                        flush=True,
                    )
                finally:
                    sdk_call_histogram[game_calls] += 1
                    counts["games_with_unique_forecasts"] += int(
                        counts["target_qualified_unique_forecasts"] > forecasts_before
                    )
                    for key, value in bridge.stats.items():
                        if type(value) in {int, float} and (
                            key.endswith("attempted")
                            or key.endswith("succeeded")
                            or key.endswith("errors")
                            or key.endswith("seconds")
                            or key in {"budget_exhaustion_requests", "rejected_requests"}
                        ):
                            hds_totals[key] += value
                        elif key.endswith("exhausted") and type(value) is bool:
                            budget_flags[key] += int(value)
    except Exception as exc:
        errors.append(
            {
                "type": type(exc).__name__,
                "contract_code": str(exc)
                if isinstance(exc, ContractError)
                else "unexpected_exception",
                "trace_locations": [
                    {"file": Path(row.filename).name, "function": row.name, "line": row.lineno}
                    for row in traceback.extract_tb(exc.__traceback__)[-4:]
                ],
            }
        )
    covered = counts["target_qualified_unique_forecasts"]
    compared = counts["same_covered_steps_with_majority"]
    total = counts["nonreset_public_responses"]
    result = {
        "schema": "arc3-public-prequential-hds-diagnostic.v1",
        "run_id": output.stem,
        "observed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "environment_and_chooser_seed": SEED,
        "max_sdk_calls_per_game_including_resets": CALLS_PER_GAME,
        "fresh_hds_per_game": True,
        "hds_budgets_per_game": {"updates": 80, "queries": 80, "seconds": 120.0},
        "selection_provenance": selection,
        "chooser": "fresh uniform legal-action RNG per game; Action6 uniform visible-grid coordinates",
        "majority_baseline": "same game strictly previous non-reset public responses; current label added after comparison",
        "majority_tie_break_order": list(MAJORITY_ORDER),
        "counts": dict(sorted(counts.items())),
        "sdk_calls_per_game_histogram": dict(sorted(sdk_call_histogram.items())),
        "target_unique_forecast_coverage": covered / total if total else None,
        "target_unique_forecast_precision": counts["target_unique_matches"] / covered
        if covered
        else None,
        "same_covered_steps_comparison": {
            "steps": compared,
            "hds_precision": counts["target_matches_on_majority_comparable_steps"] / compared
            if compared
            else None,
            "previous_majority_precision": counts["majority_matches_on_same_covered_steps"]
            / compared
            if compared
            else None,
        },
        "hds_aggregate_stats": dict(sorted(hds_totals.items())),
        "games_with_exhausted_budget_flags": dict(sorted(budget_flags.items())),
        "prior_load_status_counts": dict(sorted(prior_counts.items())),
        "contract_errors": errors,
        "stopped_on_contract_error": bool(errors),
        "game_ids_raw_boards_coordinates_or_action_sequences_persisted": False,
        "only_public_sdk_frames_and_responses_used": True,
        "hds_predictions_influenced_action_choice": False,
        "model_score_or_causal_action_improvement_measured": False,
        "competition_api_gpu_or_model_called": False,
        "sdk_versions": versions,
        "source_sha256": {"diagnostic": _sha(Path(__file__)), **source},
        "public_environment_manifest_sha256": _input_manifest(),
        "elapsed_seconds": time.perf_counter() - started,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "counts",
                    "target_unique_forecast_coverage",
                    "target_unique_forecast_precision",
                    "same_covered_steps_comparison",
                    "contract_errors",
                )
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
