"""私的な既存bundle上で実MyAgentの代表点候補を公開ゲームpaired評価する。"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import importlib.util
import io
import json
import logging
import math
import os
import random
import re
import subprocess
import sys
import tempfile
import time
import types
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "接続/図式観測.py"
HELPER = ROOT / "検証/ARC3成分代表探索候補.py"
SPLIT_SEED = 20261022
ENVIRONMENT_SEED = 0
POLICY_SEED = 31025


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"module load failed: {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _bundle(reference: Path) -> tuple[bytes, dict[str, str]]:
    builder = _module("arc3_reference_builder", reference / "道具/ARC3提出物構築.py")
    original, _ = builder._bundle()
    replacement = {"接続/図式観測.py": OVERLAY.read_bytes(), "検証/ARC3成分代表探索候補.py": HELPER.read_bytes()}
    with zipfile.ZipFile(io.BytesIO(original)) as archive:
        entries = {info.filename: archive.read(info) for info in archive.infolist()}
    if "接続/図式観測.py" not in entries:
        raise RuntimeError("reference bundle lacks component module")
    manifest = json.loads(entries.pop("ARC3-SOURCE-MANIFEST.json").decode("utf-8"))
    entries.update(replacement)
    records = manifest["含有"]
    for record in records:
        path = record["パス"]
        if path in replacement:
            record["bytes"] = len(entries[path])
            record["sha256"] = _sha(entries[path])
    if any(record["パス"] == "検証/ARC3成分代表探索候補.py" for record in records):
        raise RuntimeError("candidate helper unexpectedly exists in source manifest")
    records.append({"パス": "検証/ARC3成分代表探索候補.py", "bytes": len(replacement["検証/ARC3成分代表探索候補.py"]), "sha256": _sha(replacement["検証/ARC3成分代表探索候補.py"])})
    for record in records:
        data = entries[record["パス"]]
        if len(data) != record["bytes"] or _sha(data) != record["sha256"]:
            raise RuntimeError("bundle manifest mismatch")
    entries["ARC3-SOURCE-MANIFEST.json"] = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path, data in sorted(entries.items()):
            info = zipfile.ZipInfo(path, date_time=(2026, 10, 22, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    payload = buffer.getvalue()
    return payload, {"reference_bundle_sha256": _sha(original), "evaluation_bundle_sha256": _sha(payload), "component_overlay_sha256": _sha(replacement["接続/図式観測.py"]), "candidate_helper_sha256": _sha(replacement["検証/ARC3成分代表探索候補.py"])}


def _games(reference: Path, count: int) -> list[tuple[str, Path]]:
    root = reference / "入力/Kaggle/environment_files"
    entries = []
    for path in sorted(root.rglob("metadata.json")):
        metadata = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(metadata.get("game_id"), str):
            entries.append((metadata["game_id"], path))
    if len(entries) != 25 or len({game for game, _ in entries}) != 25:
        raise RuntimeError("expected 25 distinct public environments")
    entries.sort()
    random.Random(SPLIT_SEED).shuffle(entries)
    return entries[:count]


def _input_manifest(reference: Path) -> dict[str, Any]:
    paths = []
    for directory in (reference / "入力/Kaggle/environment_files", reference / "入力/Kaggle/ARC-AGI-3-Agents/agents"):
        paths.extend(path for path in directory.rglob("*") if path.is_file() and (path.suffix == ".py" or path.name == "metadata.json"))
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda p: p.relative_to(reference).as_posix()):
        name = path.relative_to(reference).as_posix().encode("utf-8")
        digest.update(len(name).to_bytes(4, "big"))
        digest.update(name)
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return {"sha256": digest.hexdigest(), "file_count": len(paths)}


class _StepCounter:
    def __init__(self, env: Any) -> None:
        self._env = env
        self.steps = 0

    def __getattr__(self, name: str) -> Any:
        return getattr(self._env, name)

    def step(self, *args: Any, **kwargs: Any) -> Any:
        self.steps += 1
        return self._env.step(*args, **kwargs)


class _WarningCounter(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.count = 0

    def emit(self, record: logging.LogRecord) -> None:
        self.count += 1


def _child(arm: str, reference: Path, bundle: Path, result_path: Path, count: int) -> None:
    from arc_agi import Arcade, OperationMode

    logging.disable(logging.NOTSET)
    logging.getLogger().handlers.clear()
    logging.getLogger().addHandler(logging.NullHandler())
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="arc3-v3-paired-private-") as folder:
        source = Path(folder) / "source"
        source.mkdir()
        with zipfile.ZipFile(bundle) as archive:
            archive.extractall(source)
        sys.path[:0] = [str(source), str(source / "HDS/学習系統/v0.4.2"), str(reference / "検証")]
        starter_package = types.ModuleType("agents")
        starter_package.__path__ = [str(reference / "入力/Kaggle/ARC-AGI-3-Agents/agents")]
        sys.modules["agents"] = starter_package
        starter = importlib.import_module("agents.agent")
        agent_module = _module("arc3_paired_agent", source / "接続/ARC3提出agent.py")
        if not issubclass(agent_module.MyAgent, starter.Agent):
            raise RuntimeError("bundle agent does not use official Starter")
        warnings = _WarningCounter()
        agent_module._LOG.addHandler(warnings)
        agent_module._LOG.setLevel(logging.WARNING)
        agent_module._LOG.propagate = False
        helper = _module("arc3_paired_component_helper", source / "検証/ARC3成分代表探索候補.py")
        observe = importlib.import_module("接続.ARC3境界").観測する
        base_policy = agent_module.観測駆動探索方針

        class _Candidate(base_policy):
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                super().__init__(*args, **kwargs)
                self.representative_choices = 0
                self.coordinate_replacements = 0
                self.fallbacks = 0
                self.representative_seconds = 0.0

            def _未試行座標を選ぶ(self, 盤面: Any, 色: int, 未試行座標: Any) -> tuple[int, int]:
                baseline = super()._未試行座標を選ぶ(盤面, 色, 未試行座標)
                tick = time.perf_counter()
                point, reason = helper.代表座標(盤面, 色, 未試行座標, baseline)
                self.representative_seconds += time.perf_counter() - tick
                self.representative_choices += int(reason == "代表点")
                self.coordinate_replacements += int(point != baseline)
                self.fallbacks += int(reason != "代表点")
                return point

        def fixed_policy(*args: Any, **kwargs: Any) -> Any:
            kwargs["乱数種"] = POLICY_SEED
            return (base_policy if arm == "previous" else _Candidate)(*args, **kwargs)

        agent_module.観測駆動探索方針 = fixed_policy
        original_memory = agent_module.事前記憶をHDSへ供給する

        def fixed_memory(hds: Any) -> dict[str, Any]:
            report = dict(original_memory(hds))
            report["visible_change_coefficient"] = 0.0
            return report

        agent_module.事前記憶をHDSへ供給する = fixed_memory
        arcade = Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=str(reference / "入力/Kaggle/environment_files"), recordings_dir=str(Path(folder) / "recordings"))
        rows = []
        for ordinal, (game_id, metadata_path) in enumerate(_games(reference, count), 1):
            tick = time.perf_counter()
            warning_start = warnings.count
            try:
                card_id = arcade.create_scorecard()
                raw_env = arcade.make(game_id, seed=ENVIRONMENT_SEED, scorecard_id=card_id, save_recording=False, include_frame_data=True)
                if raw_env is None:
                    raise RuntimeError("offline environment unavailable")
                env = _StepCounter(raw_env)
                initial = observe(env.observation_space, 観測通番=0)
                start = {"state": initial.状態, "levels": initial.完了レベル数, "legal": initial.作用可能番号, "board": initial.最新盤面}
                start_hash = _sha(json.dumps(start, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
                agent = agent_module.MyAgent(card_id="local-evaluation", game_id=game_id, agent_name="MyAgent", ROOT_URL="http://offline", record=False, arc_env=env)
                trace: list[list[Any]] = []
                noops = 0
                dispatches = 0
                game_over_events = 0
                first_action_seconds = None
                original_dispatch = agent.do_action_request

                def traced_dispatch(action: Any) -> Any:
                    nonlocal noops, dispatches, game_over_events, first_action_seconds
                    if first_action_seconds is None:
                        first_action_seconds = time.perf_counter() - tick
                    before = observe(env.observation_space, 観測通番=dispatches)
                    trace.append([action.作用番号, dict(action.引数)])
                    dispatches += 1
                    response = original_dispatch(action)
                    after = observe(env.observation_space, 観測通番=dispatches)
                    delta = after.完了レベル数 - before.完了レベル数
                    game_over_events += int(after.状態 == "GAME_OVER")
                    if action.作用番号 != 0 and before.最新盤面 == after.最新盤面 and delta == 0:
                        noops += 1
                    return response

                agent.do_action_request = traced_dispatch
                agent.main()
                final = env.observation_space
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                human_baseline = metadata.get("baseline_actions")
                if not isinstance(human_baseline, list) or not human_baseline or not all(type(value) is int and value > 0 for value in human_baseline):
                    raise RuntimeError("public scorecard baseline unavailable")
                env_info = next((info for info in arcade.available_environments if info.game_id == game_id), None)
                if env_info is None or env_info.baseline_actions != human_baseline:
                    raise RuntimeError("SDK metadata baseline mismatch")
                scorecard = arcade.close_scorecard(card_id)
                if scorecard is None:
                    raise RuntimeError("SDK scorecard unavailable")
                environment_score = scorecard.find_environment(game_id)
                if environment_score is None or environment_score.id != game_id or not environment_score.runs:
                    raise RuntimeError("SDK environment score unavailable")
                if any(run.message or not math.isfinite(run.score) for run in environment_score.runs):
                    raise RuntimeError("SDK scorecard has invalid or diagnostic runs")
                score = environment_score.score
                if not math.isfinite(score) or not math.isclose(score, max(run.score for run in environment_score.runs)):
                    raise RuntimeError("SDK scorecard best play mismatch")
                levels = environment_score.levels_completed
                runtime = agent.hds_runtime_stats
                rows.append({"case": ordinal, "initial_sha256": start_hash, "score": score, "levels": levels, "available_levels": getattr(final, "win_levels", None), "win": environment_score.completed, "final_state": getattr(final.state, "name", str(final.state)), "sdk_play_count": len(environment_score.runs), "sdk_actions": environment_score.actions, "sdk_runs": [{"actions": run.actions, "levels": run.levels_completed, "score": run.score, "resets": run.resets} for run in environment_score.runs], "actions": len(trace), "dispatches": dispatches, "steps": env.steps, "noops": noops, "game_over_events": game_over_events, "agent_warning_events": warnings.count - warning_start, "authorization": bool(runtime.get("事前記憶Action認可", True)), "representative_choices": getattr(agent._policy, "representative_choices", 0), "coordinate_replacements": getattr(agent._policy, "coordinate_replacements", 0), "fallbacks": getattr(agent._policy, "fallbacks", 0), "representative_seconds": getattr(agent._policy, "representative_seconds", 0.0), "first_action_seconds": first_action_seconds, "trace": trace, "elapsed_seconds": time.perf_counter() - tick})
            except Exception as exc:
                rows.append({"case": ordinal, "error": type(exc).__name__, "elapsed_seconds": time.perf_counter() - tick})
            print(f"PROGRESS {arm} {ordinal}/{count}", flush=True)
        result_path.write_text(json.dumps({"arm": arm, "rows": rows, "elapsed_seconds": time.perf_counter() - started}, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--games", type=int, default=5, choices=range(1, 26))
    parser.add_argument("--concurrent-reference", action="store_true")
    parser.add_argument("--child", choices=("previous", "candidate"))
    parser.add_argument("--bundle", type=Path)
    args = parser.parse_args()
    if args.child:
        if args.bundle is None:
            parser.error("child requires bundle")
        _child(args.child, args.reference_root, args.bundle, args.output, args.games)
        return
    if args.output.exists():
        raise SystemExit("既存の結果を上書きしません")
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("PYTHONHASHSEED=0 が必要です")
    reference_commit = subprocess.run(["git", "-C", str(args.reference_root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    main_base_commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    reference_dirty = bool(subprocess.run(["git", "-C", str(args.reference_root), "status", "--porcelain", "--untracked-files=no"], capture_output=True, text=True, check=True).stdout.strip())
    candidate_dirty = bool(subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "--", "検証/ARC3実Agent成分代表paired.py", "検証/ARC3成分代表探索候補.py"], capture_output=True, text=True, check=True).stdout.strip())
    runner_sha256 = _sha(Path(__file__).read_bytes())
    input_manifest = _input_manifest(args.reference_root)
    selected_set_sha256 = _sha(json.dumps([game for game, _ in _games(args.reference_root, args.games)], ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    payload, hashes = _bundle(args.reference_root)
    with tempfile.TemporaryDirectory(prefix="arc3-v3-paired-private-") as folder:
        root = Path(folder)
        bundle = root / "bundle.zip"
        bundle.write_bytes(payload)
        results = []
        for arm in ("previous", "candidate"):
            result_path = root / f"{arm}.json"
            cmd = [sys.executable, str(Path(__file__).resolve()), "--child", arm, "--reference-root", str(args.reference_root), "--bundle", str(bundle), "--output", str(result_path), "--games", str(args.games)]
            error_type = "unknown"
            with subprocess.Popen(cmd, cwd=args.reference_root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1) as proc:
                assert proc.stdout is not None
                for line in proc.stdout:
                    if line.startswith("PROGRESS "):
                        print(line.rstrip(), flush=True)
                    match = re.match(r"^([A-Za-z][A-Za-z0-9_]*(?:Error|Exception)):", line)
                    if match:
                        error_type = match.group(1)
                code = proc.wait()
            if code != 0 or not result_path.exists():
                raise RuntimeError(f"{arm} child failed: exit {code}, type {error_type}")
            results.append(json.loads(result_path.read_text(encoding="utf-8")))
        previous, candidate = results
        pairs = []
        for a, b in zip(previous["rows"], candidate["rows"], strict=True):
            if a["case"] != b["case"]:
                raise RuntimeError("paired case order mismatch")
            if "error" in a or "error" in b:
                pairs.append({"case": a["case"], "previous_error": a.get("error"), "candidate_error": b.get("error")})
                continue
            first = next((i for i, (x, y) in enumerate(zip(a["trace"], b["trace"])) if x != y), None)
            if first is None and len(a["trace"]) != len(b["trace"]):
                first = min(len(a["trace"]), len(b["trace"]))
            for row in (a, b):
                row["trace_sha256"] = _sha(json.dumps(row.pop("trace"), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
            pairs.append({"case": a["case"], "matched_start": a["initial_sha256"] == b["initial_sha256"], "first_trace_divergence": first, "previous": a, "candidate": b, "score_delta": b["score"] - a["score"], "level_delta": b["levels"] - a["levels"]})
        if (_input_manifest(args.reference_root) != input_manifest or subprocess.run(["git", "-C", str(args.reference_root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip() != reference_commit or subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip() != main_base_commit or _sha(Path(__file__).read_bytes()) != runner_sha256 or _sha(HELPER.read_bytes()) != hashes["candidate_helper_sha256"] or _sha(OVERLAY.read_bytes()) != hashes["component_overlay_sha256"]):
            raise RuntimeError("reference input or commit changed during evaluation")
        valid = [pair for pair in pairs if "score_delta" in pair]
        summary = {"valid_pairs": len(valid), "error_pairs": len(pairs) - len(valid), "matched_starts": sum(pair["matched_start"] for pair in valid), "score_delta_mean": sum(pair["score_delta"] for pair in valid) / len(valid) if valid else None, "level_delta_total": sum(pair["level_delta"] for pair in valid), "win_delta_total": sum(int(pair["candidate"]["win"]) - int(pair["previous"]["win"]) for pair in valid), "positive_negative_tied": [sum(pair["score_delta"] > 0 for pair in valid), sum(pair["score_delta"] < 0 for pair in valid), sum(pair["score_delta"] == 0 for pair in valid)], "step_dispatch_mismatches": sum(pair[arm]["steps"] != pair[arm]["dispatches"] for pair in valid for arm in ("previous", "candidate")), "agent_warning_events": sum(pair[arm]["agent_warning_events"] for pair in valid for arm in ("previous", "candidate")), "authorization_true": sum(pair[arm]["authorization"] for pair in valid for arm in ("previous", "candidate")), "trace_divergent_pairs": sum(pair["first_trace_divergence"] is not None for pair in valid), "noops_previous": sum(pair["previous"]["noops"] for pair in valid), "noops_candidate": sum(pair["candidate"]["noops"] for pair in valid)}
        result = {"experiment": "v3_component_representative_sdk_scorecard", "reference_commit": reference_commit, "reference_tracked_worktree_dirty": reference_dirty, "main_base_commit": main_base_commit, "candidate_files_uncommitted": candidate_dirty, "runner_sha256": runner_sha256, "bundle": hashes, "input_manifest": input_manifest, "selected_games_sha256": selected_set_sha256, "python": sys.version.split()[0], "arc_agi": importlib.metadata.version("arc-agi"), "arcengine": importlib.metadata.version("arcengine"), "split_seed": SPLIT_SEED, "environment_seed": ENVIRONMENT_SEED, "policy_seed": POLICY_SEED, "episodes_per_arm": args.games, "concurrent_reference_run": args.concurrent_reference, "summary": summary, "pairs": pairs, "limitations": "Public games reused in prior development; this is not untouched holdout or a Kaggle score. No-op uses the last public frame; warning capture covers the agent logger. Concurrent load prevents reliable timing comparison."}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps({"output": str(args.output), "sha256": _sha(args.output.read_bytes())}, ensure_ascii=False))


if __name__ == "__main__":
    main()
