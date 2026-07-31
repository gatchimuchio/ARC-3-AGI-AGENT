#!/usr/bin/env python3
"""Run or verify the PH-D01B source-blind bubblewrap evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DISTILLATION_SOURCE = REPOSITORY_ROOT / "distillation" / "src"
if str(DISTILLATION_SOURCE) not in sys.path:
    sys.path.insert(0, str(DISTILLATION_SOURCE))

from hds_distill.source_blind_execution import (  # noqa: E402
    ROLE_ORDER,
    SourceBlindExecutionError,
    artifact_bytes,
    build_source_blind_execution_record,
    load_source_blind_execution_plan,
    verify_source_blind_execution_record,
)

PLAN_PATH = Path("distillation/input/source_blind_execution_plan.json")
REPORT_PATH = Path(
    "distillation/artifacts/reports/source_blind_execution.json"
)
BUBBLEWRAP_PATH = Path("/usr/bin/bwrap")

PROBE_PROGRAM = r"""
import json
import os
from pathlib import Path

mounts = json.loads(os.environ["SOURCE_BLIND_DATA_MOUNTS"])
mounted_targets = []
read_only_targets = []
mounted_file_read_count = 0
write_probe_denied_count = 0
for mount in mounts:
    target = Path(mount["target"])
    if not target.exists():
        raise SystemExit("MOUNT_TARGET_MISSING:" + target.as_posix())
    mounted_targets.append(target.as_posix())
    if target.is_dir():
        files = sorted(path for path in target.rglob("*") if path.is_file())
        if not files:
            raise SystemExit("MOUNT_DIRECTORY_EMPTY:" + target.as_posix())
        for path in files:
            path.read_bytes()
        mounted_file_read_count += len(files)
        write_target = target / ".source-blind-write-probe"
    else:
        target.read_bytes()
        mounted_file_read_count += 1
        write_target = target
    try:
        with write_target.open("ab") as stream:
            stream.write(b"x")
    except OSError:
        write_probe_denied_count += 1
        read_only_targets.append(target.as_posix())
    else:
        raise SystemExit("READ_ONLY_WRITE_SUCCEEDED:" + target.as_posix())

