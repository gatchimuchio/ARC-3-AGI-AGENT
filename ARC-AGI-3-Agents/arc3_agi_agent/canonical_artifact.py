"""Canonical logical serialization and deterministic physical packaging."""

from __future__ import annotations

import hashlib
import io
import zipfile
from dataclasses import dataclass
from typing import Mapping

from .schema import canonical_json

CANONICAL_ARTIFACT_VERSION = "arc3-canonical-artifact-v1"
FIXED_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def canonical_json_bytes(value: object) -> bytes:
    """Return strict UTF-8 JSON; NaN and infinity are rejected by schema."""

    return canonical_json(value).encode("utf-8")


def logical_digest(
    value: object,
    *,
    namespace: str = "logical-artifact",
) -> str:
    return namespace + ":" + hashlib.sha256(
        canonical_json_bytes(value)
    ).hexdigest()


def physical_digest(
    payload: bytes,
    *,
    namespace: str = "physical-package",
) -> str:
    return namespace + ":" + hashlib.sha256(payload).hexdigest()


def build_canonical_zip(
    members: Mapping[str, bytes],
    *,
    compression: int = zipfile.ZIP_DEFLATED,
    compresslevel: int = 9,
) -> bytes:
    """Build byte-reproducible ZIP content with fixed metadata and order."""

    if not members:
        raise ValueError("CANONICAL_ZIP_MEMBER_REQUIRED")
    normalized: dict[str, bytes] = {}
    for name, payload in members.items():
        if (
            not isinstance(name, str)
            or not name
            or name.startswith("/")
            or "\\" in name
            or ".." in name.split("/")
        ):
            raise ValueError("CANONICAL_ZIP_MEMBER_NAME_INVALID")
        if not isinstance(payload, bytes):
            raise TypeError("CANONICAL_ZIP_MEMBER_BYTES_REQUIRED")
        if name in normalized:
            raise ValueError("CANONICAL_ZIP_MEMBER_DUPLICATE")
        normalized[name] = payload
    output = io.BytesIO()
    with zipfile.ZipFile(
        output,
        mode="w",
        compression=compression,
        compresslevel=compresslevel,
        strict_timestamps=True,
    ) as archive:
        for name in sorted(normalized):
            info = zipfile.ZipInfo(name, date_time=FIXED_ZIP_TIMESTAMP)
            info.compress_type = compression
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(
                info,
                normalized[name],
                compress_type=compression,
                compresslevel=compresslevel,
            )
    return output.getvalue()


@dataclass(frozen=True, slots=True)
class CanonicalArtifactDigest:
    logical_digest: str
    physical_digest: str


def digest_canonical_package(
    *,
    logical_value: object,
    members: Mapping[str, bytes],
) -> CanonicalArtifactDigest:
    package = build_canonical_zip(members)
    return CanonicalArtifactDigest(
        logical_digest=logical_digest(logical_value),
        physical_digest=physical_digest(package),
    )


__all__ = [
    "CANONICAL_ARTIFACT_VERSION",
    "FIXED_ZIP_TIMESTAMP",
    "CanonicalArtifactDigest",
    "build_canonical_zip",
    "canonical_json_bytes",
    "digest_canonical_package",
    "logical_digest",
    "physical_digest",
]
