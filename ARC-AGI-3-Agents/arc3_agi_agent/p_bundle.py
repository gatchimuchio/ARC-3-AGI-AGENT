"""Deterministic executable P bundle with canonical tensor artifacts."""

from __future__ import annotations

import io
import json
import math
import struct
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Final

import numpy as np

from .canonical_artifact import (
    build_canonical_zip,
    canonical_json_bytes,
    physical_digest,
)
from .compiled_policy import (
    COMPILED_POLICY_FORMAT_ID,
    CompiledAutonomousInstructionBody,
    compiled_autonomous_instruction_body_from_artifact,
)
from .generic_compute import (
    GenericInstructionBody,
    HybridRelationalInstructionBody,
    ParametricRelationalInstructionBody,
    SymbolicRelationalInstructionBody,
)
from .p_ir import (
    p_ir_program_from_dict,
    p_ir_program_logical_digest,
    p_ir_program_to_dict,
)
from .p_ir_types import (
    ParameterManifest,
    PIRProgram,
    TensorParameterSpec,
)
from .schema import digest_object, forbidden_runtime_paths

P_BUNDLE_SCHEMA_VERSION: Final = "arc3-p-bundle-v1"
P_COMPILER_SEMANTICS_VERSION: Final = "arc3-p-compiler-semantics-v2"
P_BUNDLE_LIFECYCLES: Final = frozenset(
    {"ACTIVE", "CANDIDATE", "PREVIOUS_STABLE", "REJECTED"}
)
CANONICAL_TENSOR_DTYPES: Final = frozenset(
    {"f16le", "i64", "ppm_i64", "u8"}
)


def _product(values: Sequence[int]) -> int:
    result = 1
    for value in values:
        result *= value
    return result


@dataclass(frozen=True, slots=True)
class CanonicalTensor:
    name: str
    dtype: str
    shape: tuple[int, ...]
    values: tuple[int, ...] = ()
    raw_bytes: bytes = field(default=b"", repr=False)

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not self.name or "/" in self.name or "\\" in self.name:
            failures.append("P_TENSOR_NAME_INVALID")
        if self.dtype not in CANONICAL_TENSOR_DTYPES:
            failures.append("P_TENSOR_DTYPE_INVALID")
        if (
            not self.shape
            or any(
                isinstance(item, bool)
                or not isinstance(item, int)
                or item <= 0
                for item in self.shape
            )
        ):
            failures.append("P_TENSOR_SHAPE_INVALID")
        if self.dtype == "f16le":
            if self.values:
                failures.append("P_TENSOR_F16_VALUES_FORBIDDEN")
            if len(self.raw_bytes) != _product(self.shape) * 2:
                failures.append("P_TENSOR_BYTE_LENGTH_INVALID")
            elif any(
                not math.isfinite(item[0])
                for item in struct.iter_unpack("<e", self.raw_bytes)
            ):
                failures.append("P_TENSOR_NONFINITE_VALUE")
        else:
            if self.raw_bytes:
                failures.append("P_TENSOR_RAW_BYTES_FORBIDDEN")
            if _product(self.shape) != len(self.values):
                failures.append("P_TENSOR_VALUE_COUNT_MISMATCH")
            if any(
                isinstance(item, bool) or not isinstance(item, int)
                for item in self.values
            ):
                failures.append("P_TENSOR_VALUE_INVALID")
            if self.dtype == "u8" and any(
                not 0 <= item <= 255 for item in self.values
            ):
                failures.append("P_TENSOR_U8_RANGE_INVALID")
            if self.dtype in {"i64", "ppm_i64"} and any(
                not -(2**63) <= item < 2**63 for item in self.values
            ):
                failures.append("P_TENSOR_I64_RANGE_INVALID")
        return tuple(sorted(set(failures)))

    def canonical_bytes(self) -> bytes:
        failures = self.validate()
        if failures:
            raise ValueError(";".join(failures))
        if self.dtype == "f16le":
            return self.raw_bytes
        if self.dtype == "u8":
            return bytes(self.values)
        return struct.pack("<" + "q" * len(self.values), *self.values)

    def logical_digest(self) -> str:
        return "p-tensor-logical:" + digest_object(
            {
                "name": self.name,
                "dtype": self.dtype,
                "shape": self.shape,
                "bytes_sha256": physical_digest(
                    self.canonical_bytes(),
                    namespace="tensor-bytes",
                ),
            }
        )

    def parameter_spec(self) -> TensorParameterSpec:
        payload = self.canonical_bytes()
        return TensorParameterSpec(
            name=self.name,
            dtype=self.dtype,
            shape=self.shape,
            logical_digest=self.logical_digest(),
            byte_length=len(payload),
        )