role_id = os.environ["SOURCE_BLIND_ROLE_ID"]
repository_root_visible = Path(
    os.environ["SOURCE_BLIND_ORIGINAL_REPOSITORY_ROOT"]
).exists()
environment_source_mount_observed = Path(
    "/source/environment_files"
).is_dir()
mount_namespace_enforced = (
    os.readlink("/proc/self/ns/mnt")
    != os.environ["SOURCE_BLIND_HOST_MOUNT_NAMESPACE"]
)
network_namespace_enforced = (
    os.readlink("/proc/self/ns/net")
    != os.environ["SOURCE_BLIND_HOST_NETWORK_NAMESPACE"]
)
result = {
    "role_id": role_id,
    "process_instance_count": 1,
    "mount_namespace_enforced": mount_namespace_enforced,
    "network_namespace_enforced": network_namespace_enforced,
    "repository_root_visible": repository_root_visible,
    "environment_source_mount_observed": (
        environment_source_mount_observed
    ),
    "mounted_targets": mounted_targets,
    "read_only_targets": read_only_targets,
    "mounted_file_read_count": mounted_file_read_count,
    "write_probe_denied_count": write_probe_denied_count,
    "probe_status": "PASS",
}
print(json.dumps(result, sort_keys=True, separators=(",", ":")))
"""


def _role_index(plan: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    roles = plan.get("roles")
    if not isinstance(roles, list):
        raise SourceBlindExecutionError("D01B_SOURCE_BLIND_ROLES_NOT_ARRAY")
    result: dict[str, Mapping[str, Any]] = {}
    for value in roles:
        if not isinstance(value, dict) or not isinstance(
            value.get("role_id"),
            str,
        ):
            raise SourceBlindExecutionError(
                "D01B_SOURCE_BLIND_ROLE_INVALID"
            )
        result[value["role_id"]] = value
    if tuple(result) != ROLE_ORDER:
        raise SourceBlindExecutionError(
            "D01B_SOURCE_BLIND_ROLE_ORDER"
        )
    return result


def _data_mounts(
    repository_root: Path,
    role: Mapping[str, Any],
) -> list[dict[str, str]]:
    values = role.get("mount_allowlist")
    if not isinstance(values, list):
        raise SourceBlindExecutionError(
            "D01B_SOURCE_BLIND_MOUNTS_NOT_ARRAY"
        )
    mounts: list[dict[str, str]] = []
    for value in values:
        if not isinstance(value, dict):
            raise SourceBlindExecutionError(
                "D01B_SOURCE_BLIND_MOUNT_INVALID"
            )
        source_path = value.get("source_path")
        target = value.get("target")
        if not isinstance(source_path, str) or not isinstance(target, str):
            raise SourceBlindExecutionError(
                "D01B_SOURCE_BLIND_MOUNT_INVALID"
            )
        source = (repository_root / source_path).resolve()
        try:
            source.relative_to(repository_root)
        except ValueError as exc:
            raise SourceBlindExecutionError(
                "D01B_SOURCE_BLIND_MOUNT_SOURCE_ESCAPE"
            ) from exc
        if not source.exists():
            raise SourceBlindExecutionError(
                "D01B_SOURCE_BLIND_MOUNT_SOURCE_MISSING:" + source_path
            )
        source_digest = value.get("source_digest")
        if not isinstance(source_digest, str):
            raise SourceBlindExecutionError(
                "D01B_SOURCE_BLIND_MOUNT_DIGEST_INVALID"
            )
        if source.is_dir():
            manifest_path = (
                repository_root
                / "distillation/manifests/source_content/"
                "arc3-environment-source-bundle.json"
            )
            manifest = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )
            observed_digest = manifest.get("directory_merkle_root")
        else:
            artifact = json.loads(source.read_text(encoding="utf-8"))
            observed_digest = artifact.get("content_digest")
        if observed_digest != source_digest:
            raise SourceBlindExecutionError(
                "D01B_SOURCE_BLIND_MOUNT_DIGEST_MISMATCH:" + source_path
            )
        mounts.append(
            {
                "source": str(source),
                "source_path": source_path,
                "target": target,
            }
        )
    return mounts


def _materialize_exact_environment_projection(
    repository_root: Path,
    destination: Path,
) -> None:
    manifest_path = (
        repository_root
        / "distillation/manifests/source_content/"
        "arc3-environment-source-bundle.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = manifest.get("files")
    if not isinstance(files, list) or len(files) != 50:
        raise SourceBlindExecutionError(
            "D01B_SOURCE_BLIND_ENVIRONMENT_MANIFEST_INVALID"
        )
    for value in files:
        if not isinstance(value, dict):
            raise SourceBlindExecutionError(
                "D01B_SOURCE_BLIND_ENVIRONMENT_FILE_INVALID"
            )
        relative_path = value.get("repository_relative_posix_path")
        expected_sha256 = value.get("sha256")
        if (
            not isinstance(relative_path, str)
            or not relative_path.startswith("environment_files/")
            or not isinstance(expected_sha256, str)
        ):
            raise SourceBlindExecutionError(
                "D01B_SOURCE_BLIND_ENVIRONMENT_FILE_INVALID"
            )
        source = (repository_root / relative_path).resolve()
        target = destination / relative_path.removeprefix(
            "environment_files/"
        )
        payload = source.read_bytes()
        if hashlib.sha256(payload).hexdigest() != expected_sha256:
            raise SourceBlindExecutionError(
                "D01B_SOURCE_BLIND_ENVIRONMENT_FILE_DRIFT:"
                + relative_path
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    projected_files = [
        path for path in destination.rglob("*") if path.is_file()
    ]
    if len(projected_files) != 50:
        raise SourceBlindExecutionError(
            "D01B_SOURCE_BLIND_ENVIRONMENT_PROJECTION_COUNT"
        )


def _probe_role(
    repository_root: Path,
    role: Mapping[str, Any],
) -> dict[str, Any]:
    mounts = _data_mounts(repository_root, role)
    with tempfile.TemporaryDirectory(
        prefix="arc3-d01b-source-blind-",
    ) as temporary_directory:
        temporary_root = Path(temporary_directory)
        for index, mount in enumerate(mounts):
            if mount["source_path"] == "environment_files":
                projection = temporary_root / f"projection-{index}"
                _materialize_exact_environment_projection(
                    repository_root,
                    projection,
                )
                mount["source"] = str(projection)
        parent_directories = sorted(
            {
                str(Path(mount["target"]).parent)
                for mount in mounts
                if str(Path(mount["target"]).parent) != "/"
            },
            key=lambda item: (item.count("/"), item),
        )
        command = [
            str(BUBBLEWRAP_PATH),
            "--die-with-parent",
            "--new-session",
            "--unshare-all",
            "--ro-bind",
            "/usr",
            "/usr",
            "--ro-bind",
            "/lib",
            "/lib",
            "--ro-bind",
            "/lib64",
            "/lib64",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--tmpfs",
            "/tmp",
            "--dir",
            "/workspace",
        ]
        for directory in parent_directories:
            command.extend(["--dir", directory])
        for mount in mounts:
            command.extend(
                [
                    "--ro-bind",
                    mount["source"],
                    mount["target"],
                ]
            )
        host_mount_namespace = os.readlink("/proc/self/ns/mnt")
        host_network_namespace = os.readlink("/proc/self/ns/net")
        role_id = str(role["role_id"])
        data_mounts = [
            {"target": mount["target"]}
            for mount in mounts
        ]
        command.extend(
            [
                "--setenv",
                "SOURCE_BLIND_ROLE_ID",
                role_id,
                "--setenv",
                "SOURCE_BLIND_DATA_MOUNTS",
                json.dumps(
                    data_mounts,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                "--setenv",
                "SOURCE_BLIND_ORIGINAL_REPOSITORY_ROOT",
                str(repository_root),
                "--setenv",
                "SOURCE_BLIND_HOST_MOUNT_NAMESPACE",
                host_mount_namespace,
                "--setenv",
                "SOURCE_BLIND_HOST_NETWORK_NAMESPACE",
                host_network_namespace,
                "--chdir",
                "/",
                "/usr/bin/python3",
                "-c",
                PROBE_PROGRAM,
            ]
        )
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    if completed.returncode != 0:
        raise SourceBlindExecutionError(
            "D01B_SOURCE_BLIND_PROBE_FAILED:"
            + role_id
            + ":"
            + completed.stderr.strip()
        )
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise SourceBlindExecutionError(
            "D01B_SOURCE_BLIND_PROBE_OUTPUT_INVALID:" + role_id
        ) from exc
    if not isinstance(value, dict):
        raise SourceBlindExecutionError(
            "D01B_SOURCE_BLIND_PROBE_OUTPUT_NOT_OBJECT:" + role_id
        )
    return value


def build_live_record(repository_root: Path) -> dict[str, Any]:
    """Run all three role probes and build deterministic checked evidence."""

    plan_path = repository_root / PLAN_PATH
    plan = load_source_blind_execution_plan(plan_path)
    roles = _role_index(plan)
    probe_results = [
        _probe_role(repository_root, roles[role_id])
        for role_id in ROLE_ORDER
    ]
    tool_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return build_source_blind_execution_record(
        plan,
        probe_results=probe_results,
        probe_tool_sha256=tool_sha256,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=REPOSITORY_ROOT,
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write-report", action="store_true")
    mode.add_argument("--verify-report", action="store_true")
    mode.add_argument("--verify-record-only", action="store_true")
    arguments = parser.parse_args()
    repository_root = arguments.root.resolve()
    report_path = repository_root / REPORT_PATH
    if arguments.verify_record_only:
        record = verify_source_blind_execution_record(
            repository_root / PLAN_PATH,
            report_path,
            probe_tool_path=Path(__file__).resolve(),
            bubblewrap_path=BUBBLEWRAP_PATH,
        )
    else:
        record = build_live_record(repository_root)
        encoded = artifact_bytes(record)
        if arguments.write_report:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_bytes(encoded)
        else:
            try:
                checked = report_path.read_bytes()
            except OSError as exc:
                raise SourceBlindExecutionError(
                    "D01B_SOURCE_BLIND_REPORT_UNREADABLE"
                ) from exc
            if checked != encoded:
                raise SourceBlindExecutionError(
                    "D01B_SOURCE_BLIND_REPORT_MISMATCH"
                )
    summary = {
        "content_digest": record["content_digest"],
        "role_count": len(record["role_records"]),
        "status": "PASS",
    }
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
