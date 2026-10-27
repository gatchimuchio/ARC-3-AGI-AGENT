"""凍結R3のTEMPコピーへnative照会候補patchを適用し、CPU契約だけを検査する。"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "出力/ARC3-RUN-003-local/C2-078/shadow-r3/visual-hds-source.zip"
BUNDLE_SHA = "ed0c13e329c948e774424ebc738eaf2a8c3bb83c0bcdbcf71945a0ac3c5f3766"
PROBE = ROOT / "運用/証拠/ARC26-UNIFIED/C2-078_synthetic-learning-probe.json"
PROBE_SHA = "b11ca86bb4cb8229accf20ba5b95863cf10d50911dcfabc3cd269dff0b3654a3"
PATCH = Path(__file__).with_suffix(".patch")
NATIVE = Path("HDS/学習系統/v0.4.2/hds学習系統")
PREIMAGES = {
    "系統.py": "f57e34fcab9249ad7fef72d7b9088fbb440c01afcd4313c9447b7a31427bd4a5",
    "実行系.py": "11d253705181873bcc22e312a0d0a2198fe16a82e3d7289ea8746fdc14695429",
}

# The subprocess imports only the extracted native package and frozen prior loader.
# All safety fixtures below are synthetic. No game/environment/model is imported.
CPU_CONTRACT = r"""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import sys

root, mode, fixture_path = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "HDS/学習系統/v0.4.2"))
from hds学習系統 import HDS学習系統
from hds学習系統 import 実行系
from hds学習系統.型 import 外部入力
from 接続.ARC3事前記憶 import 事前記憶をHDSへ供給する

実行系.現在時刻 = lambda: "2000-01-01T00:00:00+00:00"
fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
boundary = "ARC3視覚公開作用応答候補"
outcome_path = ("公開応答区分",)
scope = (outcome_path,)
hds = HDS学習系統()
事前記憶をHDSへ供給する(hds)
for row in fixture["training"]:
    content = deepcopy(row["input_features"])
    content["公開応答区分"] = row["expected_outcome"]
    hds.処理する(外部入力(content, boundary))
assert hds.エンジン.台帳.件数("観測台帳") == 17

def learned_state(system):
    engine = system.エンジン
    return deepcopy((engine.台帳.全取得(), engine.状態.履歴(), engine._原理履歴))

def query(system, value, selected=None, explicit=False):
    state = learned_state(system)
    identifiers = system.エンジン.識別子.状態を書き出す()
    frozen_input = deepcopy(value)
    if explicit:
        result = system.照会する(value, 結果経路群=selected)
    else:
        result = system.照会する(value)
    assert state == learned_state(system)
    assert value == frozen_input
    after = system.エンジン.識別子.状態を書き出す()
    expected = dict(identifiers)
    for kind in ("照会", "学習判定"):
        expected[kind] = expected.get(kind, 0) + 1
    assert after == expected
    return asdict(result)

def supported(result, paths):
    content = result["内容"]
    return (result["状態"] == "出力"
            and set(paths) <= {tuple(p["結果経路"]) for p in content["予測群"]}
            and not any(content[k] for k in
                        ("競合群", "追加観測要求群", "係争中原理群", "識別不能群")))

cases = []
def inspect(name, system, value, paths, expected_supported=False, hold_field=None):
    whole = query(deepcopy(system), value)
    row = {"name": name, "whole": whole}
    if mode == "candidate":
        explicit_none = query(deepcopy(system), value, None, True)
        assert whole == explicit_none
        scoped = query(deepcopy(system), value, paths, True)
        assert scoped["追跡情報"]["照会結果経路群"] == paths
        assert all(tuple(p["結果経路"]) in paths for p in scoped["内容"]["予測群"])
        assert supported(scoped, paths) is expected_supported
        if not expected_supported:
            assert scoped["状態"] == "断定保留"
        if hold_field:
            assert scoped["内容"][hold_field]
        row["scoped"] = scoped
    cases.append(row)

for row in fixture["queries"]:
    value = 外部入力(deepcopy(row["input_features"]), boundary)
    inspect(f"frozen_probe_action_{row['action_number']}", hds, value, scope, True)
    assert cases[-1]["whole"]["状態"] == row["native_output"]["状態"] == "断定保留"
    if mode == "candidate":
        expected = row["bridge_result"]["predictions"][0]["value"]
        assert {p["予測値"] for p in cases[-1]["scoped"]["内容"]["予測群"]} == {expected}

value = 外部入力(deepcopy(fixture["queries"][0]["input_features"]), boundary)
inspect("no_observations", HDS学習系統(), value, scope, hold_field="追加観測要求群")
inspect("unlearned_boundary", hds, 外部入力(value.内容, "別の合成境界"), scope,
        hold_field="追加観測要求群")
inspect("one_requested_target_has_no_rule", hds, value, (outcome_path, ("未学習結果",)),
        hold_field="追加観測要求群")
known_result = deepcopy(value.内容)
known_result["公開応答区分"] = "盤面変化"
inspect("already_observed_label_is_not_a_forecast", hds, 外部入力(known_result, boundary),
        scope, hold_field="追加観測要求群")

# Target isolation is caused by an actual contradictory synthetic update.
isolated = deepcopy(hds)
counterexample = deepcopy(value.内容)
counterexample["公開応答区分"] = "可視変化なし"
isolated.処理する(外部入力(counterexample, boundary))
inspect("relevant_target_isolation", isolated, value, scope, hold_field="係争中原理群")

# Two naturally learned relations are observationally indistinguishable.
# Contradictory test conditions also give an actual native target conflict.
ambiguous = HDS学習系統()
for repeat in range(3):
    for number, label in ((0, "A"), (1, "B")):
        ambiguous.処理する(外部入力({"条件A": number, "条件B": number, "結果": label}, "合成"))
