"""C2-088: enable original v5 competition path over frozen online-learning-r3."""
from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "出力/ARC3-RUN-003-local/C2-087/online-learning-r3"
V5 = ROOT / "出力/ARC3-RUN-002-local/C2-029-source/v5-submission.ipynb"
V5_SHA = "5763f69d0794d7161dbe81a967edd2c10a6810c92ed1a28208bd47222fd5dfbc"
SOURCE = ROOT / "入力/モデル実行基底/v5/taaf-source-v1/patched"
SOURCE_MANIFEST = SOURCE.parent / "source-manifest.json"
SOURCE_MANIFEST_SHA = "2c9daf710a75154256e42dcf77a59cd4c580421a08d4bf434a913ef15bf66c12"
OUTPUT = ROOT / "出力/ARC3-RUN-003-local/C2-088/official-online"
KERNEL = "tecchannn/arc3-v6-online-official-c2-088"
GUARD = ('if TRUE_SUBMISSION:\n'
         '    raise RuntimeError("C2-078 is an offline pilot; competition rerun is not enabled.")\n')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def text(cell):
    return "".join(cell["source"])


def guarded(path, expected):
    raw = path.read_bytes()
    if sha(raw) != expected:
        raise ValueError("Frozen source hash drift: " + str(path))
    return raw


def cpu_cell(source, submission, records):
    """Packaging cell only: no model/framework/native instance or SDK games."""
    with tempfile.TemporaryDirectory(prefix="arc3-c2088-cell-") as name:
        root = Path(name).resolve()
        assert root.is_relative_to(Path(tempfile.gettempdir()).resolve())
        public = root / "public-source"
        for row in records:
            out = public / row["path"]
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(guarded(SOURCE / row["path"], row["sha256"]))
        expected = {p.relative_to(BASE / "preflight-source").as_posix(): sha(p.read_bytes())
                    for p in (BASE / "preflight-source").rglob("*") if p.is_file()}
        (root / "cell.py").write_text(source, encoding="utf8", newline="\n")
        smoke = f'''import hashlib,json,os,pathlib,sys,sysconfig,tempfile
root=pathlib.Path({str(root)!r})
site=root/'isolated-site';site.mkdir()
sysconfig.get_paths=lambda:{{'purelib':str(site)}}
old=tempfile.mkdtemp
def local_temp(*a,**k):
    k['dir']=root
    return old(*a,**k)
tempfile.mkdtemp=local_temp
context={{'TRUE_SUBMISSION':{submission!r},'BUNDLE_DIR':root/'public-source','os':os}}
exec(compile((root/'cell.py').read_text(encoding='utf8'),'C2-088-generated-cell','exec'),context)
expected={expected!r}
for path,digest in expected.items():
    assert hashlib.sha256((root/'public-source'/path).read_bytes()).hexdigest()==digest,path
pth=(site/'arc3_visual_hds_sources.pth').read_text(encoding='utf8')
assert pth.endswith(chr(10)) and pth.splitlines()==context['_arc3_hds_paths']
assert os.environ['ARC3_HDS_GAME_RESPONSE_UPDATES']=='enabled'
assert os.environ['ARC3_HDS_EVIDENCE_VISIBILITY']=='shown'
assert os.environ['LOCAL_ANALYZER_SEED']=='0'
assert 'hds学習系統' not in sys.modules and 'inference' not in sys.modules and 'torch' not in sys.modules
print(json.dumps({{'TRUE_SUBMISSION':{submission!r},'generated_cell_executed':True,'public_postimages_verified':len(expected),'GPU_framework_native_instance_or_game':False}}))
'''
        driver = root / "check.py"
        driver.write_text(smoke, encoding="utf8", newline="\n")
        env = {k: os.environ[k] for k in ("SYSTEMROOT", "PATH", "TEMP", "TMP") if k in os.environ}
        env.update(CUDA_VISIBLE_DEVICES="", HF_HUB_OFFLINE="1")
        done = subprocess.run([sys.executable, "-I", "-S", "-X", "utf8", str(driver)],
                              cwd=root, env=env, capture_output=True, text=True, encoding="utf8", timeout=40)
        if done.returncode:
            raise RuntimeError("Generated packaging cell CPU failure: " + done.stderr[-3000:])
        return json.loads(done.stdout.splitlines()[-1])


def configuration(notebook, submission):
    bm = SimpleNamespace(solver=SimpleNamespace())
    context = {"bm": bm, "target": SimpleNamespace(max_runtime_s=32400.0),
               "TRUE_SUBMISSION": submission, "USE_PRIORITY_SCHEDULING": True,
               "os": SimpleNamespace(environ={"ARC3_DEV_GAME_LIMIT": "3"}), "print": lambda *a: None}
    exec(compile(text(notebook["cells"][18]), "original-v5-config", "exec"), context)
    exec(compile(text(notebook["cells"][19]), "offline-only-pilot-config", "exec"), context)
    return {"TRUE_SUBMISSION": submission, "n_passes": bm.n_passes,
            "game_limit": None if submission else context["DEV_GAME_LIMIT"],
            "max_actions_per_game": bm.solver.max_actions_per_game,
            "max_runtime_s_per_game": bm.solver.max_runtime_s_per_game,
            "concurrency": bm.solver.concurrency, "analyzer_timeout": bm.solver.analyzer_timeout,
            "save_request_logs": bm.solver.save_request_logs}


