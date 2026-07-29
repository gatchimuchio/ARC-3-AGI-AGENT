"""Deterministic allow-list package builder for the generic runtime."""

from __future__ import annotations

import hashlib
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

GENERIC_PACKAGE_VERSION = "arc3-generic-runtime-package-v1"
GENERIC_RUNTIME_MODULES = (
    "authority_state.py",
    "canonical_artifact.py",
    "causal_record.py",
    "competition_contract.py",
    "control_state.py",
    "decision_context.py",
    "data_access_ledger.py",
    "development_loop.py",
    "episode_transaction.py",
    "evaluation_registry.py",
    "evidence_binding.py",
    "evidence_policy.py",
    "experience_ledger.py",
    "generic_compute.py",
    "generic_env.py",
    "generic_hds.py",
    "generic_learning.py",
    "generic_memory.py",
    "generic_runtime.py",
    "generic_session.py",
    "generic_structural.py",
    "generic_types.py",
    "identity_boundary.py",
    "initial_state_compiler.py",
    "memory_overlay.py",
    "memory_backend.py",
    "memory_consolidation.py",
    "memory_event.py",
    "memory_image.py",
    "memory_retrieval.py",
    "memory_transaction.py",
    "negative_transfer.py",
    "p_bundle.py",
    "p_compiler_v2.py",
    "p_evaluator.py",
    "p_ir.py",
    "p_ir_abi.py",
    "p_ir_interpreter.py",
    "p_ir_resource.py",
    "p_ir_types.py",
    "p_ir_validator.py",
    "p_registry.py",
    "runtime_identity.py",
    "schema.py",
    "sealed_client.py",
    "taint.py",
    "version_lineage.py",
)
GENERIC_PACKAGE_FORBIDDEN_NAMES = (
    "teacher",
    "environment_files",
    "training_corpus",
    "solution_graph",
    "s5_rendered_policy",
    "p10_",
    "sealed_evaluator.py",
)


@dataclass(frozen=True, slots=True)
class GenericPackageReport:
    package_version: str
    filename: str
    sha256: str
    size_bytes: int
    member_names: tuple[str, ...]
    reproducible: bool
    forbidden_member_count: int
    forbidden_content_count: int
    training_examples_included: bool
    teacher_graph_included: bool
    sealed_source_included: bool

    def passed(self) -> bool:
        return (
            self.reproducible
            and self.forbidden_member_count == 0
            and self.forbidden_content_count == 0
            and not self.training_examples_included
            and not self.teacher_graph_included
            and not self.sealed_source_included
        )


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    info.create_system = 3
    return info


def build_generic_runtime_package(
    *,
    package_dir: Path,
    output_path: Path,
    module_names: Sequence[str] = GENERIC_RUNTIME_MODULES,
) -> tuple[str, ...]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    members: list[tuple[str, bytes]] = [
        (
            "arc3_agi_agent/__init__.py",
            (
                '"""Minimal pre-official GenericAGIRuntime package."""\n'
                "__all__: list[str] = []\n"
            ).encode("utf-8"),
        ),
    ]
    for name in sorted(set(module_names)):
        path = package_dir / name
        if not path.is_file():
            raise FileNotFoundError(path)
        members.append((f"arc3_agi_agent/{name}", path.read_bytes()))
    manifest = (
        f"package_version={GENERIC_PACKAGE_VERSION}\n"
        + "\n".join(name for name, _ in members)
        + "\n"
    ).encode("utf-8")
    members.append(("GENERIC_RUNTIME_MANIFEST.txt", manifest))
    members.sort(key=lambda item: item[0])
    with zipfile.ZipFile(
        output_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        strict_timestamps=True,
    ) as archive:
        for name, content in members:
            archive.writestr(_zip_info(name), content)
    return tuple(name for name, _ in members)


def audit_generic_runtime_package(
    *,
    package_dir: Path,
    first_output: Path,
    second_output: Path,
) -> GenericPackageReport:
    first_members = build_generic_runtime_package(
        package_dir=package_dir,
        output_path=first_output,
    )
    second_members = build_generic_runtime_package(
        package_dir=package_dir,
        output_path=second_output,
    )
    first_bytes = first_output.read_bytes()
    second_bytes = second_output.read_bytes()
    lowered_names = tuple(name.casefold() for name in first_members)
    forbidden_member_count = sum(
        1
        for name in lowered_names
        if any(term in name for term in GENERIC_PACKAGE_FORBIDDEN_NAMES)
    )
    forbidden_content_count = 0
    with zipfile.ZipFile(first_output) as archive:
        for name in first_members:
            content = archive.read(name).lower()
            if any(
                term.encode("utf-8") in content
                for term in (
                    "analysis/teacher",
                    "full_solution_corpus",
                    "level_solution_graph",
                    "s5_rendered_policy_training_corpus",
                )
            ):
                forbidden_content_count += 1
    return GenericPackageReport(
        package_version=GENERIC_PACKAGE_VERSION,
        filename=first_output.name,
        sha256=hashlib.sha256(first_bytes).hexdigest(),
        size_bytes=len(first_bytes),
        member_names=first_members,
        reproducible=(
            first_bytes == second_bytes and first_members == second_members
        ),
        forbidden_member_count=forbidden_member_count,
        forbidden_content_count=forbidden_content_count,
        training_examples_included=any(
            "training" in name for name in lowered_names
        ),
        teacher_graph_included=any(
            "teacher" in name or "solution_graph" in name
            for name in lowered_names
        ),
        sealed_source_included=any(
            "sealed_evaluator.py" in name for name in lowered_names
        ),
    )


__all__ = [
    "GENERIC_PACKAGE_FORBIDDEN_NAMES",
    "GENERIC_PACKAGE_VERSION",
    "GENERIC_RUNTIME_MODULES",
    "GenericPackageReport",
    "audit_generic_runtime_package",
    "build_generic_runtime_package",
]
