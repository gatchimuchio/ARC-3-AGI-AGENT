from __future__ import annotations

import ast
import hashlib
import io
import json
import math
import os
import struct
import subprocess
import sys
import zipfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import pytest

from hds_distill.canonical import (
    CANONICAL_NPY_VERSION,
    CANONICAL_NPZ_VERSION,
    FIXED_ZIP_CREATE_SYSTEM,
    FIXED_ZIP_EXTERNAL_ATTR,
    FIXED_ZIP_TIMESTAMP,
    FIXED_ZIP_VERSION,
    NPY_HEADER_ALIGNMENT,
    CanonicalizationError,
    CanonicalTensor,
    DigestExclusionPolicy,
    bind_trajectory_digests,
    build_canonical_npz,
    build_canonical_zip,
    canonical_json,
    canonical_json_bytes,
    canonical_npy_bytes,
    canonical_npz_digests,
    canonical_npz_logical_value,
    canonical_trajectory_digest,
    canonicalize,
    content_derived_id,
    digest_canonical_package,
    logical_content_digest,
    logical_digest_body,
    normalize_repository_relative_posix_path,
    parse_json_strict,
    physical_package_digest,
    raw_trajectory_digest,
    validate_confidence_ppm,
    verify_canonical_json_bytes,
    verify_canonical_zip,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DISTILLATION_SOURCE = REPOSITORY_ROOT / "distillation" / "src"
CONTRACT_PATH = (
    REPOSITORY_ROOT
    / "distillation"
    / "input"
    / "canonicalization_contract.json"
)
TEST_VECTOR_ROOT = (
    REPOSITORY_ROOT / "distillation" / "artifacts" / "test_vectors"
)
CONFORMANCE_REPORT_PATH = (
    REPOSITORY_ROOT
    / "distillation"
    / "artifacts"
    / "reports"
    / "canonicalization_conformance.json"
)


def _policy() -> DigestExclusionPolicy:
    return DigestExclusionPolicy(
        id_fields=frozenset({"artifact_id"}),
        digest_fields=frozenset({"content_digest"}),
        timestamp_fields=frozenset({"created_at"}),
        physical_metadata_fields=frozenset({"local_path"}),
    )


def _logical_fixture(variant: int = 0) -> dict[str, object]:
    unordered = [
        {"name": "beta", "rank": 2},
        {"name": "alpha", "rank": 1},
        {"name": "cafe\u0301", "rank": 3},
    ]
    if variant % 2:
        unordered.reverse()
    entries: list[tuple[str, object]] = [
        ("artifact_id", "artifact-" + str(variant)),
        ("content_digest", "stale:" + str(variant)),
        ("created_at", f"2026-07-30T00:00:0{variant}Z"),
        ("local_path", f"C:/different/root/{variant}/artifact.json"),
        ("title", "Cafe\u0301"),
        ("confidence_ppm", 875_000),
        ("ordered", ["second", "first"]),
        ("unordered", unordered),
        ("tags", {"zeta", "alpha", "e\u0301"}),
        (
            "provenance",
            {
                "source_id": "source-stays-bound",
                "source_digest": "source-sha256:bound",
            },
        ),
    ]
    if variant % 2:
        entries.reverse()
    return dict(entries)


def _tensors(variant: int = 0) -> dict[str, CanonicalTensor]:
    entries = [
        (
            "pixels",
            CanonicalTensor.from_values(
                dtype="|u1",
                shape=(2, 3),
                values=(0, 1, 2, 3, 4, 255),
            ),
        ),
        (
            "scores",
            CanonicalTensor.from_values(
                dtype="<f4",
                shape=(2,),
                values=(0.0, 1.5),
            ),
        ),
        (
            "valid",
            CanonicalTensor.from_values(
                dtype="|b1",
                shape=(3,),
                values=(True, False, True),
            ),
        ),
    ]
    if variant % 2:
        entries.reverse()
    return dict(entries)


def _npy_header(payload: bytes) -> tuple[dict[str, object], bytes]:
    assert payload[:6] == b"\x93NUMPY"
    assert payload[6:8] == b"\x01\x00"
    header_length = struct.unpack("<H", payload[8:10])[0]
    header_end = 10 + header_length
    assert header_end % NPY_HEADER_ALIGNMENT == 0
    header = payload[10:header_end]
    assert header.endswith(b"\n")
    value = ast.literal_eval(header.decode("latin-1").strip())
    assert isinstance(value, dict)
    return cast(dict[str, object], value), payload[header_end:]


def test_canonical_json_normalizes_nfc_keys_values_sets_and_selected_arrays(
) -> None:
    value = {
        "z": 1,
        "e\u0301": "Cafe\u0301",
        "set": {"beta", "alpha", "e\u0301"},
        "unordered": [{"v": 2}, {"v": 1}],
        "ordered": [{"v": 2}, {"v": 1}],
    }

    normalized = canonicalize(
        value,
        unordered_paths=("/unordered",),
    )

    assert normalized == {
        "z": 1,
        "é": "Café",
        "set": ["alpha", "beta", "é"],
        "unordered": [{"v": 1}, {"v": 2}],
        "ordered": [{"v": 2}, {"v": 1}],
    }
    assert canonical_json(
        value,
        unordered_paths=("/unordered",),
    ) == (
        '{"ordered":[{"v":2},{"v":1}],"set":["alpha","beta","é"],'
        '"unordered":[{"v":1},{"v":2}],"z":1,"é":"Café"}'
    )


def test_unordered_array_pointer_must_resolve_and_ordered_arrays_stay_ordered(
) -> None:
    assert canonical_json({"items": [2, 1]}) == '{"items":[2,1]}'
    assert canonical_json(
        {"items": [2, 1]},
        unordered_paths=("/items",),
    ) == '{"items":[1,2]}'
    with pytest.raises(
        CanonicalizationError,
        match="D02A_UNORDERED_POINTER_NOT_ARRAY",
    ):
        canonical_json({"items": [2, 1]}, unordered_paths=("/missing",))
    with pytest.raises(
        CanonicalizationError,
        match="D02A_UNORDERED_POINTER_INVALID",
    ):
        canonical_json({"items": []}, unordered_paths=("items",))


def test_nested_unordered_array_uses_wildcard_descendant_pointer() -> None:
    value = {
        "groups": [
            {"members": [3, 1]},
            {"members": [4, 2]},
        ]
    }

    assert canonicalize(
        value,
        unordered_paths=("/groups", "/groups/*/members"),
    ) == {
        "groups": [
            {"members": [1, 3]},
            {"members": [2, 4]},
        ]
    }


def test_nfc_key_collision_and_non_string_keys_fail_closed() -> None:
    with pytest.raises(
        CanonicalizationError,
        match="D02A_NFC_KEY_COLLISION",
    ):
        canonical_json({"é": 1, "e\u0301": 2})
    with pytest.raises(
        CanonicalizationError,
        match="D02A_OBJECT_KEY_STRING_REQUIRED",
    ):
        canonical_json({1: "coercion-forbidden"})


@pytest.mark.parametrize(
    "value",
    [float("nan"), float("inf"), float("-inf")],
)
def test_nonfinite_json_numbers_are_rejected(value: float) -> None:
    with pytest.raises(
        CanonicalizationError,
        match="D02A_NONFINITE_NUMBER_FORBIDDEN",
    ):
        canonical_json({"value": value})


def test_unsupported_json_types_and_negative_zero_are_canonical() -> None:
    with pytest.raises(
        CanonicalizationError,
        match="D02A_UNSUPPORTED_JSON_VALUE",
    ):
        canonical_json({"payload": b"bytes-are-not-json"})
    assert canonical_json({"minus_zero": -0.0}) == '{"minus_zero":0.0}'


def test_strict_json_parser_and_verifier_reject_noncanonical_bytes() -> None:
    payload = '{"x":1,"é":"Café"}'.encode()
    assert verify_canonical_json_bytes(payload) == {"é": "Café", "x": 1}
    assert parse_json_strict(payload) == {"é": "Café", "x": 1}

    for invalid, code in (
        (b'{"x":1,"x":2}', "D02A_DUPLICATE_JSON_KEY"),
        (b'{"x":NaN}', "D02A_NONFINITE_JSON_TOKEN_FORBIDDEN"),
        (b"\xef\xbb\xbf{}", "D02A_UTF8_BOM_FORBIDDEN"),
        (b"\xff", "D02A_JSON_UTF8_INVALID"),
    ):
        with pytest.raises(CanonicalizationError, match=code):
            parse_json_strict(invalid)
    with pytest.raises(
        CanonicalizationError,
        match="D02A_JSON_NOT_CANONICAL",
    ):
        verify_canonical_json_bytes(b'{ "x": 1 }')


@pytest.mark.parametrize("value", [0, 1, 875_000, 1_000_000])
def test_confidence_ppm_accepts_only_bounded_non_bool_integers(
    value: int,
) -> None:
    assert validate_confidence_ppm(value) == value
    assert canonical_json({"confidence_ppm": value})


@pytest.mark.parametrize(
    "value",
    [True, False, -1, 1_000_001, 0.5, "875000"],
)
def test_invalid_confidence_ppm_and_legacy_confidence_fail(
    value: object,
) -> None:
    with pytest.raises(CanonicalizationError):
        canonical_json({"confidence_ppm": value})
    with pytest.raises(
        CanonicalizationError,
        match="D02A_LEGACY_CONFIDENCE_FIELD_FORBIDDEN",
    ):
        canonical_json({"confidence": 0.875})


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("dir/file.json", "dir/file.json"),
        ("unicode/cafe\u0301.txt", "unicode/café.txt"),
        ("one", "one"),
    ],
)
def test_repository_relative_posix_path_contract(
    source: str,
    expected: str,
) -> None:
    assert normalize_repository_relative_posix_path(source) == expected


