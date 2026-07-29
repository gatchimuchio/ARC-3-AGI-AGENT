"""Frozen logical identity for one executable ARC3 subject."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Sequence

from .generic_compute import GenericInstructionBody
from .generic_hds import HDSConfiguration
from .generic_memory import SemanticRecord
from .p_ir import p_ir_program_logical_digest
from .p_ir_abi import L0_ABI_VERSION
from .p_ir_types import PIRProgram
from .schema import digest_object

RUNTIME_IDENTITY_VERSION = "arc3-runtime-identity-v1"


@lru_cache(maxsize=32)
def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


@lru_cache(maxsize=4)
def _source_tree_digest(package_directory: Path) -> str:
    source_root = package_directory.parent
    paths = list(package_directory.rglob("*.py"))
    agent_entrypoint = source_root / "agents" / "templates" / "generic_agi_agent.py"
    if agent_entrypoint.is_file():
        paths.append(agent_entrypoint)
    digest = hashlib.sha256()
    for path in sorted(set(paths), key=lambda item: item.relative_to(source_root).as_posix()):
        relative = path.relative_to(source_root).as_posix().encode("utf-8")
        body = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(body).to_bytes(8, "big"))
        digest.update(body)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class RuntimeIdentity:
    code_tree_digest: str
    l0_abi_version: str
    p_logical_digest: str
    j_implementation_digest: str
    j_config_digest: str
    m0_logical_digest: str
    adapter_digest: str
    dependency_lock_digest: str

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        for field_name in (
            "code_tree_digest",
            "l0_abi_version",
            "p_logical_digest",
            "j_implementation_digest",
            "j_config_digest",
            "m0_logical_digest",
            "adapter_digest",
            "dependency_lock_digest",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value:
                failures.append(
                    "RUNTIME_IDENTITY_FIELD_MISSING:" + field_name
                )
        return tuple(failures)

    def digest(self) -> str:
        failures = self.validate()
        if failures:
            raise ValueError(";".join(failures))
        return "runtime-identity:" + digest_object(self)


def build_runtime_identity(
    *,
    p_bundle: GenericInstructionBody,
    p_ir_program: PIRProgram,
    hds_configuration: HDSConfiguration,
    initial_memory_records: Sequence[SemanticRecord],
) -> RuntimeIdentity:
    """Measure the local executable without incorporating run/game identity."""

    package_directory = Path(__file__).resolve().parent
    project_directory = package_directory.parent
    lock_path = project_directory / "uv.lock"
    hds_path = package_directory / "generic_hds.py"
    adapter_path = package_directory / "generic_env.py"
    identity = RuntimeIdentity(
        code_tree_digest="sha256:" + _source_tree_digest(package_directory),
        l0_abi_version=L0_ABI_VERSION,
        p_logical_digest="p-runtime-logical:"
        + digest_object(
            {
                "instruction_body": p_bundle.digest(),
                "p_ir": p_ir_program_logical_digest(p_ir_program),
            }
        ),
        j_implementation_digest="sha256:" + _file_digest(hds_path),
        j_config_digest="hds-config:" + digest_object(hds_configuration),
        m0_logical_digest="m0:" + digest_object(tuple(initial_memory_records)),
        adapter_digest="sha256:" + _file_digest(adapter_path),
        dependency_lock_digest=(
            "sha256:" + _file_digest(lock_path)
            if lock_path.is_file()
            else "sha256:" + hashlib.sha256(b"NO_DEPENDENCY_LOCK").hexdigest()
        ),
    )
    failures = identity.validate()
    if failures:
        raise ValueError(";".join(failures))
    return identity


__all__ = [
    "RUNTIME_IDENTITY_VERSION",
    "RuntimeIdentity",
    "build_runtime_identity",
]
