#!/usr/bin/env python3
"""Compile verified teacher structure into the runtime ARC3 P/J0/M0 package."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPOSITORY_ROOT / "ARC-AGI-3-Agents"
sys.path.insert(0, str(PACKAGE_ROOT))

from arc3_agi_agent.initial_state_compiler import (  # noqa: E402
    initial_state_from_package,
)
from arc3_agi_agent.product_capability import (  # noqa: E402
    PRODUCT_CAPABILITY_DESCRIPTOR_FILENAME,
    PRODUCT_CAPABILITY_PACKAGE_FILENAME,
    ProductCompilationEvidence,
    compile_product_initial_state,
    load_product_initial_state,
    product_capability_descriptor,
)
from arc3_agi_agent.product_governance import (  # noqa: E402
    ARC3_DEVELOPMENT_ACTION_BUDGET,
    ARC3_PRODUCT_NO_PROGRESS_LIMIT,
)
from arc3_agi_agent.schema import digest_object  # noqa: E402

TEACHER_INPUTS = (
    Path("analysis/teacher/CROSS_GAME_STRUCTURAL_GRAMMAR.json"),
    Path("analysis/teacher/PRIVILEGE_SUBTRACTION_MATRIX.json"),
    Path("analysis/teacher/RUNTIME_P_COMPILATION_REPORT.json"),
)


def _object(value: object, error: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(error)
    return {str(key): item for key, item in value.items()}


def _integer(value: Mapping[str, object], key: str) -> int:
    item = value.get(key)
    if isinstance(item, bool) or not isinstance(item, int):
        raise TypeError("M2_INTEGER_FIELD_INVALID:" + key)
    return item


def _verified_content_bound_json(path: Path) -> tuple[dict[str, Any], str]:
    payload = path.read_bytes()
    value = _object(json.loads(payload), "M2_TEACHER_OBJECT_REQUIRED")
    expected = value.get("content_digest")
    if not isinstance(expected, str) or ":" not in expected:
        raise ValueError("M2_TEACHER_CONTENT_DIGEST_MISSING")
    body = dict(value)
    body.pop("content_digest")
    prefix = expected.split(":", 1)[0] + ":"
    if expected != prefix + digest_object(body):
        raise ValueError("M2_TEACHER_CONTENT_DIGEST_MISMATCH:" + path.name)
    return value, "sha256:" + hashlib.sha256(payload).hexdigest()


def compilation_evidence(root: Path) -> ProductCompilationEvidence:
    loaded = tuple(
        _verified_content_bound_json(root / relative)
        for relative in TEACHER_INPUTS
    )
    grammar, matrix, runtime_report = (item[0] for item in loaded)
    coverage = _object(
        grammar.get("coverage"),
        "M2_GRAMMAR_COVERAGE_REQUIRED",
    )
    claims = _object(
        runtime_report.get("claims"),
        "M2_RUNTIME_CLAIMS_REQUIRED",
    )
    runtime_target = _object(
        runtime_report.get("runtime_student_target"),
        "M2_RUNTIME_TARGET_REQUIRED",
    )
    forbidden = runtime_target.get("forbidden_inputs")
    if not isinstance(forbidden, list):
        raise TypeError("M2_RUNTIME_FORBIDDEN_INPUTS_REQUIRED")
    required_forbidden = {
        "ANSWER_OR_REPLAY",
        "FIXED_ACTION_SEQUENCE",
        "GAME_OR_LEVEL_ID_ROUTING",
        "LITERAL_COORDINATE_TABLE",
        "SOURCE_OR_HIDDEN_STATE",
        "TEACHER_PACKAGE",
    }
    if (
        grammar.get("identity_free_artifact") is not True
        or grammar.get("contains_game_or_level_routing") is not False
        or grammar.get("contains_literal_coordinates") is not False
        or matrix.get("capability_count") != 183
        or matrix.get("source_causal_semantic_complete_count") != 183
        or matrix.get("rendered_only_proven_count") != 183
        or claims.get("teacher_183_closure") != "PASS"
        or not str(claims.get("rendered_only_183", "")).startswith("PASS")
        or claims.get("identity_routing_free_183") != "PASS"
        or claims.get("literal_coordinate_free_183") != "PASS"
        or claims.get("source_hidden_state_free_183") != "PASS"
        or not required_forbidden.issubset(set(map(str, forbidden)))
    ):
        raise ValueError("M2_TEACHER_CLOSURE_CONTRACT_INVALID")
    evidence = ProductCompilationEvidence(
        source_digests=tuple(sorted(item[1] for item in loaded)),
        source_artifact_count=len(loaded),
        structural_record_count=_integer(matrix, "capability_count"),
        rendered_only_record_count=_integer(
            matrix,
            "rendered_only_proven_count",
        ),
        action_primitive_count=_integer(
            coverage,
            "distinct_action_primitive_count",
        ),
        role_family_count=_integer(
            coverage,
            "distinct_source_causal_role_count",
        ),
        fixed_action_dependency_count=_integer(
            matrix,
            "fixed_action_dependent_count",
        ),
        literal_coordinate_dependency_count=_integer(
            matrix,
            "literal_coordinate_dependent_count",
        ),
        identity_routing_dependency_count=_integer(
            matrix,
            "identity_routing_dependent_count",
        ),
        source_state_dependency_count=_integer(
            matrix,
            "source_or_hidden_state_dependent_count",
        ),
    )
    failures = evidence.validate()
    if failures:
        raise ValueError(";".join(failures))
    return evidence


def build(root: Path, output_directory: Path) -> dict[str, object]:
    evidence = compilation_evidence(root)
    initial_state = compile_product_initial_state(
        evidence=evidence,
        action_budget=ARC3_DEVELOPMENT_ACTION_BUDGET,
        no_progress_limit=ARC3_PRODUCT_NO_PROGRESS_LIMIT,
    )
    package_payload = initial_state.package_bytes()
    restored = initial_state_from_package(package_payload)
    if restored.package_bytes() != package_payload:
        raise RuntimeError("M2_PRODUCT_PACKAGE_REPRODUCTION_FAILED")
    descriptor = product_capability_descriptor(
        initial_state=initial_state,
        evidence=evidence,
        package_payload=package_payload,
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    descriptor_path = output_directory / PRODUCT_CAPABILITY_DESCRIPTOR_FILENAME
    package_path = output_directory / PRODUCT_CAPABILITY_PACKAGE_FILENAME
    package_path.write_bytes(package_payload)
    descriptor_path.write_text(
        json.dumps(descriptor, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    loaded = load_product_initial_state(
        descriptor_path=descriptor_path,
        package_path=package_path,
    )
    if loaded.package_bytes() != package_payload:
        raise RuntimeError("M2_PRODUCT_RUNTIME_LOAD_REPRODUCTION_FAILED")
    return {
        "descriptor": descriptor_path.relative_to(root).as_posix(),
        "package": package_path.relative_to(root).as_posix(),
        "package_sha256": hashlib.sha256(package_payload).hexdigest(),
        "package_size_bytes": len(package_payload),
        "initial_state_logical_digest": loaded.logical_digest,
        "p_logical_digest": loaded.p_bundle.logical_digest(),
        "p_program_id": loaded.p_bundle.program.program_id,
        "p_compiler_mode": loaded.p_bundle.compiler_report.mode,
        "j0_digest": "j0:" + digest_object(loaded.j0),
        "m0_digest": "m0:" + digest_object(loaded.m0),
        "m0_record_count": len(loaded.m0),
        "source_structure_count": evidence.structural_record_count,
        "rendered_only_structure_count": evidence.rendered_only_record_count,
        "status": "PRODUCT_CAPABILITY_PACKAGE_BUILT",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=REPOSITORY_ROOT)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "ARC-AGI-3-Agents"
            / "arc3_agi_agent"
            / "bundles"
        ),
    )
    arguments = parser.parse_args()
    root = arguments.repo_root.resolve()
    output = arguments.output_directory.resolve()
    result = build(root, output)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