@pytest.mark.parametrize(
    "path",
    [
        "",
        "/absolute",
        "C:/drive",
        "a\\b",
        "a/../b",
        "a/./b",
        "a//b",
        "a/",
        "a\x00b",
    ],
)
def test_invalid_repository_paths_fail_closed(path: str) -> None:
    with pytest.raises(
        CanonicalizationError,
        match="D02A_RELATIVE_POSIX_PATH_INVALID",
    ):
        normalize_repository_relative_posix_path(path)


def test_explicit_digest_exclusions_preserve_nested_provenance() -> None:
    first = _logical_fixture(0)
    second = _logical_fixture(1)

    first_body = logical_digest_body(
        first,
        policy=_policy(),
        unordered_paths=("/unordered",),
    )
    second_body = logical_digest_body(
        second,
        policy=_policy(),
        unordered_paths=("/unordered",),
    )

    assert first_body == second_body
    assert set(first_body) == {
        "confidence_ppm",
        "ordered",
        "provenance",
        "tags",
        "title",
        "unordered",
    }
    assert first_body["provenance"] == {
        "source_digest": "source-sha256:bound",
        "source_id": "source-stays-bound",
    }
    assert logical_content_digest(
        "hds-test-logical",
        first,
        policy=_policy(),
        unordered_paths=("/unordered",),
    ) == logical_content_digest(
        "hds-test-logical",
        second,
        policy=_policy(),
        unordered_paths=("/unordered",),
    )
    assert content_derived_id(
        "hds-test-id",
        first,
        policy=_policy(),
        unordered_paths=("/unordered",),
    ) == content_derived_id(
        "hds-test-id",
        second,
        policy=_policy(),
        unordered_paths=("/unordered",),
    )

    changed = _logical_fixture(0)
    changed["provenance"] = {
        "source_digest": "source-sha256:changed",
        "source_id": "source-stays-bound",
    }
    assert logical_content_digest(
        "hds-test-logical",
        changed,
        policy=_policy(),
        unordered_paths=("/unordered",),
    ) != logical_content_digest(
        "hds-test-logical",
        first,
        policy=_policy(),
        unordered_paths=("/unordered",),
    )


