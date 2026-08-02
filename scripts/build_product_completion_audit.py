#!/usr/bin/env python3
"""Build or verify the fail-closed ARC3 product completion audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Final

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPOSITORY_ROOT / "ARC-AGI-3-Agents"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from arc3_agi_agent.product_completion_audit import (  # noqa: E402
    evaluate_product_completion_evidence,
)

OUTPUT_PATH: Final = Path(
    "analysis/product/rev4/product_completion_audit.json"
)
CV_PATH: Final = Path("analysis/autonomous_completion/cv_manifest.json")
INPUT_PATHS: Final[dict[str, Path]] = {
    "known_sample_report": Path(
        "analysis/product/rev4/m4_full_sample_product.json"
    ),
    "clean_install_report": Path(
        "analysis/product/rev4/m5_clean_install_product.json"
    ),
    "release_report": Path("analysis/product/rev4/m5_product_release.json"),
    "product_descriptor": Path(
        "ARC-AGI-3-Agents/arc3_agi_agent/bundles/"
        "arc3_product_initial_state_v1.json"
    ),
    "active_policy_manifest": Path(
        "ARC-AGI-3-Agents/arc3_agi_agent/bundles/"
        "generic_autonomous_policy_v1.json"
    ),
    "teacher_policy_manifest": Path(
        "ARC-AGI-3-Agents/arc3_agi_agent/bundles/"
        "s5_rendered_policy_v1.json"
    ),
    "perturbation_report": Path(
        "analysis/runtime/S6_PERTURBATION_MEASUREMENT.json"
    ),
    "active_transformation_report": Path(
        "analysis/product/rev4/m3_active_product_transformation.json"
    ),
    "sealed_report": Path(
        "analysis/genericity/SEALED_CUSTOM_ENV_REPORT.json"
    ),
}


def _json_bytes(payload: bytes, *, source: str) -> dict[str, object]:
    value = json.loads(payload.decode("utf-8"))
    if not isinstance(value, dict):
        raise TypeError("PRODUCT_COMPLETION_AUDIT_OBJECT_REQUIRED:" + source)
    return value


def _read(root: Path, relative: Path) -> tuple[dict[str, object], str]:
    payload = (root / relative).read_bytes()
    return (
        _json_bytes(payload, source=relative.as_posix()),
        hashlib.sha256(payload).hexdigest(),
    )


def _git_json(
    root: Path,
    *,
    revision: str,
    relative: Path,
) -> tuple[dict[str, object], str, str]:
    resolved_revision = subprocess.run(
        ("git", "rev-parse", f"{revision}^{{commit}}"),
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    payload = subprocess.run(
        ("git", "show", f"{resolved_revision}:{relative.as_posix()}"),
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout
    return (
        _json_bytes(payload, source=f"{resolved_revision}:{relative}"),
        hashlib.sha256(payload).hexdigest(),
        resolved_revision,
    )


def build_audit(root: Path, *, cv_revision: str) -> dict[str, object]:
    values: dict[str, dict[str, object]] = {}
    bindings: dict[str, object] = {}
    for name, relative in INPUT_PATHS.items():
        value, sha256 = _read(root, relative)
        values[name] = value
        bindings[name] = {
            "path": relative.as_posix(),
            "sha256": sha256,
        }
    cv_manifest, cv_sha256, resolved_revision = _git_json(
        root,
        revision=cv_revision,
        relative=CV_PATH,
    )
    bindings["cv_manifest"] = {
        "path": CV_PATH.as_posix(),
        "sha256": cv_sha256,
        "git_revision": resolved_revision,
        "source": "COMMITTED_BLOB_NOT_WORKTREE",
    }
    return evaluate_product_completion_evidence(
        known_sample_report=values["known_sample_report"],
        clean_install_report=values["clean_install_report"],
        release_report=values["release_report"],
        product_descriptor=values["product_descriptor"],
        active_policy_manifest=values["active_policy_manifest"],
        teacher_policy_manifest=values["teacher_policy_manifest"],
        cv_manifest=cv_manifest,
        perturbation_report=values["perturbation_report"],
        active_transformation_report=values["active_transformation_report"],
        sealed_report=values["sealed_report"],
        evidence_bindings=bindings,
    )


def _encoded(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=REPOSITORY_ROOT)
    parser.add_argument("--cv-revision", default="HEAD")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    report = build_audit(root, cv_revision=str(arguments.cv_revision))
    expected = _encoded(report)
    path = root / OUTPUT_PATH
    if arguments.write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(expected)
        status = "WRITTEN"
        ok = True
    else:
        ok = path.is_file() and path.read_bytes() == expected
        status = "PASS" if ok else "STALE"
    print(
        json.dumps(
            {
                "blocking_requirement_count": len(
                    report["blocking_requirement_ids"]
                ),
                "completion_allowed": report["product_completion_allowed"],
                "output_path": OUTPUT_PATH.as_posix(),
                "status": status,
            },
            sort_keys=True,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