def tensor_from_floats(
    *,
    name: str,
    shape: tuple[int, ...],
    values: Sequence[float],
) -> CanonicalTensor:
    quantized: list[int] = []
    for value in values:
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
        ):
            raise ValueError("P_TENSOR_NONFINITE_VALUE")
        item = int(round(float(value) * 1_000_000))
        quantized.append(0 if item == 0 else item)
    tensor = CanonicalTensor(
        name=name,
        dtype="ppm_i64",
        shape=shape,
        values=tuple(quantized),
    )
    failures = tensor.validate()
    if failures:
        raise ValueError(";".join(failures))
    return tensor


def tensor_from_float16_array(
    *,
    name: str,
    value: np.ndarray,
) -> CanonicalTensor:
    array = np.asarray(value)
    if not array.shape or any(int(item) <= 0 for item in array.shape):
        raise ValueError("P_TENSOR_SHAPE_INVALID")
    if not np.isfinite(array).all():
        raise ValueError("P_TENSOR_NONFINITE_VALUE")
    canonical = np.ascontiguousarray(array, dtype="<f2")
    tensor = CanonicalTensor(
        name=name,
        dtype="f16le",
        shape=tuple(int(item) for item in canonical.shape),
        raw_bytes=canonical.tobytes(order="C"),
    )
    failures = tensor.validate()
    if failures:
        raise ValueError(";".join(failures))
    return tensor


@dataclass(frozen=True, slots=True)
class InstructionBodyManifest:
    format_id: str
    body_version: str
    provenance_items: tuple[tuple[str, str], ...]
    action_bias_keys: tuple[str, ...] = ()

    def digest(self) -> str:
        return "instruction-body-manifest:" + digest_object(self)


def instruction_body_manifest(
    body: GenericInstructionBody,
) -> InstructionBodyManifest:
    provenance: tuple[tuple[str, str], ...]
    action_bias_keys: tuple[str, ...]
    if isinstance(body, CompiledAutonomousInstructionBody):
        provenance = (
            ("compiled", body.provenance_digest()),
            ("structural", body.structural.provenance_digest()),
        )
        action_bias_keys = ()
    elif isinstance(body, SymbolicRelationalInstructionBody):
        provenance = (("symbolic", body.provenance),)
        action_bias_keys = ()
    elif isinstance(body, ParametricRelationalInstructionBody):
        provenance = (("parametric", body.provenance),)
        action_bias_keys = tuple(key for key, _ in body.action_bias_items)
    elif isinstance(body, HybridRelationalInstructionBody):
        provenance = (
            ("parametric", body.parametric.provenance),
            ("symbolic", body.symbolic.provenance),
        )
        action_bias_keys = tuple(
            key for key, _ in body.parametric.action_bias_items
        )
    else:
        raise TypeError("P_BUNDLE_INSTRUCTION_BODY_UNSUPPORTED")
    return InstructionBodyManifest(
        format_id=body.format_id(),
        body_version=body.body_version(),
        provenance_items=tuple(sorted(provenance)),
        action_bias_keys=action_bias_keys,
    )