def test_content_id_and_logical_digest_have_distinct_domains() -> None:
    value = _logical_fixture()
    logical = logical_content_digest(
        "hds-test",
        value,
        policy=_policy(),
        unordered_paths=("/unordered",),
    )
    identifier = content_derived_id(
        "hds-test",
        value,
        policy=_policy(),
        unordered_paths=("/unordered",),
    )

    assert logical != identifier
    assert logical.split(":", 1)[0] == identifier.split(":", 1)[0]
    assert len(logical.split(":", 1)[1]) == 64
    assert len(identifier.split(":", 1)[1]) == 64


def test_digest_exclusion_policy_is_explicit_top_level_and_disjoint() -> None:
    with pytest.raises(
        CanonicalizationError,
        match="D02A_DIGEST_EXCLUSION_CATEGORY_OVERLAP",
    ):
        DigestExclusionPolicy(
            id_fields=frozenset({"same"}),
            digest_fields=frozenset({"same"}),
        )
    with pytest.raises(
        CanonicalizationError,
        match="D02A_DIGEST_EXCLUSION_TOP_LEVEL_ONLY",
    ):
        DigestExclusionPolicy(
            id_fields=frozenset({"nested/id"}),
        )


def test_logical_and_physical_package_digests_are_not_substitutable() -> None:
    logical_value = _logical_fixture()
    package = build_canonical_zip({"manifest.json": b"{}"})
    digests = digest_canonical_package(
        logical_namespace="hds-test-logical",
        physical_namespace="hds-test-physical",
        logical_value=logical_value,
        package_payload=package,
        policy=_policy(),
        unordered_paths=("/unordered",),
    )

    assert digests.logical_content_digest.startswith("hds-test-logical:")
    assert digests.physical_package_digest.startswith(
        "hds-test-physical:"
    )
    assert digests.logical_content_digest != digests.physical_package_digest
    assert physical_package_digest("hds-test-physical", package) == (
        digests.physical_package_digest
    )


