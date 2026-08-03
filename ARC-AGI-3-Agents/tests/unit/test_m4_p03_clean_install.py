from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
REPORT_PATH = (
    REPOSITORY_ROOT
    / "analysis"
    / "product"
    / "rev5_1"
    / "m4_p03_clean_install.json"
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def test_m4_p03_clean_install_evidence_is_sealed_and_complete() -> None:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    claimed = report.pop("logical_content_sha256")
    canonical = json.dumps(
        report,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    assert claimed == _sha256(canonical)
    assert report["status"] == "M4_P03_PASS"
    assert report["clean_environment"] == {
        **report["clean_environment"],
        "fresh_environment": True,
        "outside_development_tree": True,
        "system_site_packages_inherited": False,
        "pip_cache_disabled": True,
        "editable_install": False,
        "development_tree_import_count": 0,
        "outside_fresh_prefix_import_count": 0,
        "development_tree_sys_path_count": 0,
        "credential_binding_count": 0,
    }
    assert report["install_audit"]["wheel_install"] == "PASS"
    assert report["install_audit"]["dependency_pin_mismatch_count"] == 0
    assert report["install_audit"]["official_sample_game_directory_count"] == 25
    assert report["boot_audit"]["release_bundle_load"] == "PASS"
    assert report["boot_audit"]["C_J_M_P_self_check"] == "PASS"
    assert report["boot_audit"]["state_owner_violation_count"] == 0
    assert report["boot_audit"]["identity_boundary_finding_count"] == 0
    assert report["exit_audit"]["status"] == "M4_P03_PASS"
    assert report["claim_boundary"]["clean_full_sample_repeat_complete"] is False
    assert "install_root" not in json.dumps(report)