def instruction_body_tensors(
    body: GenericInstructionBody,
) -> tuple[CanonicalTensor, ...]:
    if isinstance(body, CompiledAutonomousInstructionBody):
        compiled_tensors = [
            CanonicalTensor(
                name="compiled.manifest",
                dtype="u8",
                shape=(len(body.serialize()),),
                values=tuple(body.serialize()),
            ),
            *(
                tensor_from_float16_array(
                    name="compiled.array." + name,
                    value=array,
                )
                for name, array in body.tensor_arrays().items()
            ),
        ]
        return tuple(
            sorted(compiled_tensors, key=lambda item: item.name)
        )
    if isinstance(body, SymbolicRelationalInstructionBody):
        return ()
    parametric = (
        body.parametric
        if isinstance(body, HybridRelationalInstructionBody)
        else body
    )
    if not isinstance(parametric, ParametricRelationalInstructionBody):
        raise TypeError("P_BUNDLE_PARAMETRIC_BODY_REQUIRED")
    hidden_rows = len(parametric.hidden_weights)
    parametric_tensors = (
        tensor_from_floats(
            name="parametric.hidden_weights",
            shape=(hidden_rows, 8),
            values=tuple(
                value
                for row in parametric.hidden_weights
                for value in row
            ),
        ),
        tensor_from_floats(
            name="parametric.progress_weights",
            shape=(len(parametric.progress_weights),),
            values=parametric.progress_weights,
        ),
        tensor_from_floats(
            name="parametric.hazard_weights",
            shape=(len(parametric.hazard_weights),),
            values=parametric.hazard_weights,
        ),
        tensor_from_floats(
            name="parametric.information_weights",
            shape=(len(parametric.information_weights),),
            values=parametric.information_weights,
        ),
        tensor_from_floats(
            name="parametric.action_bias",
            shape=(max(1, len(parametric.action_bias_items)),),
            values=(
                tuple(value for _, value in parametric.action_bias_items)
                or (0.0,)
            ),
        ),
    )
    return tuple(sorted(parametric_tensors, key=lambda item: item.name))


def _float_values(tensor: CanonicalTensor) -> tuple[float, ...]:
    if tensor.dtype != "ppm_i64":
        raise TypeError("P_BUNDLE_PPM_TENSOR_REQUIRED")
    return tuple(value / 1_000_000.0 for value in tensor.values)


def instruction_body_from_artifact(
    manifest: InstructionBodyManifest,
    tensors: Sequence[CanonicalTensor],
) -> GenericInstructionBody:
    provenance = dict(manifest.provenance_items)
    if manifest.format_id == COMPILED_POLICY_FORMAT_ID:
        tensor_map = {item.name: item for item in tensors}
        manifest_tensor = tensor_map.get("compiled.manifest")
        if (
            manifest_tensor is None
            or manifest_tensor.dtype != "u8"
            or not manifest_tensor.values
        ):
            raise ValueError("P_BUNDLE_COMPILED_MANIFEST_MISSING")
        prefix = "compiled.array."
        array_tensors = {
            name.removeprefix(prefix): tensor
            for name, tensor in tensor_map.items()
            if name.startswith(prefix)
        }
        if not array_tensors:
            raise ValueError("P_BUNDLE_COMPILED_TENSOR_MISSING")
        arrays: dict[str, np.ndarray] = {}
        for name, tensor in array_tensors.items():
            if tensor.dtype != "f16le":
                raise ValueError("P_BUNDLE_COMPILED_TENSOR_DTYPE_INVALID")
            arrays[name] = np.frombuffer(
                tensor.canonical_bytes(),
                dtype="<f2",
            ).reshape(tensor.shape)
        return compiled_autonomous_instruction_body_from_artifact(
            manifest_bytes=manifest_tensor.canonical_bytes(),
            tensor_arrays=arrays,
        )
    if manifest.format_id == "generic-symbolic-relational":
        return SymbolicRelationalInstructionBody(
            version=manifest.body_version,
            provenance=provenance["symbolic"],
        )
    tensor_map = {item.name: item for item in tensors}
    required = {
        "parametric.hidden_weights",
        "parametric.progress_weights",
        "parametric.hazard_weights",
        "parametric.information_weights",
        "parametric.action_bias",
    }
    if not required.issubset(tensor_map):
        raise ValueError("P_BUNDLE_PARAMETRIC_TENSOR_MISSING")
    hidden_tensor = tensor_map["parametric.hidden_weights"]
    if len(hidden_tensor.shape) != 2 or hidden_tensor.shape[1] != 8:
        raise ValueError("P_BUNDLE_HIDDEN_TENSOR_SHAPE_INVALID")
    hidden_values = _float_values(hidden_tensor)
    hidden = tuple(
        tuple(hidden_values[index * 8 : (index + 1) * 8])
        for index in range(hidden_tensor.shape[0])
    )
    bias_values = _float_values(tensor_map["parametric.action_bias"])
    if manifest.action_bias_keys:
        if len(bias_values) != len(manifest.action_bias_keys):
            raise ValueError("P_BUNDLE_ACTION_BIAS_SHAPE_INVALID")
        action_bias = tuple(zip(manifest.action_bias_keys, bias_values))
    else:
        action_bias = ()
    parametric = ParametricRelationalInstructionBody(
        version=manifest.body_version,
        provenance=provenance["parametric"],
        hidden_weights=hidden,
        progress_weights=_float_values(
            tensor_map["parametric.progress_weights"]
        ),
        hazard_weights=_float_values(
            tensor_map["parametric.hazard_weights"]
        ),
        information_weights=_float_values(
            tensor_map["parametric.information_weights"]
        ),
        action_bias_items=action_bias,
    )
    if manifest.format_id == "generic-parametric-relational":
        return parametric
    if manifest.format_id == "generic-hybrid-relational":
        return HybridRelationalInstructionBody(
            symbolic=SymbolicRelationalInstructionBody(
                provenance=provenance["symbolic"],
            ),
            parametric=parametric,
            version=manifest.body_version,
        )
    raise ValueError("P_BUNDLE_INSTRUCTION_FORMAT_UNSUPPORTED")