def test_canonical_zip_normalizes_names_order_and_metadata() -> None:
    first = build_canonical_zip(
        {
            "z-last.bin": b"\x00\x01",
            "unicode/cafe\u0301.txt": "Café\n".encode(),
            "a-first.json": b"{}",
        }
    )
    second = build_canonical_zip(
        {
            "a-first.json": b"{}",
            "unicode/café.txt": "Café\n".encode(),
            "z-last.bin": b"\x00\x01",
        }
    )

    assert first == second
    members = verify_canonical_zip(first)
    assert list(members) == [
        "a-first.json",
        "unicode/café.txt",
        "z-last.bin",
    ]
    with zipfile.ZipFile(io.BytesIO(first), "r") as archive:
        for info in archive.infolist():
            assert info.date_time == FIXED_ZIP_TIMESTAMP
            assert info.compress_type == zipfile.ZIP_STORED
            assert info.create_system == FIXED_ZIP_CREATE_SYSTEM
            assert info.create_version == FIXED_ZIP_VERSION
            assert info.extract_version == FIXED_ZIP_VERSION
            assert info.external_attr == FIXED_ZIP_EXTERNAL_ATTR
            assert info.internal_attr == 0
            assert info.extra == b""
            assert info.comment == b""


def test_canonical_zip_rejects_invalid_names_collisions_and_payloads() -> None:
    with pytest.raises(
        CanonicalizationError,
        match="D02A_ZIP_MEMBER_NFC_COLLISION",
    ):
        build_canonical_zip({"é.txt": b"1", "e\u0301.txt": b"2"})
    with pytest.raises(
        CanonicalizationError,
        match="D02A_RELATIVE_POSIX_PATH_INVALID",
    ):
        build_canonical_zip({"../escape": b"x"})
    with pytest.raises(TypeError, match="D02A_ZIP_MEMBER_BYTES_REQUIRED"):
        build_canonical_zip(cast(Mapping[str, bytes], {"x": "not-bytes"}))


def test_zip_with_noncanonical_timestamp_is_rejected() -> None:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        info = zipfile.ZipInfo("x", date_time=(2026, 7, 30, 0, 0, 0))
        info.compress_type = zipfile.ZIP_STORED
        info.create_system = FIXED_ZIP_CREATE_SYSTEM
        info.external_attr = FIXED_ZIP_EXTERNAL_ATTR
        archive.writestr(info, b"x")
    with pytest.raises(
        CanonicalizationError,
        match="D02A_ZIP_TIMESTAMP_INVALID",
    ):
        verify_canonical_zip(output.getvalue())


@pytest.mark.parametrize(
    ("dtype", "shape", "values", "expected_data"),
    [
        ("|b1", (3,), (True, False, True), b"\x01\x00\x01"),
        ("|i1", (2,), (-128, 127), b"\x80\x7f"),
        ("|u1", (2,), (0, 255), b"\x00\xff"),
        ("<i2", (2,), (-2, 258), struct.pack("<hh", -2, 258)),
        ("<u2", (2,), (0, 65535), struct.pack("<HH", 0, 65535)),
        ("<i4", (1,), (-123456,), struct.pack("<i", -123456)),
        ("<u4", (1,), (4_000_000_000,), struct.pack("<I", 4_000_000_000)),
        ("<i8", (1,), (-(2**62),), struct.pack("<q", -(2**62))),
        ("<u8", (1,), (2**63,), struct.pack("<Q", 2**63)),
        ("<f2", (1,), (1.5,), struct.pack("<e", 1.5)),
        ("<f4", (1,), (1.5,), struct.pack("<f", 1.5)),
        ("<f8", (1,), (1.5,), struct.pack("<d", 1.5)),
    ],
)
def test_canonical_npy_fixes_dtype_endian_shape_and_data(
    dtype: str,
    shape: tuple[int, ...],
    values: tuple[bool | int | float, ...],
    expected_data: bytes,
) -> None:
    tensor = CanonicalTensor(dtype=dtype, shape=shape, values=values)
    payload = canonical_npy_bytes(tensor)
    header, data = _npy_header(payload)

    assert header == {
        "descr": dtype,
        "fortran_order": False,
        "shape": shape,
    }
    assert data == expected_data


def test_canonical_npy_supports_scalar_and_empty_shapes() -> None:
    scalar = canonical_npy_bytes(
        CanonicalTensor(dtype="<i4", shape=(), values=(7,))
    )
    empty = canonical_npy_bytes(
        CanonicalTensor(dtype="<i4", shape=(0, 3), values=())
    )

    assert _npy_header(scalar)[0]["shape"] == ()
    assert _npy_header(empty)[0]["shape"] == (0, 3)
    assert _npy_header(empty)[1] == b""