generic_scope = (("結果",),)
inspect("relevant_target_identifiability", ambiguous,
        外部入力({"条件A": 0, "条件B": 0}, "合成"), generic_scope,
        hold_field="識別不能群")
inspect("relevant_target_conflict", ambiguous,
        外部入力({"条件A": 0, "条件B": 1}, "合成"), generic_scope, hold_field="競合群")
inspect("missing_condition", ambiguous, 外部入力({"条件A": 0}, "合成"), generic_scope,
        hold_field="追加観測要求群")
inspect("unseen_condition_values", ambiguous,
        外部入力({"条件A": 99, "条件B": 99}, "合成"), generic_scope,
        hold_field="追加観測要求群")

rejected = 0
if mode == "candidate":
    malformed = ((), "結果", [outcome_path], ((),), (("",),), (("x", 1),),
                 (outcome_path, outcome_path))
    for paths in malformed:
        system = deepcopy(hds)
        state = learned_state(system)
        ids = system.エンジン.識別子.状態を書き出す()
        try:
            system.照会する(value, 結果経路群=paths)
        except ValueError:
            rejected += 1
        else:
            raise AssertionError("malformed explicit scope accepted")
        assert state == learned_state(system)
        assert ids == system.エンジン.識別子.状態を書き出す()
print(json.dumps({"mode": mode, "cases": cases, "malformed_scopes_rejected": rejected,
                  "learned_memory_state_and_input_unchanged_by_queries": True,
                  "legacy_query_identifier_allocation_preserved": True}, ensure_ascii=False))
"""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def preflight() -> dict:
    if sha256(BUNDLE) != BUNDLE_SHA or sha256(PROBE) != PROBE_SHA:
        raise ValueError("frozen R3 bundle or native fixture drifted")
    canonical_before = {name: sha256(ROOT / NATIVE / name) for name in PREIMAGES}
    script_sha, patch_sha = sha256(Path(__file__)), sha256(PATCH)
    with tempfile.TemporaryDirectory(prefix="arc3-c2079-native-") as work:
        work = Path(work)
        original = work / "original"
        original.mkdir()
        with zipfile.ZipFile(BUNDLE) as archive:
            for name in archive.namelist():
                target = (original / name).resolve()
                if not target.is_relative_to(original.resolve()):
                    raise ValueError("unsafe frozen bundle member")
            archive.extractall(original)
        for name, expected in PREIMAGES.items():
            if sha256(original / NATIVE / name) != expected:
                raise ValueError(f"native preimage drift: {name}")
        candidate = work / "candidate"
        shutil.copytree(original, candidate)
        git = shutil.which("git")
        if git is None:
            raise RuntimeError("git apply is needed for candidate patch proof")
        command = [git, "-c", "core.autocrlf=false", "apply"]
        subprocess.run(
            command + ["--check", str(PATCH)],
            cwd=candidate,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            command + [str(PATCH)], cwd=candidate, check=True, capture_output=True, text=True
        )
        changed = [
            p.name
            for p in sorted((original / NATIVE).glob("*.py"))
            if p.read_bytes() != (candidate / NATIVE / p.name).read_bytes()
        ]
        if set(changed) != set(PREIMAGES):
            raise AssertionError("patch changed unexpected native files")
        hashes = [
            {
                "path": (NATIVE / name).as_posix(),
                "pre_sha256": PREIMAGES[name],
                "post_sha256": sha256(candidate / NATIVE / name),
            }
            for name in PREIMAGES
        ]
        compiled = 0
        for path in (candidate / NATIVE).glob("*.py"):
            compile(path.read_bytes(), str(path), "exec")
            compiled += 1
        runs = {}
        for mode, base in (("original", original), ("candidate", candidate)):
            result = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-S",
                    "-X",
                    "utf8",
                    "-c",
                    CPU_CONTRACT,
                    str(base),
                    mode,
                    str(PROBE),
                ],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=55,
            )
            runs[mode] = json.loads(result.stdout)
    old, new = runs["original"], runs["candidate"]
    assert [r["name"] for r in old["cases"]] == [r["name"] for r in new["cases"]]
    assert all(a["whole"] == b["whole"] for a, b in zip(old["cases"], new["cases"]))
    assert canonical_before == {name: sha256(ROOT / NATIVE / name) for name in PREIMAGES}
    return {
        "schema": "arc3-native-target-query-candidate-cpu.v1",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "frozen_R3_bundle_sha256": BUNDLE_SHA,
        "frozen_synthetic_native_probe_sha256": PROBE_SHA,
        "proof_runner_sha256": script_sha,
        "candidate_patch_sha256": patch_sha,
        "native_source_pre_post": hashes,
        "native_python_files_compiled_without_import": compiled,
        "patch_applied_only_to_temporary_copy": True,
        "canonical_native_sources_unchanged": True,
        "bridge_builder_R3_artifacts_modified": False,
        "whole_query_full_structure_matches_frozen_original": True,
        "explicit_None_equals_omitted_scope": True,
        "query_nonmutation_limit": "Learned ledgers, state versions, principles and input remain unchanged. Existing query/learning-check identifiers still advance once per query, exactly as before.",
        "candidate_contract": new,
        "original_whole_query_contract": old,
        "game_model_GPU_Kaggle_called": False,
        "ability_score_or_action_improvement_proven": False,
        "adoption_status": "ISOLATED_CPU_CANDIDATE_ONLY",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    if output.exists():
        parser.error(f"refusing to overwrite evidence: {output}")
    result = preflight()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "output": str(output),
                "sha256": sha256(output),
                "cases": len(result["candidate_contract"]["cases"]),
                "whole_query_exact_compatibility": True,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
