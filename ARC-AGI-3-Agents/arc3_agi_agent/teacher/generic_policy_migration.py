"""Development-only migration of an identity-free learned P into Generic P."""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..compiled_policy import (
    COMPILED_POLICY_BODY_VERSION,
    COMPILED_POLICY_FORMAT_ID,
    COMPILED_POLICY_SCHEMA_VERSION,
    compiled_policy_manifest_digest,
    load_compiled_autonomous_instruction_body,
)
from ..generic_compute import HybridRelationalInstructionBody
from ..schema import digest_object

GENERIC_POLICY_MIGRATION_VERSION = "arc3-generic-policy-migration-v1"


def migrate_identity_free_policy(
    *,
    source_manifest_path: Path,
    source_weights_path: Path,
    output_manifest_path: Path,
    output_weights_path: Path,
) -> dict[str, object]:
    """Copy only learned parameters and runtime schema; omit dev examples."""

    value = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise TypeError("GENERIC_POLICY_MIGRATION_SOURCE_MANIFEST_INVALID")
    source: Mapping[str, Any] = value
    if (
        source.get("runtime_identity_free") is not True
        or source.get("runtime_artifact_contains_training_examples") is not False
    ):
        raise PermissionError("GENERIC_POLICY_MIGRATION_SOURCE_BOUNDARY_INVALID")
    weights_sha256 = hashlib.sha256(
        source_weights_path.read_bytes()
    ).hexdigest()
    if source.get("weights_sha256") != weights_sha256:
        raise ValueError("GENERIC_POLICY_MIGRATION_WEIGHTS_DIGEST_MISMATCH")
    structural = HybridRelationalInstructionBody()
    source_parameter_digest = "source-parameter-artifact:" + digest_object(
        {
            "manifest_content_digest": source.get("content_digest"),
            "weights_sha256": weights_sha256,
            "parameter_count": source.get("parameter_count"),
        }
    )
    provenance_digest = "generic-policy-provenance:" + digest_object(
        {
            "migration_version": GENERIC_POLICY_MIGRATION_VERSION,
            "source_parameter_digest": source_parameter_digest,
            "structural_body_digest": structural.digest(),
        }
    )
    manifest: dict[str, object] = {
        "action_heads": source["action_heads"],
        "body_version": COMPILED_POLICY_BODY_VERSION,
        "content_digest": "",
        "feature_count": source["feature_count"],
        "feature_schema": source["feature_schema"],
        "format_id": COMPILED_POLICY_FORMAT_ID,
        "frame_dimensions": source["frame_dimensions"],
        "migration_version": GENERIC_POLICY_MIGRATION_VERSION,
        "model_family": source["model_family"],
        "parameter_count": source["parameter_count"],
        "parameter_dtype": source["parameter_dtype"],
        "pointer_heads": source["pointer_heads"],
        "provenance_digest": provenance_digest,
        "runtime_artifact_contains_examples": False,
        "runtime_identity_free": True,
        "runtime_inputs": (
            "rendered observation",
            "available actions",
            "bounded HDS-authorized action-effect memory",
            "passive semantic memory",
        ),
        "schema_version": COMPILED_POLICY_SCHEMA_VERSION,
        "source_parameter_digest": source_parameter_digest,
        "structural_body_digest": structural.digest(),
        "weights_sha256": weights_sha256,
    }
    manifest["content_digest"] = compiled_policy_manifest_digest(manifest)
    output_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    output_manifest_path.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    shutil.copyfile(source_weights_path, output_weights_path)
    body = load_compiled_autonomous_instruction_body(
        manifest_path=output_manifest_path,
        weights_path=output_weights_path,
    )
    return {
        "migration_version": GENERIC_POLICY_MIGRATION_VERSION,
        "body_digest": body.digest(),
        "body_version": body.body_version(),
        "parameter_count": body.parameter_count,
        "runtime_identity_free": True,
        "runtime_artifact_contains_examples": False,
        "source_parameter_digest": source_parameter_digest,
        "weights_sha256": weights_sha256,
    }


__all__ = [
    "GENERIC_POLICY_MIGRATION_VERSION",
    "migrate_identity_free_policy",
]
