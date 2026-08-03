"""Auditable source, dependency, and resource freeze for the release product."""

from __future__ import annotations

import ast
import base64
import csv
import hashlib
import importlib.metadata
import io
import sys
from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from .canonical_artifact import build_canonical_zip, canonical_json_bytes
from .product_release import (
    PRODUCT_RELEASE_DESCRIPTOR_FILENAME,
    PRODUCT_RELEASE_PACKAGE_FILENAME,
)
from .schema import digest_object

PRODUCT_FREEZE_SCHEMA_VERSION: Final = "arc3-product-freeze-v1"
RELEASE_DISTRIBUTION_NAME: Final = "arc3-completion-agent-release"
RELEASE_DISTRIBUTION_VERSION: Final = "0.1.0"
RELEASE_WHEEL_FILENAME: Final = (
    "arc3_completion_agent_release-0.1.0-py3-none-any.whl"
)
RELEASE_RESOURCE_FILENAME: Final = "arc3_official_sample_resources_v1.zip"
RELEASE_ENTRYPOINT: Final = "arc3-completion-product"
RELEASE_ENTRYPOINT_TARGET: Final = "arc3_agi_agent.product_runner:main"
RELEASE_ROOT_MODULES: Final = (
    "agents.templates.arc3_completion_agent",
    "arc3_agi_agent.product_runner",
)
_LOCAL_ROOTS: Final = frozenset({"agents", "arc3_agi_agent"})
_OPTIONAL_EXTERNAL_IMPORT_ROOTS: Final = frozenset({"agentops"})
_GENERATED_PACKAGE_INITS: Final[dict[str, bytes]] = {
    "agents/__init__.py": (
        b'"""Minimal release package; optional agent registry is excluded."""\n'
        b"__all__: list[str] = []\n"
    ),
    "agents/templates/__init__.py": (
        b'"""ARC3CompletionAgent release template package."""\n'
        b"__all__: list[str] = []\n"
    ),
    "arc3_agi_agent/__init__.py": (
        b'"""Minimal ARC3CompletionAgent RELEASE_FROZEN runtime."""\n'
        b"__all__: list[str] = []\n"
    ),
}
_FORBIDDEN_RELEASE_MEMBER_TOKENS: Final = (
    "analysis/",
    "environment_files/",
    "p05_next",
    "recording",
    "s5_",
    "solution_graph",
    "teacher/",
    "token",
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _module_name(relative: Path) -> str:
    parts = list(relative.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = Path(parts[-1]).stem
    return ".".join(parts)


def _module_index(package_root: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for root_name in sorted(_LOCAL_ROOTS):
        root = package_root / root_name
        for path in sorted(root.rglob("*.py")):
            relative = path.relative_to(package_root)
            module = _module_name(relative)
            if module in index:
                raise ValueError("RELEASE_MODULE_DUPLICATE:" + module)
            index[module] = relative
    return index


def _resolve_from_base(
    *,
    current_module: str,
    current_relative: Path,
    level: int,
    imported_module: str | None,
) -> str:
    if level == 0:
        return imported_module or ""
    current_package = (
        current_module
        if current_relative.name == "__init__.py"
        else current_module.rpartition(".")[0]
    )
    parts = current_package.split(".") if current_package else []
    up_count = level - 1
    if up_count > len(parts):
        raise ValueError("RELEASE_RELATIVE_IMPORT_ESCAPES_PACKAGE")
    base = parts[: len(parts) - up_count]
    if imported_module:
        base.extend(imported_module.split("."))
    return ".".join(base)


@dataclass(frozen=True, slots=True)
class RuntimeSourceClosure:
    source_members: tuple[tuple[str, bytes], ...]
    module_names: tuple[str, ...]
    external_import_roots: tuple[str, ...]
    dynamic_import_count: int
    source_tree_digest: str


def discover_runtime_source_closure(package_root: Path) -> RuntimeSourceClosure:
    """Resolve the local import graph from the only two release roots."""

    index = _module_index(package_root)
    missing_roots = tuple(module for module in RELEASE_ROOT_MODULES if module not in index)
    if missing_roots:
        raise ValueError("RELEASE_ROOT_MODULE_MISSING:" + ",".join(missing_roots))
    pending: deque[str] = deque(RELEASE_ROOT_MODULES)
    selected: set[str] = set()
    external_roots: set[str] = set()
    dynamic_import_count = 0
    while pending:
        module = pending.popleft()
        if module in selected:
            continue
        selected.add(module)
        relative = index[module]
        tree = ast.parse(
            (package_root / relative).read_text(encoding="utf-8"),
            filename=relative.as_posix(),
        )
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                dynamic_name = ""
                if isinstance(node.func, ast.Name):
                    dynamic_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    dynamic_name = node.func.attr
                if dynamic_name in {"__import__", "import_module"}:
                    dynamic_import_count += 1
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported = alias.name
                    if imported in index:
                        pending.append(imported)
                    elif imported.split(".", 1)[0] not in _LOCAL_ROOTS:
                        external_roots.add(imported.split(".", 1)[0])
            elif isinstance(node, ast.ImportFrom):
                base = _resolve_from_base(
                    current_module=module,
                    current_relative=relative,
                    level=node.level,
                    imported_module=node.module,
                )
                if base in index:
                    pending.append(base)
                for alias in node.names:
                    candidate = f"{base}.{alias.name}" if base else alias.name
                    if candidate in index:
                        pending.append(candidate)
                root = base.split(".", 1)[0] if base else ""
                if node.level == 0 and root and root not in _LOCAL_ROOTS:
                    external_roots.add(root)
    for module in tuple(selected):
        parts = module.split(".")[:-1]
        while parts:
            parent = ".".join(parts)
            if parent in index:
                selected.add(parent)
            parts.pop()
    source_members: dict[str, bytes] = {}
    for module in sorted(selected):
        relative = index[module]
        name = relative.as_posix()
        if name in _GENERATED_PACKAGE_INITS:
            continue
        source_members[name] = (package_root / relative).read_bytes()
    source_members.update(_GENERATED_PACKAGE_INITS)
    entries = tuple(
        {
            "path": name,
            "sha256": _sha256(payload),
            "size_bytes": len(payload),
        }
        for name, payload in sorted(source_members.items())
    )
    return RuntimeSourceClosure(
        source_members=tuple(sorted(source_members.items())),
        module_names=tuple(sorted(selected)),
        external_import_roots=tuple(
            sorted(root for root in external_roots if root not in sys.stdlib_module_names)
        ),
        dynamic_import_count=dynamic_import_count,
        source_tree_digest="release-source-tree:" + digest_object(entries),
    )


@dataclass(frozen=True, slots=True)
class DependencyPin:
    canonical_name: str
    distribution_name: str
    version: str

    @property
    def requirement(self) -> str:
        return f"{self.distribution_name}=={self.version}"


def _direct_distributions(import_roots: Sequence[str]) -> tuple[str, ...]:
    mapping = importlib.metadata.packages_distributions()
    selected: set[str] = set()
    for root in import_roots:
        names = mapping.get(root, ())
        if not names:
            if root in _OPTIONAL_EXTERNAL_IMPORT_ROOTS:
                continue
            raise ValueError("RELEASE_IMPORT_DISTRIBUTION_UNKNOWN:" + root)
        selected.update(canonicalize_name(name) for name in names)
    selected.discard(canonicalize_name("arc-agi-3-agents"))
    return tuple(sorted(selected))


def resolve_dependency_pins(import_roots: Sequence[str]) -> tuple[DependencyPin, ...]:
    """Pin the active platform's complete transitive runtime dependency set."""

    pending: deque[str] = deque(_direct_distributions(import_roots))
    selected: dict[str, DependencyPin] = {}
    while pending:
        canonical_name = canonicalize_name(pending.popleft())
        if canonical_name in selected:
            continue
        try:
            distribution = importlib.metadata.distribution(canonical_name)
        except importlib.metadata.PackageNotFoundError as error:
            raise ValueError(
                "RELEASE_DEPENDENCY_NOT_INSTALLED:" + canonical_name
            ) from error
        display_name = distribution.metadata.get("Name") or canonical_name
        selected[canonical_name] = DependencyPin(
            canonical_name=canonical_name,
            distribution_name=display_name,
            version=distribution.version,
        )
        for raw_requirement in distribution.requires or ():
            requirement = Requirement(raw_requirement)
            if requirement.marker is not None and not requirement.marker.evaluate():
                continue
            dependency = canonicalize_name(requirement.name)
            if dependency != canonicalize_name("arc-agi-3-agents"):
                pending.append(dependency)
    return tuple(selected[name] for name in sorted(selected))


def _wheel_metadata(dependencies: Sequence[DependencyPin]) -> bytes:
    lines = [
        "Metadata-Version: 2.1",
        f"Name: {RELEASE_DISTRIBUTION_NAME}",
        f"Version: {RELEASE_DISTRIBUTION_VERSION}",
        "Summary: RELEASE_FROZEN ARC3CompletionAgent runtime",
        "Requires-Python: ==3.12.*",
    ]
    lines.extend(f"Requires-Dist: {pin.requirement}" for pin in dependencies)
    return ("\n".join(lines) + "\n").encode("utf-8")


def _record_digest(payload: bytes) -> str:
    encoded = base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).rstrip(b"=")
    return "sha256=" + encoded.decode("ascii")


def _wheel_record(members: Mapping[str, bytes], record_name: str) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    for name, payload in sorted(members.items()):
        writer.writerow((name, _record_digest(payload), str(len(payload))))
    writer.writerow((record_name, "", ""))
    return output.getvalue().encode("utf-8")


@dataclass(frozen=True, slots=True)
class ReleaseWheelBuild:
    payload: bytes
    source_closure: RuntimeSourceClosure
    dependencies: tuple[DependencyPin, ...]
    member_names: tuple[str, ...]
    logical_digest: str


def build_release_wheel(
    *,
    package_root: Path,
    release_descriptor_payload: bytes,
    release_package_payload: bytes,
) -> ReleaseWheelBuild:
    closure = discover_runtime_source_closure(package_root)
    if closure.dynamic_import_count != 0:
        raise ValueError("RELEASE_DYNAMIC_IMPORT_FORBIDDEN")
    dependencies = resolve_dependency_pins(closure.external_import_roots)
    dist_info = (
        "arc3_completion_agent_release-0.1.0.dist-info"
    )
    members = dict(closure.source_members)
    members[
        "arc3_agi_agent/bundles/" + PRODUCT_RELEASE_DESCRIPTOR_FILENAME
    ] = release_descriptor_payload
    members[
        "arc3_agi_agent/bundles/" + PRODUCT_RELEASE_PACKAGE_FILENAME
    ] = release_package_payload
    release_manifest = {
        "schema_version": PRODUCT_FREEZE_SCHEMA_VERSION,
        "product": "ARC3CompletionAgent",
        "asset_stage": "RELEASE_FROZEN",
        "source_tree_digest": closure.source_tree_digest,
        "runtime_module_count": len(closure.module_names),
        "external_import_roots": closure.external_import_roots,
        "dependency_pins": tuple(pin.requirement for pin in dependencies),
        "release_descriptor_sha256": _sha256(release_descriptor_payload),
        "release_package_sha256": _sha256(release_package_payload),
        "entrypoint": RELEASE_ENTRYPOINT,
        "entrypoint_target": RELEASE_ENTRYPOINT_TARGET,
        "entrypoint_count": 1,
        "development_source_included": False,
        "credential_binding_count": 0,
    }
    release_manifest["content_digest"] = (
        "release-wheel-manifest:" + digest_object(release_manifest)
    )
    members[f"{dist_info}/METADATA"] = _wheel_metadata(dependencies)
    members[f"{dist_info}/WHEEL"] = (
        "Wheel-Version: 1.0\n"
        "Generator: ARC3CompletionAgent M4-P02\n"
        "Root-Is-Purelib: true\n"
        "Tag: py3-none-any\n"
    ).encode("utf-8")
    members[f"{dist_info}/entry_points.txt"] = (
        "[console_scripts]\n"
        f"{RELEASE_ENTRYPOINT} = {RELEASE_ENTRYPOINT_TARGET}\n"
    ).encode("utf-8")
    members[f"{dist_info}/top_level.txt"] = b"agents\narc3_agi_agent\n"
    members[f"{dist_info}/release_manifest.json"] = canonical_json_bytes(
        release_manifest
    )
    record_name = f"{dist_info}/RECORD"
    members[record_name] = _wheel_record(members, record_name)
    forbidden = tuple(
        name
        for name in members
        if any(token in name.casefold() for token in _FORBIDDEN_RELEASE_MEMBER_TOKENS)
    )
    if forbidden:
        raise ValueError("RELEASE_WHEEL_FORBIDDEN_MEMBER:" + ",".join(forbidden))
    payload = build_canonical_zip(members)
    logical_material = {
        "schema_version": PRODUCT_FREEZE_SCHEMA_VERSION,
        "source_tree_digest": closure.source_tree_digest,
        "dependencies": dependencies,
        "members": tuple(
            {
                "name": name,
                "sha256": _sha256(content),
                "size_bytes": len(content),
            }
            for name, content in sorted(members.items())
        ),
    }
    return ReleaseWheelBuild(
        payload=payload,
        source_closure=closure,
        dependencies=dependencies,
        member_names=tuple(sorted(members)),
        logical_digest="release-wheel:" + digest_object(logical_material),
    )


@dataclass(frozen=True, slots=True)
class ReleaseResourceBuild:
    payload: bytes
    member_names: tuple[str, ...]
    logical_digest: str


def build_official_sample_resource_archive(
    environments_dir: Path,
) -> ReleaseResourceBuild:
    members: dict[str, bytes] = {}
    for path in sorted(environments_dir.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        relative = path.relative_to(environments_dir).as_posix()
        members["environment_files/" + relative] = path.read_bytes()
    if not members:
        raise ValueError("RELEASE_OFFICIAL_SAMPLE_RESOURCE_EMPTY")
    payload = build_canonical_zip(members)
    logical_material = tuple(
        {
            "name": name,
            "sha256": _sha256(content),
            "size_bytes": len(content),
        }
        for name, content in sorted(members.items())
    )
    return ReleaseResourceBuild(
        payload=payload,
        member_names=tuple(sorted(members)),
        logical_digest="release-official-sample-resources:"
        + digest_object(logical_material),
    )


__all__ = [
    "PRODUCT_FREEZE_SCHEMA_VERSION",
    "RELEASE_DISTRIBUTION_NAME",
    "RELEASE_DISTRIBUTION_VERSION",
    "RELEASE_ENTRYPOINT",
    "RELEASE_ENTRYPOINT_TARGET",
    "RELEASE_RESOURCE_FILENAME",
    "RELEASE_ROOT_MODULES",
    "RELEASE_WHEEL_FILENAME",
    "DependencyPin",
    "ReleaseResourceBuild",
    "ReleaseWheelBuild",
    "RuntimeSourceClosure",
    "build_official_sample_resource_archive",
    "build_release_wheel",
    "discover_runtime_source_closure",
    "resolve_dependency_pins",
]