def bind_program_parameters(
    program: PIRProgram,
    *,
    body_manifest: InstructionBodyManifest,
    tensors: Sequence[CanonicalTensor],
) -> PIRProgram:
    ordered = tuple(sorted(tensors, key=lambda item: item.name))
    source_digests = tuple(
        sorted(
            {
                *program.provenance.source_digests,
                body_manifest.digest(),
            }
        )
    )
    return replace(
        program,
        parameter_manifest=ParameterManifest(
            tensors=tuple(item.parameter_spec() for item in ordered),
            scalar_parameters=program.parameter_manifest.scalar_parameters,
        ),
        provenance=replace(
            program.provenance,
            source_digests=source_digests,
        ),
    )


@dataclass(frozen=True, slots=True)
class PCompilerReport:
    compiler_version: str
    mode: str
    selected_evidence_count: int
    evidence_selection_digest: str
    compiled_targets: tuple[str, ...]
    taint_finding_count: int
    resource_failures: tuple[str, ...]
    deterministic: bool


@dataclass(frozen=True, slots=True)
class PBundleManifest:
    schema_version: str
    bundle_id: str
    version: str
    lifecycle: str
    compiler_semantics_version: str
    parent_logical_digest: str
    evidence_selection_digest: str
    l0_abi_version: str
    program_logical_digest: str
    body_manifest: InstructionBodyManifest
    body_digest: str
    identity_free: bool


