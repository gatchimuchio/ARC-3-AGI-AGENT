#!/usr/bin/env python3
"""Validate and describe the exact Linux wheelhouse used by M4-P05."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import zipfile
from email.parser import BytesParser
from pathlib import Path
from typing import Final, Sequence, cast

REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[1]
M4_P02_REPORT_PATH: Final = Path(
    "analysis/product/rev5_1/m4_p02_freeze_manifest.json"
)
M4_P04_REPORT_PATH: Final = Path(
    "analysis/product/rev5_1/m4_p04_clean_full_sample_closure.json"
)
RELEASE_WHEEL_PATH: Final = Path(
    "release/rev5_1/arc3_completion_agent_release-0.1.0-py3-none-any.whl"
)
OUTPUT_MANIFEST_PATH: Final = Path(
    "analysis/product/rev5_1/m4_p05_kaggle_wheelhouse_manifest.json"
)
DATASET_ID: Final = "tecchannn/arc3-completion-release-rev5-1"
DATASET_SLUG: Final = "arc3-completion-release-rev5-1"
RELEASE_DISTRIBUTION: Final = "arc3-completion-agent-release"
RELEASE_VERSION: Final = "0.1.0"
RELEASE_WHEEL_SHA256: Final = (
    "b930ea1b339d4cb153f6ae153b3cec1e57ea1661dc40c7616a3ad6c6bc5790e4"
)
RELEASE_DESCRIPTOR_SHA256: Final = (
    "c86470412a3479115784c8620dcdfb6e68724dc1805c65d9a458c2bc23284d99"
)
RELEASE_PACKAGE_SHA256: Final = (
    "99dd28966a0c20eaf2d93c3c47746d81d0ff2de666290f33b13526e8e878c923"
)
_EXACT_REQUIREMENT = re.compile(r"^([^<>=!~; ]+)==([^; ]+)$")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).casefold()


def _encoded(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _logical_seal(value: dict[str, object]) -> str:
    material = dict(value)
    material.pop("logical_content_sha256", None)
    return _sha256(
        json.dumps(
            material,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )


def _load_object(path: Path) -> tuple[dict[str, object], bytes]:
    payload = path.read_bytes()
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise TypeError("M4_P05_JSON_OBJECT_REQUIRED:" + path.as_posix())
    return {str(key): item for key, item in value.items()}, payload


def _wheel_metadata(path: Path) -> tuple[str, str, tuple[str, ...]]:
    with zipfile.ZipFile(path) as archive:
        metadata_names = tuple(
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        )
        if len(metadata_names) != 1:
            raise ValueError("M4_P05_WHEEL_METADATA_CARDINALITY_INVALID:" + path.name)
        message = BytesParser().parsebytes(archive.read(metadata_names[0]))
    name = str(message.get("Name", ""))
    version = str(message.get("Version", ""))
    requirements = tuple(str(item) for item in message.get_all("Requires-Dist", ()))
    if not name or not version:
        raise ValueError("M4_P05_WHEEL_IDENTITY_MISSING:" + path.name)
    return name, version, requirements


def _expected_dependencies(
    release_wheel: Path,
) -> tuple[tuple[str, str, str], ...]:
    name, version, requirements = _wheel_metadata(release_wheel)
    if _canonical_name(name) != RELEASE_DISTRIBUTION or version != RELEASE_VERSION:
        raise ValueError("M4_P05_RELEASE_WHEEL_IDENTITY_MISMATCH")
    parsed: list[tuple[str, str, str]] = []
    for raw in requirements:
        match = _EXACT_REQUIREMENT.fullmatch(raw)
        if match is None:
            raise ValueError("M4_P05_NONEXACT_RELEASE_REQUIREMENT:" + raw)
        parsed.append((_canonical_name(match.group(1)), match.group(2), raw))
    parsed.sort()
    if len(parsed) != 32 or len({name for name, _, _ in parsed}) != len(parsed):
        raise ValueError("M4_P05_RELEASE_REQUIREMENT_CARDINALITY_INVALID")
    return tuple(parsed)


def build_wheelhouse_manifest(
    *,
    root: Path,
    wheelhouse_dir: Path,
) -> dict[str, object]:
    p02, p02_payload = _load_object(root / M4_P02_REPORT_PATH)
    p04, p04_payload = _load_object(root / M4_P04_REPORT_PATH)
    release_source = root / RELEASE_WHEEL_PATH
    release_payload = release_source.read_bytes()
    if _sha256(release_payload) != RELEASE_WHEEL_SHA256:
        raise ValueError("M4_P05_RELEASE_WHEEL_SHA256_MISMATCH")
    if p02.get("status") != "M4_P02_PASS" or p04.get("status") != "M4_P04_PASS":
        raise ValueError("M4_P05_SOURCE_POINT_NOT_PASSED")

    wheelhouse_dir.mkdir(parents=True, exist_ok=True)
    release_target = wheelhouse_dir / release_source.name
    if release_target.is_file() and release_target.read_bytes() != release_payload:
        raise ValueError("M4_P05_EXISTING_RELEASE_WHEEL_DIFFERS")
    if not release_target.is_file():
        shutil.copyfile(release_source, release_target)

    expected = _expected_dependencies(release_target)
    expected_by_name = {name: (version, raw) for name, version, raw in expected}
    selected: dict[str, dict[str, object]] = {}
    unexpected: list[str] = []
    for path in sorted(wheelhouse_dir.glob("*.whl"), key=lambda item: item.name.casefold()):
        name, version, _ = _wheel_metadata(path)
        canonical = _canonical_name(name)
        if canonical == RELEASE_DISTRIBUTION:
            continue
        expectation = expected_by_name.get(canonical)
        if expectation is None:
            unexpected.append(path.name)
            continue
        expected_version, requirement = expectation
        if version != expected_version:
            raise ValueError(
                "M4_P05_DEPENDENCY_VERSION_MISMATCH:"
                + canonical
                + ":"
                + version
                + ":"
                + expected_version
            )
        if canonical in selected:
            raise ValueError("M4_P05_DUPLICATE_DEPENDENCY_WHEEL:" + canonical)
        payload = path.read_bytes()
        selected[canonical] = {
            "distribution": canonical,
            "version": version,
            "requirement": requirement,
            "filename": path.name,
            "sha256": _sha256(payload),
            "size_bytes": len(payload),
        }
    missing = sorted(set(expected_by_name) - set(selected))
    if missing or unexpected:
        raise ValueError(
            "M4_P05_WHEELHOUSE_CONTENT_INVALID:missing="
            + ",".join(missing)
            + ":unexpected="
            + ",".join(unexpected)
        )

    release_file = {
        "distribution": RELEASE_DISTRIBUTION,
        "version": RELEASE_VERSION,
        "filename": release_target.name,
        "sha256": RELEASE_WHEEL_SHA256,
        "size_bytes": len(release_payload),
    }
    dependency_files = tuple(selected[name] for name in sorted(selected))
    all_files = (release_file, *dependency_files)
    report: dict[str, object] = {
        "schema_version": "arc3-rev5-1-m4-p05-kaggle-wheelhouse-v1",
        "artifact_type": "M4KaggleFrozenWheelhouseManifest",
        "point_id": "M4-P05_KAGGLE_PACKAGE_NORMAL_RUN",
        "runtime_product": "ARC3CompletionAgent",
        "asset_stage": "RELEASE_FROZEN",
        "status": "WHEELHOUSE_READY",
        "dataset": {
            "id": DATASET_ID,
            "slug": DATASET_SLUG,
            "private": True,
            "kaggle_mount": "/kaggle/input/" + DATASET_SLUG,
        },
        "target_runtime": {
            "python": "CPython 3.12",
            "abi": "cp312",
            "platform": "Linux x86_64",
            "binary_policy": "WHEEL_ONLY_NO_NETWORK",
        },
        "source_bindings": {
            "M4_P02_freeze": {
                "path": M4_P02_REPORT_PATH.as_posix(),
                "sha256": _sha256(p02_payload),
                "logical_content_sha256": p02.get("logical_content_sha256"),
            },
            "M4_P04_same_release_full_sample": {
                "path": M4_P04_REPORT_PATH.as_posix(),
                "sha256": _sha256(p04_payload),
                "logical_content_sha256": p04.get("logical_content_sha256"),
                "status": p04.get("status"),
            },
        },
        "release_wheel": release_file,
        "release_descriptor_sha256": RELEASE_DESCRIPTOR_SHA256,
        "release_package_sha256": RELEASE_PACKAGE_SHA256,
        "dependency_count": len(dependency_files),
        "dependency_wheels": dependency_files,
        "file_count": len(all_files),
        "total_size_bytes": sum(
            cast(int, item["size_bytes"]) for item in all_files
        ),
        "all_file_sha256": {
            str(item["filename"]): str(item["sha256"]) for item in all_files
        },
        "network_required_at_runtime": False,
        "credential_binding_count": 0,
        "runtime_policy_changed": False,
    }
    report["logical_content_sha256"] = _logical_seal(report)
    return report


def _dataset_metadata() -> dict[str, object]:
    return {
        "title": "ARC3CompletionAgent rev5.1 frozen wheelhouse",
        "id": DATASET_ID,
        "licenses": [{"name": "Apache 2.0"}],
    }


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheelhouse-dir", type=Path, required=True)
    parser.add_argument(
        "--report",
        type=Path,
        default=REPOSITORY_ROOT / OUTPUT_MANIFEST_PATH,
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    wheelhouse_dir = arguments.wheelhouse_dir.resolve()
    report = build_wheelhouse_manifest(
        root=REPOSITORY_ROOT,
        wheelhouse_dir=wheelhouse_dir,
    )
    report_path = arguments.report.resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_bytes(_encoded(report))
    (wheelhouse_dir / "ARC3_M4_P05_WHEELHOUSE_MANIFEST.json").write_bytes(
        _encoded(report)
    )
    (wheelhouse_dir / "dataset-metadata.json").write_bytes(
        _encoded(_dataset_metadata())
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "dataset_id": DATASET_ID,
                "file_count": report["file_count"],
                "total_size_bytes": report["total_size_bytes"],
                "logical_content_sha256": report["logical_content_sha256"],
                "report": report_path.as_posix(),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