@pytest.mark.parametrize(
    ("tensor", "code"),
    [
        (
            CanonicalTensor(dtype=">i4", shape=(1,), values=(1,)),
            "D02A_TENSOR_DTYPE_UNSUPPORTED",
        ),
        (
            CanonicalTensor(dtype="<i4", shape=(2,), values=(1,)),
            "D02A_TENSOR_SHAPE_VALUE_COUNT_MISMATCH",
        ),
        (
            CanonicalTensor(dtype="|u1", shape=(1,), values=(256,)),
            "D02A_TENSOR_INTEGER_OUT_OF_RANGE",
        ),
        (
            CanonicalTensor(dtype="|u1", shape=(1,), values=(True,)),
            "D02A_TENSOR_INTEGER_VALUE_REQUIRED",
        ),
        (
            CanonicalTensor(dtype="|b1", shape=(1,), values=(1,)),
            "D02A_TENSOR_BOOL_VALUE_REQUIRED",
        ),
        (
            CanonicalTensor(dtype="<f4", shape=(1,), values=(1,)),
            "D02A_TENSOR_FLOAT_VALUE_REQUIRED",
        ),
        (
            CanonicalTensor(
                dtype="<f4",
                shape=(1,),
                values=(float("nan"),),
            ),
            "D02A_TENSOR_NONFINITE_VALUE_FORBIDDEN",
        ),
    ],
)
def test_invalid_tensor_contracts_fail_closed(
    tensor: CanonicalTensor,
    code: str,
) -> None:
    with pytest.raises(CanonicalizationError, match=code):
        canonical_npy_bytes(tensor)


def test_tensor_shape_rejects_bool_negative_and_resource_exhaustion() -> None:
    for shape, code in (
        ((True,), "D02A_TENSOR_SHAPE_NONNEGATIVE_INTEGER_REQUIRED"),
        ((-1,), "D02A_TENSOR_SHAPE_NONNEGATIVE_INTEGER_REQUIRED"),
        ((100_000_001,), "D02A_TENSOR_ELEMENT_BUDGET_EXCEEDED"),
    ):
        with pytest.raises(CanonicalizationError, match=code):
            canonical_npy_bytes(
                CanonicalTensor(
                    dtype="|u1",
                    shape=cast(tuple[int, ...], shape),
                    values=(),
                )
            )


def test_canonical_npz_is_order_independent_and_contains_sorted_npy_members(
) -> None:
    first = build_canonical_npz(_tensors(0))
    second = build_canonical_npz(_tensors(1))

    assert first == second
    members = verify_canonical_zip(first)
    assert list(members) == ["pixels.npy", "scores.npy", "valid.npy"]
    assert _npy_header(members["pixels.npy"])[0] == {
        "descr": "|u1",
        "fortran_order": False,
        "shape": (2, 3),
    }


def test_npz_logical_value_and_digests_exclude_archive_metadata() -> None:
    tensors = _tensors()
    logical_value = canonical_npz_logical_value(tensors)
    digests = canonical_npz_digests(tensors)

    assert logical_value["canonical_npy_version"] == CANONICAL_NPY_VERSION
    assert logical_value["canonical_npz_version"] == CANONICAL_NPZ_VERSION
    assert logical_value["tensor_count"] == 3
    assert digests.logical_content_digest.startswith(
        "hds-canonical-npz-logical:"
    )
    assert digests.physical_package_digest.startswith(
        "hds-canonical-npz-physical:"
    )
    assert digests.logical_content_digest != digests.physical_package_digest


def test_raw_and_canonical_trajectory_digests_are_separate_and_bound() -> None:
    raw = b'{"raw_action":"ACTION1","frame":[1,2]}'
    canonical_record: dict[str, object] = {
        "trajectory_id": "excluded",
        "content_digest": "excluded",
        "created_at": "excluded",
        "steps": [
            {"action": "ACTION1", "effect": "CHANGED"},
        ],
    }
    policy = DigestExclusionPolicy(
        id_fields=frozenset({"trajectory_id"}),
        digest_fields=frozenset({"content_digest"}),
        timestamp_fields=frozenset({"created_at"}),
    )
    pair = bind_trajectory_digests(
        raw_payload=raw,
        canonical_record=canonical_record,
        policy=policy,
    )

    assert pair.raw_trajectory_digest == raw_trajectory_digest(raw)
    assert pair.canonical_trajectory_digest == canonical_trajectory_digest(
        canonical_record,
        policy=policy,
    )
    assert pair.raw_trajectory_digest.startswith("hds-raw-trajectory:")
    assert pair.canonical_trajectory_digest.startswith(
        "hds-canonical-trajectory:"
    )
    assert pair.raw_trajectory_digest != pair.canonical_trajectory_digest
    assert raw_trajectory_digest(raw + b"\n") != pair.raw_trajectory_digest