def build():
    if OUTPUT.exists():
        raise FileExistsError("Refusing to overwrite C2-088")
    base = json.loads((BASE / "build-manifest.json").read_text(encoding="utf8"))
    nb = json.loads(guarded(BASE / "submission.ipynb", base["output_notebook_sha256"]))
    metadata = json.loads(guarded(BASE / "kernel-metadata.json", base["kernel_metadata_sha256"]))
    payload = guarded(BASE / "visual-hds-source.zip", base["bundle_sha256"])
    v5 = json.loads(guarded(V5, V5_SHA))
    if base["native_game_response_learning_mode"] != "enabled" or base["evidence_visibility"] != "shown":
        raise ValueError("C2-088 requires frozen SHOWN online-learning-r3")
    for new, old in ((5, 5), (18, 17), (23, 22)):
        if text(nb["cells"][new]) != text(v5["cells"][old]):
            raise ValueError("Original v5 detection/full configuration/competition Run drift")
    before = text(nb["cells"][6])
    if before.count(GUARD) != 1:
        raise ValueError("Expected unique offline-only refusal")
    after = before.replace(GUARD, "# C2-088: real competition rerun uses the original v5 full Run path.\n", 1)
    compile(after, "C2-088-packaging-cell", "exec")
    nb["cells"][6]["source"] = after.splitlines(keepends=True)
    metadata.update(id=KERNEL, title=KERNEL.split("/", 1)[1])
    if not (metadata["is_private"] and metadata["enable_gpu"] and not metadata["enable_internet"]):
        raise ValueError("Private GPU/no-internet metadata drift")
    source_manifest = json.loads(guarded(SOURCE_MANIFEST, SOURCE_MANIFEST_SHA))
    checks = [cpu_cell(after, truth, source_manifest["patched_source_manifest"]) for truth in (False, True)]
    configs = [configuration(nb, truth) for truth in (False, True)]
    assert configs[0]["game_limit"] == 3 and configs[0]["max_actions_per_game"] == 80
    assert configs[0]["max_runtime_s_per_game"] == 1200 and configs[0]["concurrency"] == 1
    assert configs[1]["game_limit"] is None and configs[1]["max_actions_per_game"] is None
    assert configs[1]["max_runtime_s_per_game"] == 532 * 60 and configs[1]["concurrency"] == 120
    # Compile all preserved source and all notebook code without executing it.
    from IPython.core.inputtransformer2 import TransformerManager
    transformer = TransformerManager()
    for i, cell in enumerate(nb["cells"]):
        if cell["cell_type"] == "code":
            compile(transformer.transform_cell(text(cell)), f"C2-088-cell-{i}", "exec",
                    flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
    python_files = [p for p in (BASE / "preflight-source").rglob("*.py")]
    for p in python_files:
        compile(p.read_bytes(), str(p), "exec")
    OUTPUT.mkdir(parents=True)
    (OUTPUT / "submission.ipynb").write_bytes((json.dumps(nb, ensure_ascii=False, indent=1) + "\n").encode())
    (OUTPUT / "kernel-metadata.json").write_bytes((json.dumps(metadata, ensure_ascii=False, indent=2) + "\n").encode())
    (OUTPUT / "visual-hds-source.zip").write_bytes(payload)
    shutil.copytree(BASE / "preflight-source", OUTPUT / "preflight-source")
    result = {**base, "schema": "arc3-native-online-official-build.v1", "case_id": "C2-088",
              "builder_source_sha256": sha(Path(__file__).read_bytes()),
              "base_build_manifest_sha256": sha((BASE / "build-manifest.json").read_bytes()),
              "base_notebook_sha256": base["output_notebook_sha256"],
              "output_notebook_sha256": sha((OUTPUT / "submission.ipynb").read_bytes()),
              "kernel_metadata_sha256": sha((OUTPUT / "kernel-metadata.json").read_bytes()),
              "competition_rerun_allowed": True, "pilot_scope": "normal private OFFLINE validation only",
              "original_v5_official_detection_config_run_exact": {"cell5": 5, "cell18": 17, "cell23": 22},
              "changed_notebook_cells_from_online_r3": [6], "changed_metadata_fields": ["id", "title"],
              "HDS_model_prior_observer_RPC_prompt_seed_stamp_runtime_zip_unchanged": True,
              "HDS_caps_are_not_game_action_caps": True, "official_notebook_budget_seconds": 32400,
              "offline_seed0_only_no_COMPETITION_seed_override": True,
              "normal_and_official_CPU_configurations": configs, "cpu_generated_cell_both_modes": checks,
              "source_python_files_compiled": len(python_files), "notebook_code_compiled": True,
              "actual_official_score_observed": False, "Kaggle_operation_performed": False}
    (OUTPUT / "build-manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf8", newline="\n")
    print(json.dumps({"output": str(OUTPUT), "kernel": KERNEL,
                      "notebook_sha256": result["output_notebook_sha256"],
                      "build_manifest_sha256": sha((OUTPUT / "build-manifest.json").read_bytes()),
                      "cpu_configurations": configs}, ensure_ascii=True))


if __name__ == "__main__":
    build()