@dataclass(frozen=True, slots=True)
class PBundle:
    manifest: PBundleManifest
    program: PIRProgram
    body: GenericInstructionBody
    tensors: tuple[CanonicalTensor, ...]
    compiler_report: PCompilerReport
    evaluation_report: tuple[tuple[str, str], ...] = ()
    promotion_report: tuple[tuple[str, str], ...] = ()

    def logical_digest(self) -> str:
        return "p-logical:" + digest_object(
            {
                "program": p_ir_program_to_dict(self.program),
                "ordered_tensor_logical_digests": tuple(
                    (item.name, item.logical_digest())
                    for item in self.tensors
                ),
                "l0_abi_version": self.manifest.l0_abi_version,
                "compiler_semantics_version": (
                    self.manifest.compiler_semantics_version
                ),
            }
        )

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if self.manifest.schema_version != P_BUNDLE_SCHEMA_VERSION:
            failures.append("P_BUNDLE_SCHEMA_INVALID")
        if self.manifest.lifecycle not in P_BUNDLE_LIFECYCLES:
            failures.append("P_BUNDLE_LIFECYCLE_INVALID")
        if self.manifest.identity_free is not True:
            failures.append("P_BUNDLE_IDENTITY_FLAG_INVALID")
        if (
            self.manifest.compiler_semantics_version
            != P_COMPILER_SEMANTICS_VERSION
        ):
            failures.append("P_BUNDLE_COMPILER_SEMANTICS_INVALID")
        if self.manifest.l0_abi_version != self.program.l0_abi_version:
            failures.append("P_BUNDLE_ABI_MISMATCH")
        if (
            self.manifest.program_logical_digest
            != p_ir_program_logical_digest(self.program)
        ):
            failures.append("P_BUNDLE_PROGRAM_DIGEST_MISMATCH")
        if self.manifest.body_digest != self.body.digest():
            failures.append("P_BUNDLE_BODY_DIGEST_MISMATCH")
        if (
            self.manifest.body_manifest
            != instruction_body_manifest(self.body)
        ):
            failures.append("P_BUNDLE_BODY_MANIFEST_MISMATCH")
        if (
            self.manifest.body_manifest.digest()
            not in self.program.provenance.source_digests
        ):
            failures.append("P_BUNDLE_BODY_PROGRAM_BINDING_MISSING")
        body_failures = self.body.validate()
        failures.extend("P_BUNDLE_BODY:" + item for item in body_failures)
        tensor_names = tuple(item.name for item in self.tensors)
        if tensor_names != tuple(sorted(set(tensor_names))):
            failures.append("P_BUNDLE_TENSOR_ORDER_INVALID")
        for tensor in self.tensors:
            failures.extend(tensor.validate())
        expected_specs = tuple(
            item.parameter_spec() for item in self.tensors
        )
        if self.program.parameter_manifest.tensors != expected_specs:
            failures.append("P_BUNDLE_PARAMETER_MANIFEST_MISMATCH")
        if forbidden_runtime_paths(self):
            failures.append("P_BUNDLE_IDENTITY_TAINT")
        if self.compiler_report.taint_finding_count != 0:
            failures.append("P_BUNDLE_COMPILER_TAINT_FINDING")
        if self.compiler_report.resource_failures:
            failures.append("P_BUNDLE_COMPILER_RESOURCE_FAILURE")
        if self.compiler_report.deterministic is not True:
            failures.append("P_BUNDLE_COMPILER_NONDETERMINISTIC")
        return tuple(sorted(set(failures)))

    def artifact_members(self) -> dict[str, bytes]:
        failures = self.validate()
        if failures:
            raise ValueError(";".join(failures))
        manifest_value = {
            "manifest": self.manifest,
            "p_logical_digest": self.logical_digest(),
            "tensor_specs": tuple(
                item.parameter_spec() for item in self.tensors
            ),
        }
        members = {
            "manifest.json": canonical_json_bytes(manifest_value),
            "program.json": canonical_json_bytes(
                p_ir_program_to_dict(self.program)
            ),
            "compiler_report.json": canonical_json_bytes(
                self.compiler_report
            ),
            "evaluation_report.json": canonical_json_bytes(
                self.evaluation_report
            ),
            "promotion_report.json": canonical_json_bytes(
                self.promotion_report
            ),
        }
        for tensor in self.tensors:
            members["tensors/" + tensor.name + ".bin"] = (
                tensor.canonical_bytes()
            )
        return members

    def package_bytes(self) -> bytes:
        return build_canonical_zip(self.artifact_members())

    def physical_digest(self) -> str:
        return physical_digest(
            self.package_bytes(),
            namespace="p-physical-package",
        )


def _mapping(value: object, error: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(error)
    return value


def _int_field(
    value: Mapping[str, object],
    key: str,
    error: str,
) -> int:
    item = value.get(key)
    if isinstance(item, bool) or not isinstance(item, int):
        raise TypeError(error)
    return item


def _int_tuple(value: object, error: str) -> tuple[int, ...]:
    if not isinstance(value, Sequence) or isinstance(
        value, (str, bytes, bytearray)
    ):
        raise TypeError(error)
    output: list[int] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int):
            raise TypeError(error)
        output.append(item)
    return tuple(output)


def _string_pairs(value: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, Sequence) or isinstance(
        value, (str, bytes, bytearray)
    ):
        raise TypeError("P_BUNDLE_REPORT_INVALID")
    output: list[tuple[str, str]] = []
    for item in value:
        if not isinstance(item, Sequence) or isinstance(
            item, (str, bytes, bytearray)
        ):
            raise TypeError("P_BUNDLE_REPORT_PAIR_INVALID")
        pair = tuple(item)
        if len(pair) != 2:
            raise TypeError("P_BUNDLE_REPORT_PAIR_INVALID")
        output.append((str(pair[0]), str(pair[1])))
    return tuple(output)


