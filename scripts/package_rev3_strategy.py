#!/usr/bin/env python3
"""Build the deterministic, ASCII-safe rev3 strategy review package."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    REPOSITORY_ROOT
    / "artifacts"
    / "rev3"
    / "arc3_hds_distillation_first_strategy_rev3_corrected.zip"
)
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)

PACKAGE_INPUTS = {
    "arc3_authority_order_rev3.md": "AUTHORITY_ORDER.md",
    "arc3_codex_operating_contract_rev3.md": "AGENTS.md",
    "arc3_distillation_first_roadmap_rev3.md": (
        "docs/roadmap/ARC3_HDS蒸留先行_開発ロードマップ_rev3.md"
    ),
    "arc3_distillation_first_spec_rev3.md": (
        "docs/strategy/"
        "ARC3_HDS蒸留先行_汎用自律完遂主体_実装仕様書_rev3.md"
    ),
    "arc3_rev3_audit_resolution_2026-07-31.md": (
        "docs/audits/"
        "ARC3_HDS_DISTILLATION_FIRST_REV3_AUDIT_RESOLUTION_2026-07-31.md"
    ),
    "arc3_strategy_index_rev3.md": (
        "docs/strategy/ARC3_HDS蒸留先行_戦略改定_INDEX_rev3.md"
    ),
    "contracts/agi_build_ready_profile_v1.json": (
        "docs/strategy/contracts/AGI_BUILD_READY_PROFILE_V1.json"
    ),
    "contracts/claim_registry_rev3.json": (
        "docs/strategy/contracts/CLAIM_REGISTRY_REV3.json"
    ),
    "contracts/hds_structure_bundle_contract_v1.json": (
        "docs/strategy/contracts/HDS_STRUCTURE_BUNDLE_CONTRACT_V1.json"
    ),
    "contracts/mechanism_family_cv_contract_v1.json": (
        "docs/strategy/contracts/MECHANISM_FAMILY_CV_CONTRACT_V1.json"
    ),
    "contracts/owner_decision_capture_schema_v1.json": (
        "docs/strategy/contracts/OWNER_DECISION_CAPTURE_SCHEMA_V1.json"
    ),
    "contracts/rev3_governance_contract_v1.json": (
        "docs/strategy/contracts/REV3_GOVERNANCE_CONTRACT_V1.json"
    ),
    "control/rev3_current_selector.json": (
        "control/rev3/REV3_CURRENT_SELECTOR.json"
    ),
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")


def _zip_info(name: str) -> ZipInfo:
    name.encode("ascii")
    info = ZipInfo(name, FIXED_ZIP_TIME)
    info.compress_type = ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def build_package(output: Path) -> dict[str, object]:
    payloads: dict[str, bytes] = {}
    entries: list[dict[str, object]] = []
    for archive_name, source_name in sorted(PACKAGE_INPUTS.items()):
        source_path = REPOSITORY_ROOT / source_name
        data = source_path.read_bytes()
        archive_name.encode("ascii")
        payloads[archive_name] = data
        entries.append(
            {
                "archive_path": archive_name,
                "sha256": _sha256(data),
                "size_bytes": len(data),
                "source_path": source_name,
            }
        )

    logical_digest = _sha256(_canonical_json(entries))
    manifest = {
        "archive_filename_policy": "ASCII_ONLY",
        "audit_report_sha256": (
            "8536f4644fdc56cc71fa5a43699b43894c8f5d2c007ff772d68c29cc4546c1c1"
        ),
        "entries": entries,
        "entry_count": len(entries),
        "installation_status": "NOT_INSTALLED",
        "logical_digest": "sha256:" + logical_digest,
        "package_status": "PROPOSED_PENDING_OWNER_APPROVAL",
        "schema_version": "arc3-rev3-strategy-package-manifest-v1",
    }
    manifest_bytes = _canonical_json(manifest)
    payloads["MANIFEST.json"] = manifest_bytes

    checksum_lines = [
        f"{_sha256(data)}  {name}"
        for name, data in sorted(payloads.items())
    ]
    payloads["SHA256SUMS"] = ("\n".join(checksum_lines) + "\n").encode(
        "ascii"
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(
        output,
        mode="w",
        compression=ZIP_DEFLATED,
        compresslevel=9,
        strict_timestamps=True,
    ) as archive:
        for name, data in sorted(payloads.items()):
            archive.writestr(_zip_info(name), data, compresslevel=9)

    return {
        "entry_count": len(payloads),
        "logical_digest": manifest["logical_digest"],
        "output": str(output),
        "sha256": _sha256(output.read_bytes()),
        "size_bytes": output.stat().st_size,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    result = build_package(arguments.output.resolve())
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
