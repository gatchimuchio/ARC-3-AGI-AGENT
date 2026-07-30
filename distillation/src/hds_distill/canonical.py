"""PH-D02A deterministic serialization and digest contract.

This module is deliberately dependency-free and side-effect-free.  It does
not read source material, write files, execute trajectories, import a runtime,
or grant any HDS/Owner approval.  Later distillation schemas may use this
codec; historical phase-local artifacts remain bound to their original
commits and bytes.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
import struct
import unicodedata
import zipfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Never, Self, cast

type JsonScalar = None | bool | int | float | str
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type TensorScalar = bool | int | float

CANONICAL_CONTRACT_VERSION: Final = "hds-canonical-contract-v1"
CANONICAL_JSON_VERSION: Final = "hds-canonical-json-v1"
CANONICAL_ZIP_VERSION: Final = "hds-canonical-zip-stored-v1"
CANONICAL_NPY_VERSION: Final = "hds-canonical-npy-v1"
CANONICAL_NPZ_VERSION: Final = "hds-canonical-npz-v1"

LOGICAL_DIGEST_DOMAIN: Final = b"HDS-LOGICAL-CONTENT-V1\0"
CONTENT_ID_DOMAIN: Final = b"HDS-CONTENT-ID-V1\0"
PHYSICAL_DIGEST_DOMAIN: Final = b"HDS-PHYSICAL-PACKAGE-V1\0"
RAW_TRAJECTORY_DIGEST_DOMAIN: Final = b"HDS-RAW-TRAJECTORY-V1\0"
CANONICAL_TRAJECTORY_DIGEST_DOMAIN: Final = (
    b"HDS-CANONICAL-TRAJECTORY-V1\0"
)

FIXED_ZIP_TIMESTAMP: Final = (1980, 1, 1, 0, 0, 0)
FIXED_ZIP_EXTERNAL_ATTR: Final = 0o100644 << 16
FIXED_ZIP_CREATE_SYSTEM: Final = 3
FIXED_ZIP_VERSION: Final = 20
NPY_HEADER_ALIGNMENT: Final = 64
MAX_TENSOR_RANK: Final = 64
MAX_TENSOR_ELEMENTS: Final = 100_000_000

_NAMESPACE_RE: Final = re.compile(
    r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$"
)
_TENSOR_NAME_RE: Final = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*$"
)
_NPY_MAGIC: Final = b"\x93NUMPY"
_NPY_VERSION_BYTES: Final = b"\x01\x00"


class CanonicalizationError(ValueError):
    """A stable fail-closed PH-D02A representation error."""


def _pointer(path: tuple[str, ...]) -> str:
    if not path:
        return ""
    return "/" + "/".join(
        item.replace("~", "~0").replace("/", "~1") for item in path
    )


def _raise(code: str, path: tuple[str, ...] = ()) -> Never:
    suffix = _pointer(path)
    raise CanonicalizationError(code + (":" + suffix if suffix else ""))


def _nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def _normalize_namespace(namespace: str) -> str:
    if not isinstance(namespace, str):
        raise TypeError("D02A_NAMESPACE_STRING_REQUIRED")
    normalized = _nfc(namespace)
    if not _NAMESPACE_RE.fullmatch(normalized):
        raise CanonicalizationError("D02A_NAMESPACE_INVALID:" + normalized)
    return normalized


def _decode_pointer(pointer: str) -> tuple[str, ...]:
    if not isinstance(pointer, str):
        raise TypeError("D02A_UNORDERED_POINTER_STRING_REQUIRED")
    if pointer == "":
        return ()
    if not pointer.startswith("/"):
        raise CanonicalizationError(
            "D02A_UNORDERED_POINTER_INVALID:" + pointer
        )
    decoded: list[str] = []
    for raw in pointer[1:].split("/"):
        index = 0
        result: list[str] = []
        while index < len(raw):
            character = raw[index]
            if character != "~":
                result.append(character)
                index += 1
                continue
            if index + 1 >= len(raw) or raw[index + 1] not in {"0", "1"}:
                raise CanonicalizationError(
                    "D02A_UNORDERED_POINTER_ESCAPE_INVALID:" + pointer
                )
            result.append("~" if raw[index + 1] == "0" else "/")
            index += 2
        decoded.append(_nfc("".join(result)))
    return tuple(decoded)


def _prepare_unordered_paths(
    pointers: Iterable[str],
) -> frozenset[tuple[str, ...]]:
    decoded = [_decode_pointer(pointer) for pointer in pointers]
    if len(decoded) != len(set(decoded)):
        raise CanonicalizationError("D02A_UNORDERED_POINTER_DUPLICATE")
    return frozenset(decoded)


def validate_confidence_ppm(value: object) -> int:
    """Return a valid integer confidence in parts per million."""

    if type(value) is not int:
        raise CanonicalizationError(
            "D02A_CONFIDENCE_PPM_INTEGER_REQUIRED"
        )
    confidence = value
    if not 0 <= confidence <= 1_000_000:
        raise CanonicalizationError(
            "D02A_CONFIDENCE_PPM_OUT_OF_RANGE"
        )
    return confidence


def _normalized_sort_key(value: JsonValue) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _normalize_value(
    value: object,
    *,
    path: tuple[str, ...],
    unordered_paths: frozenset[tuple[str, ...]],
    used_unordered_paths: set[tuple[str, ...]],
) -> JsonValue:
    if value is None:
        return None
    if type(value) is bool:
        return value
    if type(value) is int:
        return value
    if type(value) is float:
        numeric = value
        if not math.isfinite(numeric):
            _raise("D02A_NONFINITE_NUMBER_FORBIDDEN", path)
        return 0.0 if numeric == 0.0 else numeric
    if isinstance(value, str):
        return _nfc(value)
    if isinstance(value, Mapping):
        result: dict[str, JsonValue] = {}
        source_keys: dict[str, str] = {}
        for raw_key, raw_value in value.items():
            if not isinstance(raw_key, str):
                _raise("D02A_OBJECT_KEY_STRING_REQUIRED", path)
            key = _nfc(raw_key)
            if key in result:
                previous = source_keys[key]
                raise CanonicalizationError(
                    "D02A_NFC_KEY_COLLISION:"
                    + _pointer(path)
                    + ":"
                    + previous
                    + ":"
                    + raw_key
                )
            if key == "confidence":
                _raise(
                    "D02A_LEGACY_CONFIDENCE_FIELD_FORBIDDEN",
                    path + (key,),
                )
            if key == "confidence_ppm":
                validate_confidence_ppm(raw_value)
            source_keys[key] = raw_key
            result[key] = _normalize_value(
                raw_value,
                path=path + (key,),
                unordered_paths=unordered_paths,
                used_unordered_paths=used_unordered_paths,
            )
        return result
    if isinstance(value, list | tuple):
        unordered = path in unordered_paths
        if unordered:
            used_unordered_paths.add(path)
        child_path = path + ("*",) if unordered else path
        normalized_items = [
            _normalize_value(
                item,
                path=(
                    child_path
                    if unordered
                    else path + (str(index),)
                ),
                unordered_paths=unordered_paths,
                used_unordered_paths=used_unordered_paths,
            )
            for index, item in enumerate(value)
        ]
        if unordered:
            normalized_items.sort(key=_normalized_sort_key)
        return normalized_items
    if isinstance(value, set | frozenset):
        normalized_set = [
            _normalize_value(
                item,
                path=path + ("*",),
                unordered_paths=unordered_paths,
                used_unordered_paths=used_unordered_paths,
            )
            for item in value
        ]
        normalized_set.sort(key=_normalized_sort_key)
        return normalized_set
    _raise("D02A_UNSUPPORTED_JSON_VALUE", path)


def canonicalize(
    value: object,
    *,
    unordered_paths: Iterable[str] = (),
) -> JsonValue:
    """Normalize one supported value into the strict canonical JSON domain.

    Ordinary lists and tuples are order-sensitive.  A Python set/frozenset is
    always sorted by canonical item bytes.  JSON arrays are sorted only when
    selected by an explicit RFC 6901 pointer.  Descendants of an unordered
    array use ``*`` as their pointer segment.
    """

    prepared = _prepare_unordered_paths(unordered_paths)
    used: set[tuple[str, ...]] = set()
    normalized = _normalize_value(
        value,
        path=(),
        unordered_paths=prepared,
        used_unordered_paths=used,
    )
    unused = prepared - used
    if unused:
        pointers = ",".join(sorted(_pointer(path) for path in unused))
        raise CanonicalizationError(
            "D02A_UNORDERED_POINTER_NOT_ARRAY:" + pointers
        )
    return normalized


def canonical_json(
    value: object,
    *,
    unordered_paths: Iterable[str] = (),
) -> str:
    """Return canonical UTF-8 JSON text without a trailing newline."""

    normalized = canonicalize(value, unordered_paths=unordered_paths)
    return json.dumps(
        normalized,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def canonical_json_bytes(
    value: object,
    *,
    unordered_paths: Iterable[str] = (),
) -> bytes:
    """Return exact canonical UTF-8 JSON bytes."""

    return canonical_json(
        value,
        unordered_paths=unordered_paths,
    ).encode("utf-8")


def _reject_json_constant(value: str) -> object:
    raise CanonicalizationError(
        "D02A_NONFINITE_JSON_TOKEN_FORBIDDEN:" + value
    )


def _strict_object_pairs(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise CanonicalizationError(
                "D02A_DUPLICATE_JSON_KEY:" + key
            )
        result[key] = value
    return result


def parse_json_strict(payload: bytes) -> JsonValue:
    """Parse UTF-8 JSON while rejecting BOMs, duplicates, and non-finite data."""

    if not isinstance(payload, bytes):
        raise TypeError("D02A_JSON_BYTES_REQUIRED")
    if payload.startswith(b"\xef\xbb\xbf"):
        raise CanonicalizationError("D02A_UTF8_BOM_FORBIDDEN")
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise CanonicalizationError("D02A_JSON_UTF8_INVALID") from exc
    try:
        parsed = json.loads(
            text,
            object_pairs_hook=_strict_object_pairs,
            parse_constant=_reject_json_constant,
        )
    except json.JSONDecodeError as exc:
        raise CanonicalizationError("D02A_JSON_SYNTAX_INVALID") from exc
    return canonicalize(parsed)


def verify_canonical_json_bytes(
    payload: bytes,
    *,
    unordered_paths: Iterable[str] = (),
) -> JsonValue:
    """Return parsed content only when ``payload`` is already canonical."""

    parsed = parse_json_strict(payload)
    canonical = canonical_json_bytes(
        parsed,
        unordered_paths=unordered_paths,
    )
    if canonical != payload:
        raise CanonicalizationError("D02A_JSON_NOT_CANONICAL")
    return parsed


def normalize_repository_relative_posix_path(path: str) -> str:
    """Normalize and validate one repository/archive-relative POSIX path."""

    if not isinstance(path, str):
        raise TypeError("D02A_PATH_STRING_REQUIRED")
    normalized = _nfc(path)
    if (
        not normalized
        or normalized.startswith("/")
        or normalized.endswith("/")
        or "\\" in normalized
        or "\x00" in normalized
        or ":" in normalized
    ):
        raise CanonicalizationError("D02A_RELATIVE_POSIX_PATH_INVALID")
    parts = normalized.split("/")
    if any(not part or part in {".", ".."} for part in parts):
        raise CanonicalizationError("D02A_RELATIVE_POSIX_PATH_INVALID")
    return normalized


def _normalize_field_set(
    values: frozenset[str],
    category: str,
) -> frozenset[str]:
    normalized: set[str] = set()
    for value in values:
        if not isinstance(value, str) or not value:
            raise CanonicalizationError(
                "D02A_DIGEST_EXCLUSION_FIELD_INVALID:" + category
            )
        field = _nfc(value)
        if "/" in field or "~" in field:
            raise CanonicalizationError(
                "D02A_DIGEST_EXCLUSION_TOP_LEVEL_ONLY:" + field
            )
        if field in normalized:
            raise CanonicalizationError(
                "D02A_DIGEST_EXCLUSION_NFC_COLLISION:" + field
            )
        normalized.add(field)
    return frozenset(normalized)


@dataclass(frozen=True, slots=True)
class DigestExclusionPolicy:
    """Explicit top-level fields omitted from a logical digest or content ID.

    Nested IDs/digests remain bound.  This prevents a broad recursive
    exclusion from silently deleting provenance references.
    """

    id_fields: frozenset[str] = frozenset()
    digest_fields: frozenset[str] = frozenset()
    timestamp_fields: frozenset[str] = frozenset()
    physical_metadata_fields: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        categories = {
            "id": _normalize_field_set(self.id_fields, "id"),
            "digest": _normalize_field_set(
                self.digest_fields,
                "digest",
            ),
            "timestamp": _normalize_field_set(
                self.timestamp_fields,
                "timestamp",
            ),
            "physical": _normalize_field_set(
                self.physical_metadata_fields,
                "physical",
            ),
        }
        seen: dict[str, str] = {}
        for category, values in categories.items():
            for field in values:
                if field in seen:
                    raise CanonicalizationError(
                        "D02A_DIGEST_EXCLUSION_CATEGORY_OVERLAP:"
                        + field
                        + ":"
                        + seen[field]
                        + ":"
                        + category
                    )
                seen[field] = category
        object.__setattr__(self, "id_fields", categories["id"])
        object.__setattr__(
            self,
            "digest_fields",
            categories["digest"],
        )
        object.__setattr__(
            self,
            "timestamp_fields",
            categories["timestamp"],
        )
        object.__setattr__(
            self,
            "physical_metadata_fields",
            categories["physical"],
        )

    @property
    def excluded_fields(self) -> frozenset[str]:
        return frozenset(
            {
                *self.id_fields,
                *self.digest_fields,
                *self.timestamp_fields,
                *self.physical_metadata_fields,
            }
        )

    def as_json(self) -> dict[str, JsonValue]:
        return {
            "digest_fields": cast(
                list[JsonValue],
                sorted(self.digest_fields),
            ),
            "id_fields": cast(
                list[JsonValue],
                sorted(self.id_fields),
            ),
            "physical_metadata_fields": cast(
                list[JsonValue],
                sorted(self.physical_metadata_fields),
            ),
            "timestamp_fields": cast(
                list[JsonValue],
                sorted(self.timestamp_fields),
            ),
        }


def logical_digest_body(
    value: Mapping[str, object],
    *,
    policy: DigestExclusionPolicy,
    unordered_paths: Iterable[str] = (),
) -> dict[str, JsonValue]:
    """Normalize an object and remove only declared top-level self metadata."""

    normalized = canonicalize(
        value,
        unordered_paths=unordered_paths,
    )
    if not isinstance(normalized, dict):
        raise TypeError("D02A_LOGICAL_DIGEST_OBJECT_REQUIRED")
    return {
        key: item
        for key, item in normalized.items()
        if key not in policy.excluded_fields
    }


def _domain_hash(
    domain: bytes,
    namespace: str,
    payload: bytes,
) -> str:
    normalized_namespace = _normalize_namespace(namespace)
    digest = hashlib.sha256(
        domain
        + normalized_namespace.encode("ascii")
        + b"\0"
        + payload
    ).hexdigest()
    return normalized_namespace + ":" + digest


def logical_content_digest(
    namespace: str,
    value: Mapping[str, object],
    *,
    policy: DigestExclusionPolicy,
    unordered_paths: Iterable[str] = (),
) -> str:
    """Digest canonical logical content after explicit self-field exclusion."""

    body = logical_digest_body(
        value,
        policy=policy,
        unordered_paths=unordered_paths,
    )
    return _domain_hash(
        LOGICAL_DIGEST_DOMAIN,
        namespace,
        canonical_json_bytes(body),
    )


def content_derived_id(
    namespace: str,
    value: Mapping[str, object],
    *,
    policy: DigestExclusionPolicy,
    unordered_paths: Iterable[str] = (),
) -> str:
    """Derive a full-width, namespace-bound ID from canonical logical content."""

    body = logical_digest_body(
        value,
        policy=policy,
        unordered_paths=unordered_paths,
    )
    return _domain_hash(
        CONTENT_ID_DOMAIN,
        namespace,
        canonical_json_bytes(body),
    )


def physical_package_digest(namespace: str, payload: bytes) -> str:
    """Digest exact package bytes under a distinct physical domain."""

    if not isinstance(payload, bytes):
        raise TypeError("D02A_PHYSICAL_PACKAGE_BYTES_REQUIRED")
    return _domain_hash(PHYSICAL_DIGEST_DOMAIN, namespace, payload)


@dataclass(frozen=True, slots=True)
class CanonicalPackageDigests:
    logical_content_digest: str
    physical_package_digest: str

    def as_json(self) -> dict[str, JsonValue]:
        return {
            "logical_content_digest": self.logical_content_digest,
            "physical_package_digest": self.physical_package_digest,
        }


def digest_canonical_package(
    *,
    logical_namespace: str,
    physical_namespace: str,
    logical_value: Mapping[str, object],
    package_payload: bytes,
    policy: DigestExclusionPolicy,
    unordered_paths: Iterable[str] = (),
) -> CanonicalPackageDigests:
    """Return explicitly separated logical-content and physical-byte digests."""

    return CanonicalPackageDigests(
        logical_content_digest=logical_content_digest(
            logical_namespace,
            logical_value,
            policy=policy,
            unordered_paths=unordered_paths,
        ),
        physical_package_digest=physical_package_digest(
            physical_namespace,
            package_payload,
        ),
    )


def _normalize_zip_members(
    members: Mapping[str, bytes],
) -> dict[str, bytes]:
    if not members:
        raise CanonicalizationError("D02A_ZIP_MEMBER_REQUIRED")
    normalized: dict[str, bytes] = {}
    source_names: dict[str, str] = {}
    for source_name, payload in members.items():
        if not isinstance(source_name, str):
            raise TypeError("D02A_ZIP_MEMBER_NAME_STRING_REQUIRED")
        name = normalize_repository_relative_posix_path(source_name)
        if not isinstance(payload, bytes):
            raise TypeError("D02A_ZIP_MEMBER_BYTES_REQUIRED:" + name)
        if name in normalized:
            raise CanonicalizationError(
                "D02A_ZIP_MEMBER_NFC_COLLISION:"
                + source_names[name]
                + ":"
                + source_name
            )
        source_names[name] = source_name
        normalized[name] = payload
    return normalized


def build_canonical_zip(members: Mapping[str, bytes]) -> bytes:
    """Build a ZIP_STORED package with fixed metadata and lexical members."""

    normalized = _normalize_zip_members(members)
    output = io.BytesIO()
    with zipfile.ZipFile(
        output,
        mode="w",
        compression=zipfile.ZIP_STORED,
        allowZip64=False,
        strict_timestamps=True,
    ) as archive:
        archive.comment = b""
        for name in sorted(normalized, key=lambda item: item.encode("utf-8")):
            info = zipfile.ZipInfo(name, date_time=FIXED_ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = FIXED_ZIP_CREATE_SYSTEM
            info.create_version = FIXED_ZIP_VERSION
            info.extract_version = FIXED_ZIP_VERSION
            info.flag_bits = 0
            info.volume = 0
            info.internal_attr = 0
            info.external_attr = FIXED_ZIP_EXTERNAL_ATTR
            info.extra = b""
            info.comment = b""
            archive.writestr(
                info,
                normalized[name],
                compress_type=zipfile.ZIP_STORED,
            )
    return output.getvalue()


def verify_canonical_zip(payload: bytes) -> dict[str, bytes]:
    """Return members only when exact bytes satisfy the canonical ZIP contract."""

    if not isinstance(payload, bytes):
        raise TypeError("D02A_ZIP_BYTES_REQUIRED")
    try:
        with zipfile.ZipFile(io.BytesIO(payload), mode="r") as archive:
            if archive.comment:
                raise CanonicalizationError(
                    "D02A_ZIP_ARCHIVE_COMMENT_FORBIDDEN"
                )
            infos = archive.infolist()
            names = [info.filename for info in infos]
            expected_names = sorted(names, key=lambda item: item.encode("utf-8"))
            if names != expected_names:
                raise CanonicalizationError(
                    "D02A_ZIP_MEMBER_ORDER_INVALID"
                )
            members: dict[str, bytes] = {}
            for info in infos:
                name = normalize_repository_relative_posix_path(
                    info.filename
                )
                if name != info.filename:
                    raise CanonicalizationError(
                        "D02A_ZIP_MEMBER_NAME_NOT_NFC"
                    )
                if name in members:
                    raise CanonicalizationError(
                        "D02A_ZIP_MEMBER_DUPLICATE:" + name
                    )
                if info.is_dir():
                    raise CanonicalizationError(
                        "D02A_ZIP_DIRECTORY_ENTRY_FORBIDDEN:" + name
                    )
                if info.flag_bits & 0x1:
                    raise CanonicalizationError(
                        "D02A_ZIP_ENCRYPTION_FORBIDDEN:" + name
                    )
                if info.date_time != FIXED_ZIP_TIMESTAMP:
                    raise CanonicalizationError(
                        "D02A_ZIP_TIMESTAMP_INVALID:" + name
                    )
                if info.compress_type != zipfile.ZIP_STORED:
                    raise CanonicalizationError(
                        "D02A_ZIP_COMPRESSION_INVALID:" + name
                    )
                if info.create_system != FIXED_ZIP_CREATE_SYSTEM:
                    raise CanonicalizationError(
                        "D02A_ZIP_CREATE_SYSTEM_INVALID:" + name
                    )
                if info.create_version != FIXED_ZIP_VERSION:
                    raise CanonicalizationError(
                        "D02A_ZIP_CREATE_VERSION_INVALID:" + name
                    )
                if info.extract_version != FIXED_ZIP_VERSION:
                    raise CanonicalizationError(
                        "D02A_ZIP_EXTRACT_VERSION_INVALID:" + name
                    )
                if info.external_attr != FIXED_ZIP_EXTERNAL_ATTR:
                    raise CanonicalizationError(
                        "D02A_ZIP_MODE_INVALID:" + name
                    )
                if info.internal_attr != 0 or info.extra or info.comment:
                    raise CanonicalizationError(
                        "D02A_ZIP_EXTRA_METADATA_FORBIDDEN:" + name
                    )
                member = archive.read(info)
                if len(member) != info.file_size:
                    raise CanonicalizationError(
                        "D02A_ZIP_SIZE_MISMATCH:" + name
                    )
                members[name] = member
    except zipfile.BadZipFile as exc:
        raise CanonicalizationError("D02A_ZIP_INVALID") from exc
    if build_canonical_zip(members) != payload:
        raise CanonicalizationError("D02A_ZIP_BYTES_NOT_CANONICAL")
    return members


@dataclass(frozen=True, slots=True)
class _DTypeSpec:
    descriptor: str
    kind: str
    struct_code: str
    minimum: int | None = None
    maximum: int | None = None


_DTYPE_SPECS: Final[dict[str, _DTypeSpec]] = {
    "|b1": _DTypeSpec("|b1", "bool", "?"),
    "|i1": _DTypeSpec("|i1", "int", "b", -(2**7), 2**7 - 1),
    "|u1": _DTypeSpec("|u1", "int", "B", 0, 2**8 - 1),
    "<i2": _DTypeSpec("<i2", "int", "h", -(2**15), 2**15 - 1),
    "<u2": _DTypeSpec("<u2", "int", "H", 0, 2**16 - 1),
    "<i4": _DTypeSpec("<i4", "int", "i", -(2**31), 2**31 - 1),
    "<u4": _DTypeSpec("<u4", "int", "I", 0, 2**32 - 1),
    "<i8": _DTypeSpec("<i8", "int", "q", -(2**63), 2**63 - 1),
    "<u8": _DTypeSpec("<u8", "int", "Q", 0, 2**64 - 1),
    "<f2": _DTypeSpec("<f2", "float", "e"),
    "<f4": _DTypeSpec("<f4", "float", "f"),
    "<f8": _DTypeSpec("<f8", "float", "d"),
}


@dataclass(frozen=True, slots=True)
class CanonicalTensor:
    """A dependency-free canonical C-order tensor value."""

    dtype: str
    shape: tuple[int, ...]
    values: tuple[TensorScalar, ...]

    @classmethod
    def from_values(
        cls,
        *,
        dtype: str,
        shape: Sequence[int],
        values: Sequence[TensorScalar],
    ) -> Self:
        return cls(
            dtype=dtype,
            shape=tuple(shape),
            values=tuple(values),
        )


def _validate_shape(shape: tuple[int, ...]) -> int:
    if len(shape) > MAX_TENSOR_RANK:
        raise CanonicalizationError("D02A_TENSOR_RANK_EXCEEDED")
    dimensions: list[int] = []
    for dimension in shape:
        if type(dimension) is not int or dimension < 0:
            raise CanonicalizationError(
                "D02A_TENSOR_SHAPE_NONNEGATIVE_INTEGER_REQUIRED"
            )
        dimensions.append(dimension)
    element_count = math.prod(dimensions)
    if element_count > MAX_TENSOR_ELEMENTS:
        raise CanonicalizationError(
            "D02A_TENSOR_ELEMENT_BUDGET_EXCEEDED"
        )
    return element_count


def _pack_tensor_values(
    tensor: CanonicalTensor,
) -> tuple[_DTypeSpec, bytes]:
    spec = _DTYPE_SPECS.get(tensor.dtype)
    if spec is None or tensor.dtype != spec.descriptor:
        raise CanonicalizationError(
            "D02A_TENSOR_DTYPE_UNSUPPORTED:" + tensor.dtype
        )
    element_count = _validate_shape(tensor.shape)
    if len(tensor.values) != element_count:
        raise CanonicalizationError(
            "D02A_TENSOR_SHAPE_VALUE_COUNT_MISMATCH"
        )
    packer = struct.Struct("<" + spec.struct_code)
    output = bytearray()
    for index, value in enumerate(tensor.values):
        if spec.kind == "bool":
            if type(value) is not bool:
                raise CanonicalizationError(
                    "D02A_TENSOR_BOOL_VALUE_REQUIRED:"
                    + str(index)
                )
            packed_value: bool | int | float = value
        elif spec.kind == "int":
            if type(value) is not int:
                raise CanonicalizationError(
                    "D02A_TENSOR_INTEGER_VALUE_REQUIRED:"
                    + str(index)
                )
            integer = value
            if (
                spec.minimum is None
                or spec.maximum is None
                or not spec.minimum <= integer <= spec.maximum
            ):
                raise CanonicalizationError(
                    "D02A_TENSOR_INTEGER_OUT_OF_RANGE:"
                    + str(index)
                )
            packed_value = integer
        else:
            if type(value) is not float:
                raise CanonicalizationError(
                    "D02A_TENSOR_FLOAT_VALUE_REQUIRED:"
                    + str(index)
                )
            numeric = value
            if not math.isfinite(numeric):
                raise CanonicalizationError(
                    "D02A_TENSOR_NONFINITE_VALUE_FORBIDDEN:"
                    + str(index)
                )
            packed_value = 0.0 if numeric == 0.0 else numeric
        try:
            encoded = packer.pack(packed_value)
        except (OverflowError, struct.error) as exc:
            raise CanonicalizationError(
                "D02A_TENSOR_VALUE_NOT_REPRESENTABLE:"
                + str(index)
            ) from exc
        if spec.kind == "float":
            decoded = cast(float, packer.unpack(encoded)[0])
            if not math.isfinite(decoded):
                raise CanonicalizationError(
                    "D02A_TENSOR_VALUE_NOT_FINITE_AFTER_ENCODING:"
                    + str(index)
                )
        output.extend(encoded)
    return spec, bytes(output)


def _shape_literal(shape: tuple[int, ...]) -> str:
    if not shape:
        return "()"
    if len(shape) == 1:
        return "(" + str(shape[0]) + ",)"
    return "(" + ", ".join(str(item) for item in shape) + ")"


def canonical_npy_bytes(tensor: CanonicalTensor) -> bytes:
    """Encode one tensor as deterministic, valid NPY v1.0 bytes."""

    spec, data = _pack_tensor_values(tensor)
    header_text = (
        "{'descr': '"
        + spec.descriptor
        + "', 'fortran_order': False, 'shape': "
        + _shape_literal(tensor.shape)
        + ", }"
    )
    header = header_text.encode("latin-1")
    fixed_prefix_size = len(_NPY_MAGIC) + len(_NPY_VERSION_BYTES) + 2
    padding_size = (
        -((fixed_prefix_size + len(header) + 1) % NPY_HEADER_ALIGNMENT)
    ) % NPY_HEADER_ALIGNMENT
    padded_header = header + (b" " * padding_size) + b"\n"
    if len(padded_header) > 0xFFFF:
        raise CanonicalizationError("D02A_NPY_V1_HEADER_TOO_LARGE")
    return (
        _NPY_MAGIC
        + _NPY_VERSION_BYTES
        + struct.pack("<H", len(padded_header))
        + padded_header
        + data
    )


def _normalize_tensor_name(name: str) -> str:
    if not isinstance(name, str):
        raise TypeError("D02A_TENSOR_NAME_STRING_REQUIRED")
    normalized = _nfc(name)
    if (
        not _TENSOR_NAME_RE.fullmatch(normalized)
        or normalized.endswith(".npy")
    ):
        raise CanonicalizationError(
            "D02A_TENSOR_NAME_INVALID:" + normalized
        )
    return normalized


def _normalize_tensors(
    tensors: Mapping[str, CanonicalTensor],
) -> dict[str, CanonicalTensor]:
    if not tensors:
        raise CanonicalizationError("D02A_NPZ_TENSOR_REQUIRED")
    normalized: dict[str, CanonicalTensor] = {}
    source_names: dict[str, str] = {}
    for source_name, tensor in tensors.items():
        name = _normalize_tensor_name(source_name)
        if not isinstance(tensor, CanonicalTensor):
            raise TypeError("D02A_CANONICAL_TENSOR_REQUIRED:" + name)
        if name in normalized:
            raise CanonicalizationError(
                "D02A_TENSOR_NAME_NFC_COLLISION:"
                + source_names[name]
                + ":"
                + source_name
            )
        source_names[name] = source_name
        normalized[name] = tensor
    return normalized


def build_canonical_npz(
    tensors: Mapping[str, CanonicalTensor],
) -> bytes:
    """Build a canonical NPZ as sorted canonical NPY members in canonical ZIP."""

    normalized = _normalize_tensors(tensors)
    members = {
        name + ".npy": canonical_npy_bytes(normalized[name])
        for name in sorted(
            normalized,
            key=lambda item: item.encode("utf-8"),
        )
    }
    return build_canonical_zip(members)


def canonical_npz_logical_value(
    tensors: Mapping[str, CanonicalTensor],
) -> dict[str, JsonValue]:
    """Return package-metadata-independent logical tensor content."""

    normalized = _normalize_tensors(tensors)
    records: list[JsonValue] = []
    for name in sorted(
        normalized,
        key=lambda item: item.encode("utf-8"),
    ):
        tensor = normalized[name]
        _spec, data = _pack_tensor_values(tensor)
        records.append(
            {
                "data_sha256": hashlib.sha256(data).hexdigest(),
                "dtype": tensor.dtype,
                "element_count": len(tensor.values),
                "name": name,
                "shape": list(tensor.shape),
            }
        )
    return {
        "canonical_npy_version": CANONICAL_NPY_VERSION,
        "canonical_npz_version": CANONICAL_NPZ_VERSION,
        "tensor_count": len(records),
        "tensors": records,
    }


def canonical_npz_digests(
    tensors: Mapping[str, CanonicalTensor],
) -> CanonicalPackageDigests:
    """Build and digest canonical NPZ logical content and exact bytes."""

    logical_value = canonical_npz_logical_value(tensors)
    payload = build_canonical_npz(tensors)
    return digest_canonical_package(
        logical_namespace="hds-canonical-npz-logical",
        physical_namespace="hds-canonical-npz-physical",
        logical_value=cast(Mapping[str, object], logical_value),
        package_payload=payload,
        policy=DigestExclusionPolicy(),
    )


def raw_trajectory_digest(raw_payload: bytes) -> str:
    """Digest exact raw trajectory bytes without canonical interpretation."""

    if not isinstance(raw_payload, bytes):
        raise TypeError("D02A_RAW_TRAJECTORY_BYTES_REQUIRED")
    return _domain_hash(
        RAW_TRAJECTORY_DIGEST_DOMAIN,
        "hds-raw-trajectory",
        raw_payload,
    )


def canonical_trajectory_digest(
    canonical_record: Mapping[str, object],
    *,
    policy: DigestExclusionPolicy,
    unordered_paths: Iterable[str] = (),
) -> str:
    """Digest a separately supplied canonical trajectory record."""

    body = logical_digest_body(
        canonical_record,
        policy=policy,
        unordered_paths=unordered_paths,
    )
    return _domain_hash(
        CANONICAL_TRAJECTORY_DIGEST_DOMAIN,
        "hds-canonical-trajectory",
        canonical_json_bytes(body),
    )


@dataclass(frozen=True, slots=True)
class TrajectoryDigestPair:
    raw_trajectory_digest: str
    canonical_trajectory_digest: str

    def as_json(self) -> dict[str, JsonValue]:
        return {
            "canonical_trajectory_digest": (
                self.canonical_trajectory_digest
            ),
            "raw_trajectory_digest": self.raw_trajectory_digest,
        }


def bind_trajectory_digests(
    *,
    raw_payload: bytes,
    canonical_record: Mapping[str, object],
    policy: DigestExclusionPolicy,
    unordered_paths: Iterable[str] = (),
) -> TrajectoryDigestPair:
    """Bind, but never conflate, raw-byte and canonical-record identities."""

    return TrajectoryDigestPair(
        raw_trajectory_digest=raw_trajectory_digest(raw_payload),
        canonical_trajectory_digest=canonical_trajectory_digest(
            canonical_record,
            policy=policy,
            unordered_paths=unordered_paths,
        ),
    )


__all__ = [
    "CANONICAL_CONTRACT_VERSION",
    "CANONICAL_JSON_VERSION",
    "CANONICAL_NPY_VERSION",
    "CANONICAL_NPZ_VERSION",
    "CANONICAL_ZIP_VERSION",
    "FIXED_ZIP_CREATE_SYSTEM",
    "FIXED_ZIP_EXTERNAL_ATTR",
    "FIXED_ZIP_TIMESTAMP",
    "FIXED_ZIP_VERSION",
    "NPY_HEADER_ALIGNMENT",
    "CanonicalPackageDigests",
    "CanonicalTensor",
    "CanonicalizationError",
    "DigestExclusionPolicy",
    "JsonValue",
    "TrajectoryDigestPair",
    "bind_trajectory_digests",
    "build_canonical_npz",
    "build_canonical_zip",
    "canonical_json",
    "canonical_json_bytes",
    "canonical_npy_bytes",
    "canonical_npz_digests",
    "canonical_npz_logical_value",
    "canonical_trajectory_digest",
    "canonicalize",
    "content_derived_id",
    "digest_canonical_package",
    "logical_content_digest",
    "logical_digest_body",
    "normalize_repository_relative_posix_path",
    "parse_json_strict",
    "physical_package_digest",
    "raw_trajectory_digest",
    "validate_confidence_ppm",
    "verify_canonical_json_bytes",
    "verify_canonical_zip",
]