def _body_manifest_from_dict(
    value: Mapping[str, object],
) -> InstructionBodyManifest:
    provenance_value = value.get("provenance_items", ())
    action_bias_value = value.get("action_bias_keys", ())
    if not isinstance(action_bias_value, Sequence) or isinstance(
        action_bias_value, (str, bytes, bytearray)
    ):
        raise TypeError("P_BUNDLE_ACTION_BIAS_KEYS_INVALID")
    return InstructionBodyManifest(
        format_id=str(value["format_id"]),
        body_version=str(value["body_version"]),
        provenance_items=_string_pairs(provenance_value),
        action_bias_keys=tuple(str(item) for item in action_bias_value),
    )


def _tensor_from_bytes(
    spec: TensorParameterSpec,
    payload: bytes,
) -> CanonicalTensor:
    raw_bytes = b""
    values: tuple[int, ...]
    if spec.dtype == "f16le":
        values = ()
        raw_bytes = payload
    elif spec.dtype == "u8":
        values = tuple(payload)
    elif spec.dtype in {"i64", "ppm_i64"}:
        if len(payload) % 8:
            raise ValueError("P_TENSOR_BYTE_LENGTH_INVALID")
        values = tuple(
            item[0]
            for item in struct.iter_unpack("<q", payload)
        )
    else:
        raise ValueError("P_TENSOR_DTYPE_INVALID")
    tensor = CanonicalTensor(
        name=spec.name,
        dtype=spec.dtype,
        shape=spec.shape,
        values=values,
        raw_bytes=raw_bytes,
    )
    if (
        tensor.logical_digest() != spec.logical_digest
        or len(payload) != spec.byte_length
    ):
        raise ValueError("P_TENSOR_ARTIFACT_DIGEST_MISMATCH")
    return tensor