def _subprocess_program() -> str:
    return """
import hashlib
import json
import os
import sys
from hds_distill.canonical import (
    CanonicalTensor,
    DigestExclusionPolicy,
    bind_trajectory_digests,
    build_canonical_npz,
    build_canonical_zip,
    canonical_json,
    canonical_json_bytes,
    content_derived_id,
    logical_content_digest,
    logical_digest_body,
    physical_package_digest,
)
variant = int(os.environ["D02A_VARIANT"])
unordered = [
    {"name": "beta", "rank": 2},
    {"name": "alpha", "rank": 1},
    {"name": "cafe\\u0301", "rank": 3},
]
if variant % 2:
    unordered.reverse()
entries = [
    ("artifact_id", "artifact-" + str(variant)),
    ("content_digest", "stale:" + str(variant)),
    ("created_at", "time-" + str(variant)),
    ("local_path", os.getcwd()),
    ("title", "Cafe\\u0301"),
    ("confidence_ppm", 875000),
    ("ordered", ["second", "first"]),
    ("unordered", unordered),
    ("tags", {"zeta", "alpha", "e\\u0301"}),
    ("provenance", {
        "source_id": "source-stays-bound",
        "source_digest": "source-sha256:bound",
    }),
]
if variant % 2:
    entries.reverse()
value = dict(entries)
policy = DigestExclusionPolicy(
    id_fields=frozenset({"artifact_id"}),
    digest_fields=frozenset({"content_digest"}),
    timestamp_fields=frozenset({"created_at"}),
    physical_metadata_fields=frozenset({"local_path"}),
)
body = logical_digest_body(
    value,
    policy=policy,
    unordered_paths=("/unordered",),
)
body_bytes = canonical_json_bytes(body)
zip_entries = [
    ("z-last.bin", b"\\x00\\x01"),
    ("unicode/cafe\\u0301.txt", "Cafe\\u0301\\n".encode()),
    ("manifest.json", body_bytes),
]
if variant % 2:
    zip_entries.reverse()
zip_payload = build_canonical_zip(dict(zip_entries))
tensors = [
    ("pixels", CanonicalTensor.from_values(
        dtype="|u1", shape=(2, 3), values=(0, 1, 2, 3, 4, 255)
    )),
    ("scores", CanonicalTensor.from_values(
        dtype="<f4", shape=(2,), values=(0.0, 1.5)
    )),
    ("valid", CanonicalTensor.from_values(
        dtype="|b1", shape=(3,), values=(True, False, True)
    )),
]
if variant % 2:
    tensors.reverse()
npz_payload = build_canonical_npz(dict(tensors))
trajectory = bind_trajectory_digests(
    raw_payload=b'{"raw_action":"ACTION1","frame":[1,2]}',
    canonical_record={
        "trajectory_id": "var-" + str(variant),
        "created_at": "time-" + str(variant),
        "steps": [{"action": "ACTION1", "effect": "CHANGED"}],
    },
    policy=DigestExclusionPolicy(
        id_fields=frozenset({"trajectory_id"}),
        timestamp_fields=frozenset({"created_at"}),
    ),
)
result = {
    "body": body,
    "body_sha256": hashlib.sha256(body_bytes).hexdigest(),
    "content_id": content_derived_id(
        "hds-test-id",
        value,
        policy=policy,
        unordered_paths=("/unordered",),
    ),
    "logical_digest": logical_content_digest(
        "hds-test-logical",
        value,
        policy=policy,
        unordered_paths=("/unordered",),
    ),
    "npz_physical_digest": physical_package_digest(
        "hds-test-npz-physical", npz_payload
    ),
    "npz_sha256": hashlib.sha256(npz_payload).hexdigest(),
    "trajectory": trajectory.as_json(),
    "zip_physical_digest": physical_package_digest(
        "hds-test-zip-physical", zip_payload
    ),
    "zip_sha256": hashlib.sha256(zip_payload).hexdigest(),
}
sys.stdout.buffer.write(canonical_json(result).encode() + b"\\n")
"""


def test_three_independent_process_path_time_order_and_hash_seed_rebuilds_match(
    tmp_path: Path,
) -> None:
    outputs: list[bytes] = []
    for variant, hash_seed in enumerate(("1", "17", "937")):
        working_directory = tmp_path / f"path-{variant}"
        working_directory.mkdir()
        environment = dict(os.environ)
        environment.update(
            {
                "D02A_VARIANT": str(variant),
                "PYTHONHASHSEED": hash_seed,
                "PYTHONPATH": str(DISTILLATION_SOURCE),
            }
        )
        result = subprocess.run(
            [sys.executable, "-c", _subprocess_program()],
            cwd=working_directory,
            env=environment,
            check=True,
            capture_output=True,
        )
        outputs.append(result.stdout)

    assert outputs[0] == outputs[1] == outputs[2]
    parsed = cast(dict[str, Any], json.loads(outputs[0]))
    assert parsed["body"]["title"] == "Café"
    assert len(cast(str, parsed["logical_digest"]).split(":", 1)[1]) == 64
    assert parsed["npz_sha256"] != parsed["zip_sha256"]
    assert parsed["trajectory"]["raw_trajectory_digest"] != (
        parsed["trajectory"]["canonical_trajectory_digest"]
    )


