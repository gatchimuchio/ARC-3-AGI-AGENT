from __future__ import annotations

import ast
import hashlib
import importlib.util
import io
import json
import socket
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile


ROOT = Path(__file__).resolve().parents[1]
BUILDER_PATH = ROOT / "道具" / "ARC3提出物構築.py"
SPEC = importlib.util.spec_from_file_location("arc3_submission_builder_test", BUILDER_PATH)
assert SPEC and SPEC.loader
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


class ARC3SubmissionBuilderTests(unittest.TestCase):
    def test_bundle_is_deterministic_and_contains_only_runtime_imports(self):
        payload, manifest = BUILDER._bundle()
        repeated, repeated_manifest = BUILDER._bundle()
        self.assertEqual(payload, repeated)
        self.assertEqual(manifest, repeated_manifest)
        self.assertGreaterEqual(len(manifest["含有"]), 25)
        self.assertLess(len(manifest["含有"]), 99)
        paths = [item["パス"] for item in manifest["含有"]]
        self.assertEqual(paths, sorted(paths))
        self.assertIn("接続/ARC3提出agent.py", paths)
        self.assertTrue(all(path.startswith(("接続/", "HDS/学習系統/v0.4.2/hds学習系統/")) for path in paths))
        self.assertFalse(any("__pycache__" in path or path.endswith(".pyc") for path in paths))
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            self.assertIsNone(archive.testzip())
            self.assertNotIn("入力/", "\n".join(archive.namelist()))
            self.assertNotIn("記憶/", "\n".join(archive.namelist()))

    def test_notebook_metadata_and_code_cells_are_valid(self):
        payload, _ = BUILDER._bundle()
        notebook = BUILDER._notebook("tecchannn", payload)
        metadata = notebook["metadata"]["kaggle"]
        self.assertEqual(notebook["nbformat"], 4)
        self.assertFalse(metadata["isGpuEnabled"])
        self.assertFalse(metadata["isInternetEnabled"])
        kernel_metadata = BUILDER._kernel_metadata("tecchannn")
        self.assertTrue(kernel_metadata["is_private"])
        self.assertFalse(kernel_metadata["enable_gpu"])
        self.assertFalse(kernel_metadata["enable_internet"])
        self.assertEqual(kernel_metadata["competition_sources"], [BUILDER.COMPETITION])
        self.assertNotIn("keywords", kernel_metadata)

        cells = notebook["cells"]
        self.assertIn("PurePosixPath", "".join(cells[2]["source"]))
        self.assertIn("/tmp/arc3-hds-source", "".join(cells[2]["source"]))
        self.assertNotIn("/kaggle/working/arc3-hds-source", "".join(cells[2]["source"]))
        run_source = "".join(cells[4]["source"])
        self.assertIn("/tmp/arc3-hds-source:/tmp/arc3-hds-source/HDS/学習系統/v0.4.2", run_source)
        self.assertNotIn("/kaggle/working/arc3-hds-source", run_source)
        self.assertIn("RECORDINGS_DIR=/tmp/server_recording", run_source)
        self.assertNotIn("RECORDINGS_DIR=/kaggle/working/", run_source)
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            embedded_agent = "".join(cells[3]["source"]).partition("\n")[2]
            bundled_agent = archive.read("接続/ARC3提出agent.py").decode("utf-8")
            self.assertEqual(embedded_agent, bundled_agent)
        for cell in cells:
            if cell["cell_type"] != "code":
                continue
            source = "".join(cell["source"])
            if source.startswith("!"):
                continue
            if source.startswith("%%writefile"):
                source = source.partition("\n")[2]
            ast.parse(source)

    def test_built_notebook_runs_embedded_import_checks_and_writes_parquet(self):
        payload, manifest = BUILDER._bundle()
        notebook = BUILDER._notebook("tecchannn", payload)
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            extraction = temp / "arc3-hds-source"
            extraction_cell = "".join(notebook["cells"][2]["source"])
            extraction_cell = extraction_cell.replace(
                "/tmp/arc3-hds-source", extraction.as_posix()
            )
            original_path = list(sys.path)
            try:
                exec(compile(extraction_cell, "notebook-extract-cell", "exec"), {})
                self.assertTrue((extraction / "ARC3-SOURCE-MANIFEST.json").is_file())
                self.assertEqual(len(json.loads((extraction / "ARC3-SOURCE-MANIFEST.json").read_text(encoding="utf-8"))["含有"]), len(manifest["含有"]))

                run_cell = "".join(notebook["cells"][4]["source"])
                parquet = temp / "submission.parquet"
                run_cell = run_cell.replace("/kaggle/working/submission.parquet", parquet.as_posix())
                exec(compile(run_cell, "notebook-save-run-cell", "exec"), {})
                import pandas as pd

                result = pd.read_parquet(parquet)
                self.assertEqual(list(result.columns), ["row_id", "game_id", "end_of_game", "score"])
                self.assertEqual(len(result), 1)
            finally:
                sys.path[:] = original_path
                for name in list(sys.modules):
                    if name == "接続" or name.startswith("接続.") or name == "hds学習系統" or name.startswith("hds学習系統."):
                        del sys.modules[name]

    def test_packaged_agent_holds_in_official_offline_runner_without_network(self):
        from arc_agi import Arcade, OperationMode

        payload, _ = BUILDER._bundle()
        starter_agents = ROOT / "入力" / "Kaggle" / "ARC-AGI-3-Agents" / "agents"
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            package_root = temp / "source"
            package_root.mkdir()
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                archive.extractall(package_root)
            original_path = list(sys.path)
            source_prefixes = ("接続", "hds学習系統")
            try:
                sys.path[:0] = [
                    str(package_root),
                    str(package_root / "HDS" / "学習系統" / "v0.4.2"),
                ]
                package = types.ModuleType("agents")
                package.__path__ = [str(starter_agents)]
                with patch.dict(sys.modules, {"agents": package}):
                    base = importlib.import_module("agents.agent")
                    agent_path = package_root / "接続" / "ARC3提出agent.py"
                    spec = importlib.util.spec_from_file_location("packed_arc3_agent", agent_path)
                    assert spec and spec.loader
                    agent_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(agent_module)

                    arcade = Arcade(
                        operation_mode=OperationMode.OFFLINE,
                        environments_dir=str(ROOT / "入力" / "Kaggle" / "environment_files"),
                        recordings_dir=str(temp / "recordings"),
                    )
                    environment = arcade.make("ar25")
                    self.assertIsNotNone(environment)
                    self.assertEqual(environment.observation_space.state.name, "NOT_FINISHED")
                    agent = agent_module.MyAgent(
                        card_id="local-test",
                        game_id="ar25",
                        agent_name="MyAgent",
                        ROOT_URL="http://offline",
                        record=False,
                        arc_env=environment,
                    )
                    self.assertTrue(issubclass(agent_module.MyAgent, base.Agent))
                    with patch.object(socket.socket, "connect", side_effect=AssertionError("network disabled")), patch(
                        "socket.create_connection", side_effect=AssertionError("network disabled")
                    ):
                        agent.main()
                    self.assertEqual(agent.action_counter, 0)
                    self.assertEqual(agent.last_hold["状態"], "HOLD")
                    self.assertEqual(agent.last_hold["次作用候補数"], 0)
                    self.assertFalse(agent.last_hold["候補側申告実行許可"])
            finally:
                sys.path[:] = original_path
                for name in list(sys.modules):
                    if name == "agents" or name.startswith("agents."):
                        del sys.modules[name]
                    elif any(name == prefix or name.startswith(prefix + ".") for prefix in source_prefixes):
                        del sys.modules[name]

    def test_build_records_hashes_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "bundle"
            result = BUILDER.build(output, "tecchannn")
            notebook = output / "submission.ipynb"
            metadata = output / "kernel-metadata.json"
            manifest = output / "bundle-manifest.json"
            record = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(result["kernel_id"], "tecchannn/arc3-hds-hold-baseline")
            self.assertEqual(record["notebook_sha256"], hashlib.sha256(notebook.read_bytes()).hexdigest())
            self.assertEqual(json.loads(metadata.read_text(encoding="utf-8"))["id"], result["kernel_id"])
            with self.assertRaises(FileExistsError):
                BUILDER.build(output, "tecchannn")


if __name__ == "__main__":
    unittest.main()
