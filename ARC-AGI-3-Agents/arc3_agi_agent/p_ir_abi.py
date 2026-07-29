"""Frozen L0 ABI v1 and its content-bound opcode semantics digest."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from .p_ir_types import (
    PIR_OPCODE_SPECS,
    PIR_OPCODE_VERSION,
    PIR_TYPE_VERSION,
    PIR_VALUE_TYPES,
    PIRProgram,
)
from .schema import digest_object

L0_ABI_VERSION: Final = "arc3-l0-abi-v1"
PIR_SEMANTICS_VERSION: Final = "arc3-p-ir-semantics-v1"


def _semantics_material() -> object:
    return {
        "abi_version": L0_ABI_VERSION,
        "opcode_version": PIR_OPCODE_VERSION,
        "type_version": PIR_TYPE_VERSION,
        "semantics_version": PIR_SEMANTICS_VERSION,
        "value_types": tuple(sorted(PIR_VALUE_TYPES)),
        "opcodes": tuple(
            PIR_OPCODE_SPECS[name] for name in sorted(PIR_OPCODE_SPECS)
        ),
    }


PIR_SEMANTICS_DIGEST: Final = (
    "p-ir-semantics:" + digest_object(_semantics_material())
)


@dataclass(frozen=True, slots=True)
class L0ABIManifest:
    l0_abi_version: str = L0_ABI_VERSION
    opcode_version: str = PIR_OPCODE_VERSION
    type_version: str = PIR_TYPE_VERSION
    semantics_version: str = PIR_SEMANTICS_VERSION
    semantics_digest: str = PIR_SEMANTICS_DIGEST

    def digest(self) -> str:
        return "l0-abi:" + digest_object(self)


def supported_l0_abi() -> L0ABIManifest:
    return L0ABIManifest()


def abi_compatibility_failures(program: PIRProgram) -> tuple[str, ...]:
    expected = supported_l0_abi()
    failures: list[str] = []
    if program.l0_abi_version != expected.l0_abi_version:
        failures.append("P_IR_ABI_VERSION_UNSUPPORTED")
    if program.opcode_version != expected.opcode_version:
        failures.append("P_IR_OPCODE_VERSION_UNSUPPORTED")
    if program.type_version != expected.type_version:
        failures.append("P_IR_TYPE_VERSION_UNSUPPORTED")
    if program.semantics_digest != expected.semantics_digest:
        failures.append("P_IR_SEMANTICS_DIGEST_MISMATCH")
    return tuple(sorted(set(failures)))


__all__ = [
    "L0_ABI_VERSION",
    "PIR_SEMANTICS_DIGEST",
    "PIR_SEMANTICS_VERSION",
    "L0ABIManifest",
    "abi_compatibility_failures",
    "supported_l0_abi",
]