def p_bundle_from_package(payload: bytes) -> PBundle:
    with zipfile.ZipFile(io.BytesIO(payload), mode="r") as archive:
        names = tuple(sorted(archive.namelist()))
        required = {
            "manifest.json",
            "program.json",
            "compiler_report.json",
            "evaluation_report.json",
            "promotion_report.json",
        }
        if not required.issubset(names):
            raise ValueError("P_BUNDLE_PACKAGE_MEMBER_MISSING")
        manifest_root = _mapping(
            json.loads(archive.read("manifest.json")),
            "P_BUNDLE_MANIFEST_INVALID",
        )
        manifest_value = _mapping(
            manifest_root.get("manifest"),
            "P_BUNDLE_MANIFEST_INVALID",
        )
        body_manifest_value = _mapping(
            manifest_value.get("body_manifest"),
            "P_BUNDLE_BODY_MANIFEST_INVALID",
        )
        body_manifest = _body_manifest_from_dict(body_manifest_value)
        tensor_specs_value = manifest_root.get("tensor_specs", ())
        if not isinstance(tensor_specs_value, Sequence) or isinstance(
            tensor_specs_value, (str, bytes, bytearray)
        ):
            raise TypeError("P_BUNDLE_TENSOR_SPECS_INVALID")
        tensor_specs_list: list[TensorParameterSpec] = []
        for item in tensor_specs_value:
            spec_value = _mapping(item, "P_TENSOR_SPEC_INVALID")
            tensor_specs_list.append(
                TensorParameterSpec(
                    name=str(spec_value["name"]),
                    dtype=str(spec_value["dtype"]),
                    shape=_int_tuple(
                        spec_value.get("shape", ()),
                        "P_TENSOR_SPEC_SHAPE_INVALID",
                    ),
                    logical_digest=str(spec_value["logical_digest"]),
                    byte_length=_int_field(
                        spec_value,
                        "byte_length",
                        "P_TENSOR_SPEC_BYTE_LENGTH_INVALID",
                    ),
                )
            )
        tensor_specs = tuple(tensor_specs_list)
        tensors = tuple(
            _tensor_from_bytes(
                spec,
                archive.read("tensors/" + spec.name + ".bin"),
            )
            for spec in tensor_specs
        )
        program_value = _mapping(
            json.loads(archive.read("program.json")),
            "P_IR_PROGRAM_INVALID",
        )
        program = p_ir_program_from_dict(program_value)
        body = instruction_body_from_artifact(body_manifest, tensors)
        compiler_value = _mapping(
            json.loads(archive.read("compiler_report.json")),
            "P_COMPILER_REPORT_INVALID",
        )
        compiled_targets_value = compiler_value.get("compiled_targets", ())
        resource_failures_value = compiler_value.get(
            "resource_failures", ()
        )
        if not isinstance(compiled_targets_value, Sequence) or isinstance(
            compiled_targets_value, (str, bytes, bytearray)
        ):
            raise TypeError("P_COMPILER_TARGETS_INVALID")
        if not isinstance(resource_failures_value, Sequence) or isinstance(
            resource_failures_value, (str, bytes, bytearray)
        ):
            raise TypeError("P_COMPILER_RESOURCE_FAILURES_INVALID")
        compiler_report = PCompilerReport(
            compiler_version=str(compiler_value["compiler_version"]),
            mode=str(compiler_value["mode"]),
            selected_evidence_count=_int_field(
                compiler_value,
                "selected_evidence_count",
                "P_COMPILER_EVIDENCE_COUNT_INVALID",
            ),
            evidence_selection_digest=str(
                compiler_value["evidence_selection_digest"]
            ),
            compiled_targets=tuple(
                str(item) for item in compiled_targets_value
            ),
            taint_finding_count=_int_field(
                compiler_value,
                "taint_finding_count",
                "P_COMPILER_TAINT_COUNT_INVALID",
            ),
            resource_failures=tuple(
                str(item) for item in resource_failures_value
            ),
            deterministic=bool(compiler_value["deterministic"]),
        )
        manifest = PBundleManifest(
            schema_version=str(manifest_value["schema_version"]),
            bundle_id=str(manifest_value["bundle_id"]),
            version=str(manifest_value["version"]),
            lifecycle=str(manifest_value["lifecycle"]),
            compiler_semantics_version=str(
                manifest_value["compiler_semantics_version"]
            ),
            parent_logical_digest=str(
                manifest_value["parent_logical_digest"]
            ),
            evidence_selection_digest=str(
                manifest_value["evidence_selection_digest"]
            ),
            l0_abi_version=str(manifest_value["l0_abi_version"]),
            program_logical_digest=str(
                manifest_value["program_logical_digest"]
            ),
            body_manifest=body_manifest,
            body_digest=str(manifest_value["body_digest"]),
            identity_free=bool(manifest_value["identity_free"]),
        )
        evaluation = _string_pairs(
            json.loads(archive.read("evaluation_report.json"))
        )
        promotion = _string_pairs(
            json.loads(archive.read("promotion_report.json"))
        )
    bundle = PBundle(
        manifest=manifest,
        program=program,
        body=body,
        tensors=tensors,
        compiler_report=compiler_report,
        evaluation_report=evaluation,
        promotion_report=promotion,
    )
    failures = bundle.validate()
    if failures:
        raise ValueError(";".join(failures))
    if manifest_root.get("p_logical_digest") != bundle.logical_digest():
        raise ValueError("P_BUNDLE_LOGICAL_DIGEST_MISMATCH")
    if bundle.package_bytes() != payload:
        raise ValueError("P_BUNDLE_PHYSICAL_REPRODUCTION_MISMATCH")
    return bundle


__all__ = [
    "CANONICAL_TENSOR_DTYPES",
    "P_BUNDLE_LIFECYCLES",
    "P_BUNDLE_SCHEMA_VERSION",
    "P_COMPILER_SEMANTICS_VERSION",
    "CanonicalTensor",
    "InstructionBodyManifest",
    "PBundle",
    "PBundleManifest",
    "PCompilerReport",
    "bind_program_parameters",
    "instruction_body_from_artifact",
    "instruction_body_manifest",
    "instruction_body_tensors",
    "p_bundle_from_package",
    "tensor_from_float16_array",
    "tensor_from_floats",
]
