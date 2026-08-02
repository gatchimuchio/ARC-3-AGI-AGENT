from __future__ import annotations

import base64
import csv
import hashlib
import importlib.util
import io
import sys
import zipfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPOSITORY_ROOT / "scripts" / "build_product_release.py"
SPEC = importlib.util.spec_from_file_location(
    "arc3_product_release_test_target",
    SCRIPT_PATH,
)
assert SPEC is not None and SPEC.loader is not None
sys.path.insert(0, str(SCRIPT_PATH.parent))
try:
    RELEASE = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(RELEASE)
finally:
    sys.path.remove(str(SCRIPT_PATH.parent))


def test_product_release_wheel_is_reproducible_and_self_auditing() -> None:
    first, first_report = RELEASE.build_release_wheel()
    second, second_report = RELEASE.build_release_wheel()

    assert first == second
    assert first_report == second_report
    assert first_report["product_id"] == "ARC3CompletionAgent"
    assert first_report["product_version"] == "1.0.0"
    assert first_report["byte_reproducible"] is True
    assert first_report["teacher_included"] is False
    assert first_report["fixed_action_trajectory_included"] is False
    assert first_report["runtime_identity_routing_included"] is False
    assert first_report["compiled_identity_free_product_policy_included"] is True

    with zipfile.ZipFile(io.BytesIO(first)) as archive:
        names = set(archive.namelist())
        assert "arc3_agi_agent/product_runner.py" in names
        assert "arc3_agi_agent/product_trace.py" in names
        assert (
            "arc3_agi_agent/bundles/arc3_product_initial_state_v1.zip"
            in names
        )
        assert "agents/templates/arc3_completion_agent.py" in names
        assert not any(
            marker in name.casefold()
            for name in names
            for marker in (
                "environment_files/",
                "analysis/",
                "/teacher/",
                "s5_rendered_policy",
            )
        )
        record_name = (
            "arc3_completion_agent-1.0.0.dist-info/RECORD"
        )
        rows = list(
            csv.reader(
                io.StringIO(archive.read(record_name).decode("utf-8"))
            )
        )
        recorded_names = {row[0] for row in rows}
        assert recorded_names == names
        for name, digest, size in rows:
            if name == record_name:
                assert digest == ""
                assert size == ""
                continue
            data = archive.read(name)
            assert digest.startswith("sha256=")
            assert int(size) == len(data)
            encoded = base64.urlsafe_b64encode(
                hashlib.sha256(data).digest()
            ).rstrip(b"=")
            assert digest == "sha256=" + encoded.decode("ascii")
