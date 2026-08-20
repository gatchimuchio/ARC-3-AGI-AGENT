#!/usr/bin/env python3
"""Validate repository operating-environment invariants without project dependencies."""

from __future__ import annotations

import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any


REQUIRED_SELECTOR_KEYS = (
    "active_strategy",
    "spec_path",
    "roadmap_path",
    "roadmap_manifest_path",
    "current_task_path",
    "active_point",
    "active_instruction_path",
    "auto_advance_allowed",
)

STABLE_SURFACES = (
    "AGENTS.md",
    "AUTHORITY_ORDER.md",
    "README.md",
    "docs/README.md",
    "docs/operations/REPOSITORY_OPERATING_MODEL.md",
    "control/README.md",
    "ARC-AGI-3-Agents/AGENTS.md",
    "ARC-AGI-3-Agents/README.md",
)


class EnvironmentError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EnvironmentError(f"missing JSON: {path}") from exc
    except json.JSONDecodeError as exc:
        raise EnvironmentError(f"invalid JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise EnvironmentError(f"JSON root must be object: {path}")
    return data


def repo_path(root: Path, raw: Any, field: str) -> Path:
    if not isinstance(raw, str) or not raw:
        raise EnvironmentError(f"{field} must be a non-empty repository-relative path")
    if "\\" in raw:
        raise EnvironmentError(f"{field} must use POSIX separators: {raw}")
    posix = PurePosixPath(raw)
    if posix.is_absolute() or ".." in posix.parts:
        raise EnvironmentError(f"{field} escapes repository boundary: {raw}")
    return root.joinpath(*posix.parts)


def require_file(root: Path, raw: Any, field: str, prefix: str | None = None) -> Path:
    path = repo_path(root, raw, field)
    rel = path.relative_to(root).as_posix()
    if prefix is not None and not rel.startswith(prefix):
        raise EnvironmentError(f"{field} must be under {prefix}: {rel}")
    lower_parts = {part.lower() for part in PurePosixPath(rel).parts}
    if "history" in lower_parts or any(part.startswith("historical") for part in lower_parts):
        raise EnvironmentError(f"{field} selects historical content: {rel}")
    if not path.is_file():
        raise EnvironmentError(f"{field} does not resolve to a file: {rel}")
    return path


def same(label: str, left: Any, right: Any) -> None:
    if left != right:
        raise EnvironmentError(f"{label} mismatch: selector={left!r}, selected={right!r}")


def validate(root: Path) -> int:
    checks = 0
    selector_path = root / "control" / "CURRENT_SELECTOR.json"
    selector = load_json(selector_path)

    missing = [key for key in REQUIRED_SELECTOR_KEYS if key not in selector]
    if missing:
        raise EnvironmentError(f"selector missing keys: {', '.join(missing)}")
    checks += len(REQUIRED_SELECTOR_KEYS)

    spec_path = require_file(root, selector["spec_path"], "spec_path", "docs/strategy/")
    roadmap_path = require_file(root, selector["roadmap_path"], "roadmap_path", "docs/roadmap/")
    manifest_path = require_file(
        root, selector["roadmap_manifest_path"], "roadmap_manifest_path", "control/"
    )
    task_path = require_file(root, selector["current_task_path"], "current_task_path", "control/")
    instruction_path = require_file(
        root, selector["active_instruction_path"], "active_instruction_path", "docs/instructions/"
    )
    _ = (spec_path, roadmap_path, instruction_path)
    checks += 5

    task = load_json(task_path)
    manifest = load_json(manifest_path)

    same("strategy_id", selector["active_strategy"], task.get("strategy_id"))
    same("manifest strategy_id", selector["active_strategy"], manifest.get("strategy_id"))
    same("active_point", selector["active_point"], task.get("active_point"))
    same(
        "active_instruction_path",
        selector["active_instruction_path"],
        task.get("active_instruction_path"),
    )
    if "current_point" in manifest:
        same("manifest current_point", selector["active_point"], manifest.get("current_point"))
    if "auto_advance_allowed" in task:
        same(
            "task auto_advance_allowed",
            selector["auto_advance_allowed"],
            task.get("auto_advance_allowed"),
        )
    if "auto_advance_allowed" in manifest:
        same(
            "manifest auto_advance_allowed",
            selector["auto_advance_allowed"],
            manifest.get("auto_advance_allowed"),
        )
    checks += 7

    mutable_tokens = (
        ("active_point", selector["active_point"]),
        ("active_strategy", selector["active_strategy"]),
    )
    for rel in STABLE_SURFACES:
        path = root / rel
        if not path.is_file():
            raise EnvironmentError(f"stable operating surface missing: {rel}")
        text = path.read_text(encoding="utf-8")
        for label, token in mutable_tokens:
            if isinstance(token, str) and token and token in text:
                raise EnvironmentError(
                    f"{rel} duplicates mutable {label}; keep CURRENT only in control/: {token}"
                )
            checks += 1

    print(
        json.dumps(
            {
                "status": "PASS",
                "selector": selector_path.relative_to(root).as_posix(),
                "active_point": selector["active_point"],
                "checks": checks,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def find_root(start: Path) -> Path:
    here = start.resolve()
    for candidate in (here, *here.parents):
        if (candidate / "control" / "CURRENT_SELECTOR.json").is_file():
            return candidate
    raise EnvironmentError("repository root not found from current path")


def main() -> int:
    try:
        root = find_root(Path.cwd())
        return validate(root)
    except EnvironmentError as exc:
        print(f"REPOSITORY_ENVIRONMENT_FAIL: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