def test_checked_contract_is_canonical_content_bound_and_phase_limited(
) -> None:
    payload = CONTRACT_PATH.read_bytes()
    contract = cast(dict[str, Any], verify_canonical_json_bytes(payload))
    claimed = cast(str, contract["content_digest"])

    assert hashlib.sha256(payload).hexdigest() == (
        "24475a34959e7c380afa404700f2f8b7eb5ccc0f12dda404b54506479bcedcaa"
    )
    assert claimed == (
        "hds-canonicalization-contract:"
        "bd37cc6aa0f41021448a83358c9db409b3695cdf88b2eb6ab6eec0068c137257"
    )
    assert claimed == logical_content_digest(
        "hds-canonicalization-contract",
        contract,
        policy=DigestExclusionPolicy(
            id_fields=frozenset({"contract_id"}),
            digest_fields=frozenset({"content_digest"}),
        ),
    )
    assert contract["gates"] == ["DG-06", "DG-07"]
    boundaries = cast(dict[str, Any], contract["phase_boundaries"])
    assert boundaries["ph_d02b_schema_count"] == 0
    assert boundaries["causal_ir_started"] is False
    assert boundaries["trajectory_normalization_started"] is False
    assert boundaries["rule_promotion_count"] == 0
    assert boundaries["official_access_count"] == 0
    assert boundaries["kaggle_mutation_count"] == 0


def test_checked_vectors_are_canonical_content_bound_and_rebuild_exactly(
) -> None:
    manifest_path = TEST_VECTOR_ROOT / "canonical_test_vectors.json"
    manifest_payload = manifest_path.read_bytes()
    manifest = cast(
        dict[str, Any],
        verify_canonical_json_bytes(manifest_payload),
    )
    claimed = cast(str, manifest["content_digest"])
    outputs = cast(dict[str, Any], manifest["outputs"])

    assert hashlib.sha256(manifest_payload).hexdigest() == (
        "9a09d700c4113b6474654215d757d4fbbbff569a9365e2c5e57c714328136e65"
    )
    assert claimed == (
        "hds-canonical-test-vectors:"
        "dfc146423c85b33fb7fb484dadeafb1d5071b0265bcdb0fa266fe413bc5e2f7b"
    )
    assert claimed == logical_content_digest(
        "hds-canonical-test-vectors",
        manifest,
        policy=DigestExclusionPolicy(
            id_fields=frozenset({"vector_set_id"}),
            digest_fields=frozenset({"content_digest"}),
        ),
    )

    body = logical_digest_body(
        _logical_fixture(),
        policy=_policy(),
        unordered_paths=("/unordered",),
    )
    json_payload = canonical_json_bytes(body)
    checked_json = TEST_VECTOR_ROOT / "canonical_json_v1.json"
    assert checked_json.read_bytes() == json_payload
    assert hashlib.sha256(json_payload).hexdigest() == (
        "7b0085437f032ee21ecf63130f6a05e37dcd4de085da1aed26c62d2a69965ead"
    )

    zip_payload = build_canonical_zip(
        {
            "z-last.bin": b"\x00\x01",
            "unicode/cafe\u0301.txt": "Cafe\u0301\n".encode(),
            "manifest.json": json_payload,
        }
    )
    checked_zip = TEST_VECTOR_ROOT / "canonical_zip_v1.zip"
    assert checked_zip.read_bytes() == zip_payload
    assert hashlib.sha256(zip_payload).hexdigest() == (
        "7cf212a5849e35987cd5f84aa0647aed176f5d6e43de97b08c685ad96aa2a94f"
    )

    npz_payload = build_canonical_npz(_tensors())
    checked_npz = TEST_VECTOR_ROOT / "canonical_npz_v1.npz"
    assert checked_npz.read_bytes() == npz_payload
    assert hashlib.sha256(npz_payload).hexdigest() == (
        "960bd58213db15d4dd761db47dc8a51d74da61fea41186f749e9a164000c6c82"
    )

    assert outputs["content_derived_id"] == content_derived_id(
        "hds-test-id",
        _logical_fixture(),
        policy=_policy(),
        unordered_paths=("/unordered",),
    )
    assert outputs["logical_content_digest"] == logical_content_digest(
        "hds-test-logical",
        _logical_fixture(),
        policy=_policy(),
        unordered_paths=("/unordered",),
    )
    assert cast(dict[str, Any], outputs["canonical_npz"])[
        "logical_content_digest"
    ] == canonical_npz_digests(_tensors()).logical_content_digest
    assert cast(dict[str, Any], outputs["canonical_npz"])[
        "physical_package_digest"
    ] == canonical_npz_digests(_tensors()).physical_package_digest


