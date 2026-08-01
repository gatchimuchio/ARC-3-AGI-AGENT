#!/usr/bin/env python3
"""Refresh or verify the rev3 current-authority manifest deterministically."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = (
    REPOSITORY_ROOT
    / "docs"
    / "strategy"
    / "REV3_CURRENT_AUTHORITY_MANIFEST.json"
)
CONTENT_DIGEST_PREFIX = "rev3-current-authority-manifest:"


class ManifestRefreshError(RuntimeError):
    """Raised when the manifest cannot be refreshed safely."""


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ManifestRefreshError("manifest root must be an object")
    return value


def _entry_path(
    repository_root: Path,
    manifest_path: Path,
    raw_path: object,
) -> tuple[str, Path]:
    if not isinstance(raw_path, str) or not raw_path:
        raise ManifestRefreshError("manifest entry path must be a string")
    relative = Path(raw_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ManifestRefreshError(f"unsafe manifest entry path: {raw_path}")
    resolved_root = repository_root.resolve()
    resolved = (resolved_root / relative).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ManifestRefreshError(
            f"manifest entry escapes repository: {raw_path}"
        ) from exc
    if resolved == manifest_path.resolve():
        raise ManifestRefreshError(
            "authority manifest cannot contain a hash of itself"
        )
    if not resolved.is_file():
        raise ManifestRefreshError(
            f"manifest entry does not exist: {raw_path}"
        )
    return relative.as_posix(), resolved


def render_refreshed_manifest(
    repository_root: Path,
    manifest_path: Path,
    additions: Mapping[str, str] | None = None,
) -> tuple[bytes, tuple[str, ...], str]:
    """Return refreshed bytes, changed entry paths, and the logical digest."""

    manifest = _load_object(manifest_path)
    raw_entries = manifest.get("entries")
    if not isinstance(raw_entries, list):
        raise ManifestRefreshError("manifest entries must be an array")

    additions = additions or {}
    raw_paths = {
        str(item.get("path"))
        for item in raw_entries
        if isinstance(item, dict)
    }
    for path, role in additions.items():
        if not path or not role:
            raise ManifestRefreshError("added entry path and role are required")
        if path not in raw_paths:
            raw_entries.append({"path": path, "role": role, "sha256": ""})
            raw_paths.add(path)
        else:
            existing = next(
                item
                for item in raw_entries
                if isinstance(item, dict) and item.get("path") == path
            )
            if existing.get("role") != role:
                raise ManifestRefreshError(
                    f"existing manifest role mismatch for {path}"
                )

    seen: set[str] = set()
    changed_paths: list[str] = []
    entries: list[dict[str, Any]] = []
    for index, raw_entry in enumerate(raw_entries):
        if not isinstance(raw_entry, dict):
            raise ManifestRefreshError(
                f"manifest entry {index} must be an object"
            )
        path_value, artifact = _entry_path(
            repository_root,
            manifest_path,
            raw_entry.get("path"),
        )
        if path_value in seen:
            raise ManifestRefreshError(
                f"duplicate manifest entry path: {path_value}"
            )
        seen.add(path_value)
        actual_sha256 = hashlib.sha256(artifact.read_bytes()).hexdigest()
        entry = dict(raw_entry)
        if entry.get("sha256") != actual_sha256:
            changed_paths.append(path_value)
        entry["path"] = path_value
        entry["sha256"] = actual_sha256
        entries.append(entry)

    entries.sort(key=lambda item: str(item["path"]))
    manifest["entries"] = entries
    manifest["entry_count"] = len(entries)

    excluded = manifest.get("digest_excluded_fields")
    if excluded != ["content_digest"]:
        raise ManifestRefreshError(
            "manifest digest exclusions must equal ['content_digest']"
        )
    current_digest = manifest.get("content_digest")
    if not isinstance(current_digest, str) or not current_digest.startswith(
        CONTENT_DIGEST_PREFIX
    ):
        raise ManifestRefreshError("manifest content digest prefix is invalid")
    digest_body = dict(manifest)
    digest_body.pop("content_digest")
    content_digest = CONTENT_DIGEST_PREFIX + hashlib.sha256(
        _canonical_json(digest_body).encode("utf-8")
    ).hexdigest()
    manifest["content_digest"] = content_digest
    payload = (
        json.dumps(
            manifest,
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")
    return payload, tuple(sorted(changed_paths)), content_digest


def _atomic_write(path: Path, payload: bytes) -> None:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent,
            prefix=path.name + ".",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.replace(path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
    )
    parser.add_argument(
        "--add-entry",
        action="append",
        default=[],
        metavar="PATH=ROLE",
    )
    arguments = parser.parse_args()
    additions: dict[str, str] = {}
    for binding in arguments.add_entry:
        if "=" not in binding:
            raise ManifestRefreshError(
                "--add-entry must use PATH=ROLE"
            )
        path, role = binding.split("=", 1)
        if not path or not role or path in additions:
            raise ManifestRefreshError(
                "--add-entry path and role must be non-empty and unique"
            )
        additions[path] = role
    manifest_path = arguments.manifest.resolve()
    payload, changed_paths, content_digest = render_refreshed_manifest(
        REPOSITORY_ROOT,
        manifest_path,
        additions,
    )
    current_payload = manifest_path.read_bytes()
    is_current = current_payload == payload
    if arguments.write and not is_current:
        _atomic_write(manifest_path, payload)
        is_current = True
    print(
        json.dumps(
            {
                "changed_entry_count": len(changed_paths),
                "changed_entry_paths": list(changed_paths),
                "content_digest": content_digest,
                "entry_count": json.loads(payload)["entry_count"],
                "mode": "WRITE" if arguments.write else "CHECK",
                "status": "PASS" if is_current else "STALE",
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0 if is_current else 1


if __name__ == "__main__":
    raise SystemExit(main())