def test_checked_trajectory_vector_binds_raw_and_canonical_domains() -> None:
    manifest = cast(
        dict[str, Any],
        json.loads(
            (
                TEST_VECTOR_ROOT / "canonical_test_vectors.json"
            ).read_text(encoding="utf-8")
        ),
    )
    outputs = cast(dict[str, Any], manifest["outputs"])
    expected = cast(dict[str, str], outputs["trajectory_digests"])
    actual = bind_trajectory_digests(
        raw_payload=b'{"raw_action":"ACTION1","frame":[1,2]}',
        canonical_record={
            "trajectory_id": "trajectory-vector-0",
            "created_at": "2026-07-30T00:00:00Z",
            "steps": [{"action": "ACTION1", "effect": "CHANGED"}],
        },
        policy=DigestExclusionPolicy(
            id_fields=frozenset({"trajectory_id"}),
            timestamp_fields=frozenset({"created_at"}),
        ),
    )

    assert actual.as_json() == expected
    assert expected == {
        "canonical_trajectory_digest": (
            "hds-canonical-trajectory:"
            "7d2fb4c140b2c2d94c6d04025d7dacf2b5fab1e0194d1c41d3ab2392c20ae34a"
        ),
        "raw_trajectory_digest": (
            "hds-raw-trajectory:"
            "3a7f0fe2512b3237e3f96eb9a01e6f316e5ade0bf1e4ff7343afde2e9ac7fed3"
        ),
    }


def test_canonicalization_conformance_report_is_bound_and_claim_limited(
) -> None:
    payload = CONFORMANCE_REPORT_PATH.read_bytes()
    report = cast(dict[str, Any], verify_canonical_json_bytes(payload))
    claimed = cast(str, report["content_digest"])

    assert hashlib.sha256(payload).hexdigest() == (
        "353d6e78eb7574991c30cf48d5176ef1ec0bb7163dba8cdb7fa3a71855e34b2b"
    )
    assert claimed == (
        "hds-canonicalization-conformance:"
        "d24906ab3b99f8d70bdfd2942f38a69454fa11e926fd1d0288b26b4bda68c7f2"
    )
    assert claimed == logical_content_digest(
        "hds-canonicalization-conformance",
        report,
        policy=DigestExclusionPolicy(
            id_fields=frozenset({"report_id"}),
            digest_fields=frozenset({"content_digest"}),
        ),
    )
    assert report["status"] == "CODEX_IMPLEMENTATION_VALIDATED"
    assert report["gates"] == {"DG-06": "PASS", "DG-07": "PASS"}
    assert report["active_failure_count"] == 0
    determinism = cast(dict[str, Any], report["determinism"])
    assert determinism["independent_process_rebuild_count"] == 3
    assert determinism["byte_identical"] is True
    validation = cast(dict[str, Any], report["validation"])
    assert validation["dedicated_canonical"]["failed"] == 0
    assert validation["distillation_full"]["failed"] == 0
    assert validation["scope_guard"]["finding_count"] == 0
    boundaries = cast(dict[str, Any], report["phase_boundaries"])
    assert boundaries["ph_d02b_schema_count"] == 0
    assert boundaries["causal_ir_started"] is False
    assert boundaries["trajectory_normalization_started"] is False
    assert boundaries["rule_promotion_count"] == 0
    assert boundaries["official_access_count"] == 0
    assert boundaries["kaggle_mutation_count"] == 0
    assert "PH_D02A_CANONICAL_CONTRACT_PASS" in report["claim_allowed"]
    assert "DISTILLATION_IR_EXECUTABLE" in report["claim_prohibited"]
    assert "AGI" in report["claim_prohibited"]


def test_ph_d01b_frozen_artifacts_outside_declared_d02a_docs_are_unchanged(
) -> None:
    manifest_path = (
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "PH-D01B_OWNER_REVIEW_PACKAGE"
        / "artifact_manifest.json"
    )
    manifest = cast(
        dict[str, Any],
        json.loads(manifest_path.read_text(encoding="utf-8")),
    )
    mutable_in_d02a = {
        "ARC-AGI-3-Agents/tests/unit/test_rev3_strategy_rebaseline.py",
        "distillation/README.md",
        "distillation/artifacts/reports/distillation_scope_audit.json",
        "distillation/input/README.md",
        "distillation/schemas/README.md",
        "distillation/src/hds_distill/__init__.py",
    }
    checked = 0
    for artifact_value in cast(list[object], manifest["artifacts"]):
        artifact = cast(dict[str, Any], artifact_value)
        relative_path = cast(str, artifact["path"])
        if relative_path in mutable_in_d02a:
            continue
        payload = (REPOSITORY_ROOT / relative_path).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == artifact["sha256"]
        checked += 1

    assert checked == 40


def test_canonical_hashes_are_full_width_sha256() -> None:
    value = _logical_fixture()
    logical = logical_content_digest(
        "hds-test-logical",
        value,
        policy=_policy(),
        unordered_paths=("/unordered",),
    )
    package = build_canonical_npz(_tensors())
    physical = physical_package_digest("hds-test-physical", package)

    for digest in (logical, physical):
        hexadecimal = digest.split(":", 1)[1]
        assert len(hexadecimal) == 64
        int(hexadecimal, 16)
    assert hashlib.sha256(package).hexdigest()
    assert math.isfinite(1.0)
