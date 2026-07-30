"""PH-D02C executable Causal IR conformance and boundary tests."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

import pytest

from hds_distill.canonical import JsonValue
from hds_distill.causal_ir import (
    IR_SCHEMA_CONTRACT_DIGEST,
    IRNode,
    TypedInput,
    build_code_ir_abi,
    build_program,
    type_check_program,
)
from hds_distill.interpreter import execute_program
from hds_distill.ir_types import (
    COMMON_TYPE_NAMES,
    IRContractError,
    JsonObject,
    validate_typed_value,
)
from hds_distill.operator_registry import (
    ARC2_OPCODE_NAMES,
    ARC3_OPCODE_NAMES,
    build_operator_registry,
    validate_operator_registry,
)
from hds_distill.verification import (
    BoundedSyntheticInterventionRunner,
    CanonicalExactComparator,
    SyntheticIntervention,
    build_causal_ir_conformance_report,
    build_invalid_ir_vector_artifact,
    build_phase_d02c_artifacts,
    build_valid_ir_vector_artifact,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DISTILLATION_SOURCE = REPOSITORY_ROOT / "distillation" / "src"


@lru_cache(maxsize=1)
def _valid_vectors() -> JsonObject:
    return build_valid_ir_vector_artifact()


@lru_cache(maxsize=1)
def _invalid_vectors() -> JsonObject:
    return build_invalid_ir_vector_artifact()


def _vector(domain: str, opcode: str) -> Mapping[str, Any]:
    vectors = cast(list[Mapping[str, Any]], _valid_vectors()["vectors"])
    return next(
        item
        for item in vectors
        if item["domain"] == domain and item["opcode"] == opcode
    )


def _program(domain: str, opcode: str) -> JsonObject:
    return cast(JsonObject, copy.deepcopy(_vector(domain, opcode)["program"]))


def _output(domain: str, opcode: str) -> object:
    result = cast(Mapping[str, Any], _vector(domain, opcode)["expected_result"])
    outputs = cast(Mapping[str, object], result["outputs"])
    return outputs["result"]


def test_authority_type_and_opcode_inventories_are_exact() -> None:
    assert COMMON_TYPE_NAMES == (
        "Grid",
        "Cell",
        "CellSet",
        "Region",
        "ObjectCandidate",
        "ObjectSet",
        "RelationGraph",
        "Scalar",
        "Color",
        "Vector",
        "Sequence",
        "Boolean",
        "State",
        "ActionRecord",
        "Trajectory",
        "Event",
        "Effect",
        "TerminalState",
    )
    assert len(ARC2_OPCODE_NAMES) == 33
    assert len(ARC3_OPCODE_NAMES) == 18
    assert len(set(ARC2_OPCODE_NAMES)) == 33
    assert len(set(ARC3_OPCODE_NAMES)) == 18


def test_abi_schema_digest_matches_checked_refinement_contract() -> None:
    contract = json.loads(
        (REPOSITORY_ROOT / "distillation/input/schema_contract.json").read_text(
            encoding="utf-8"
        )
    )

    assert contract["content_digest"] == IR_SCHEMA_CONTRACT_DIGEST
    for domain in ("ARC2", "ARC3"):
        assert (
            build_code_ir_abi(domain)["ir_schema_contract_digest"]
            == IR_SCHEMA_CONTRACT_DIGEST
        )


@pytest.mark.parametrize(
    ("type_name", "value"),
    [
        ("Scalar", True),
        ("Color", 10),
        ("Grid", [[1], [1, 2]]),
        ("CellSet", [[1, 0], [0, 0]]),
        ("Region", {"top": 0, "left": 0, "height": 0, "width": 1}),
        (
            "ActionRecord",
            {
                "action_id": 8,
                "available_actions": [0],
                "payload": {},
            },
        ),
    ],
)
def test_common_types_reject_coercion_and_malformed_values(
    type_name: str,
    value: object,
) -> None:
    with pytest.raises(IRContractError, match="^IR_TYPE_ERROR"):
        validate_typed_value(type_name, value)


@pytest.mark.parametrize("domain", ["ARC2", "ARC3"])
def test_registry_entries_are_complete_content_bound_and_valid(domain: str) -> None:
    registry = build_operator_registry(domain)
    validate_operator_registry(registry)
    entries = cast(list[Mapping[str, Any]], registry["entries"])
    expected = ARC2_OPCODE_NAMES if domain == "ARC2" else ARC3_OPCODE_NAMES

    assert tuple(item["opcode"] for item in entries) == expected
    for entry in entries:
        assert set(entry) == {
            "canonicalization_rule",
            "commutes_with",
            "content_digest",
            "deterministic",
            "domain",
            "execution_semantics",
            "input_types",
            "invalid_operation_semantics",
            "opcode",
            "opcode_version",
            "output_type",
            "parameter_schema",
            "preconditions",
            "resource_cost",
            "selector_cardinality",
            "side_effect_free",
            "test_vector_refs",
        }
        assert entry["commutes_with"] == []
        assert cast(str, entry["content_digest"]).startswith("hds-operator-entry:")
        assert entry["test_vector_refs"] == [f"D02C-{domain}-{entry['opcode']}-V1"]


def test_valid_vector_set_executes_every_registered_opcode() -> None:
    artifact = _valid_vectors()
    vectors = cast(list[Mapping[str, Any]], artifact["vectors"])

    assert artifact["vector_count"] == 51
    assert {(item["domain"], item["opcode"]) for item in vectors} == {
        *(("ARC2", opcode) for opcode in ARC2_OPCODE_NAMES),
        *(("ARC3", opcode) for opcode in ARC3_OPCODE_NAMES),
    }
    for vector in vectors:
        program = cast(Mapping[str, object], vector["program"])
        expected = cast(Mapping[str, object], vector["expected_result"])
        assert execute_program(program).as_json() == dict(expected)
        assert type_check_program(program).domain == vector["domain"]


@pytest.mark.parametrize(
    ("domain", "opcode", "expected"),
    [
        ("ARC2", "ROTATE_90", [[0, 1], [2, 0]]),
        (
            "ARC2",
            "TILE",
            [
                [1, 0, 1, 0],
                [1, 0, 1, 0],
                [0, 2, 0, 2],
                [0, 2, 0, 2],
            ],
        ),
        ("ARC2", "OVERLAY", [[1, 3], [4, 2]]),
        ("ARC2", "CONNECT", [[0, 0], [1, 1]]),
        ("ARC2", "COUNT_ENCODE", [[3, 3, 3]]),
        ("ARC3", "MATCH_ACTION_ID", True),
        ("ARC3", "MATCH_ACTION_PAYLOAD", True),
        ("ARC3", "ORDER_ADJACENT", True),
        ("ARC3", "TERMINAL_CONTRIBUTION", 4),
    ],
)
def test_representative_operator_outputs_have_independent_expectations(
    domain: str,
    opcode: str,
    expected: object,
) -> None:
    assert _output(domain, opcode) == expected


def test_invalid_vector_set_fails_with_exact_stable_codes() -> None:
    artifact = _invalid_vectors()
    vectors = cast(list[Mapping[str, Any]], artifact["vectors"])

    assert artifact["vector_count"] == 15
    for vector in vectors:
        with pytest.raises(IRContractError) as captured:
            execute_program(cast(Mapping[str, object], vector["program"]))
        assert captured.value.code == vector["expected_error_code"]


@pytest.mark.parametrize(
    ("forbidden_key", "expected_code"),
    [
        ("case_id", "IR_IDENTITY_ROUTING_FORBIDDEN"),
        ("game_id", "IR_IDENTITY_ROUTING_FORBIDDEN"),
        ("source_filename", "IR_IDENTITY_ROUTING_FORBIDDEN"),
        ("full_input_digest_lookup", "IR_IDENTITY_ROUTING_FORBIDDEN"),
        ("full_answer_literal", "IR_ANSWER_COPY_FORBIDDEN"),
        ("output_coordinates", "IR_ANSWER_COPY_FORBIDDEN"),
        ("successful_action_sequence", "IR_ANSWER_COPY_FORBIDDEN"),
    ],
)
def test_recursive_privileged_routing_and_answer_copy_fail_closed(
    forbidden_key: str,
    expected_code: str,
) -> None:
    program = _program("ARC2", "COPY")
    program["invariants"] = [{"nested": {forbidden_key: "forbidden"}}]

    with pytest.raises(IRContractError) as captured:
        type_check_program(program)
    assert captured.value.code == expected_code


def test_node_order_is_preserved_in_execution_trace() -> None:
    source = TypedInput(
        name="input_grid",
        type_name="Grid",
        value=validate_typed_value("Grid", [[1, 2]]),
        provenance="OBSERVED",
    )
    first = IRNode(
        node_id="copy_first",
        opcode="COPY",
        input_refs=("input_grid",),
        parameters={},
        declared_output_type="Grid",
    )
    second = IRNode(
        node_id="copy_second",
        opcode="COPY",
        input_refs=("copy_first",),
        parameters={},
        declared_output_type="Grid",
    )
    program = build_program(
        domain="ARC2",
        inputs=(source,),
        operator_nodes=(first, second),
        output_refs=("copy_second",),
    )

    result = execute_program(program)
    assert [item.node_id for item in result.trace] == [
        "copy_first",
        "copy_second",
    ]


def test_selector_cardinality_never_chooses_first_implicitly() -> None:
    zero = _program("ARC2", "UNIQUE")
    zero_inputs = cast(list[JsonObject], zero["inputs"])
    zero_inputs[0]["value"] = []
    from hds_distill.verification import _rebind_program

    _rebind_program(zero)
    with pytest.raises(IRContractError) as zero_error:
        execute_program(zero)
    assert zero_error.value.code == "IR_CARDINALITY_ERROR"

    multiple = _program("ARC2", "UNIQUE")
    multiple_inputs = cast(list[JsonObject], multiple["inputs"])
    single = cast(list[JsonValue], multiple_inputs[0]["value"])[0]
    multiple_inputs[0]["value"] = [single, copy.deepcopy(single)]
    _rebind_program(multiple)
    with pytest.raises(IRContractError) as multiple_error:
        execute_program(multiple)
    assert multiple_error.value.code == "IR_CARDINALITY_ERROR"


def test_resource_overflow_suspends_without_causal_rejection() -> None:
    program = _program("ARC2", "SELECT_COMPONENTS_4")
    program["resource_limit"] = 1
    from hds_distill.verification import _rebind_program

    _rebind_program(program)
    result = execute_program(program)

    assert result.status == "SUSPEND_RESOURCE"
    assert result.assertion_state == "SUSPEND"
    assert result.operation_state == "HOLD"
    assert result.evidence_state == "INCONCLUSIVE"
    assert result.reason_code == "SUSPEND_RESOURCE"


def test_abi_rejects_each_bound_version_or_digest_mismatch() -> None:
    program = _program("ARC2", "COPY")
    from hds_distill.verification import _rebind_program

    for field in build_code_ir_abi("ARC2"):
        changed = copy.deepcopy(program)
        changed_abi = cast(JsonObject, changed["abi"])
        value = changed_abi[field]
        changed_abi[field] = (
            value + "-mismatch" if isinstance(value, str) else "mismatch"
        )
        _rebind_program(changed)
        with pytest.raises(IRContractError) as captured:
            type_check_program(changed)
        assert captured.value.code == "IR_ABI_MISMATCH"


def test_exact_comparator_has_no_tolerance_or_repair() -> None:
    comparator = CanonicalExactComparator()
    assert comparator.compare(
        type_name="Grid",
        expected=[[1, 0]],
        actual=[[1, 0]],
    ).equal
    assert not comparator.compare(
        type_name="Grid",
        expected=[[1, 0]],
        actual=[[0, 1]],
    ).equal
    with pytest.raises(IRContractError, match="^IR_TYPE_ERROR"):
        comparator.compare(
            type_name="Grid",
            expected=[[1, 0]],
            actual=[[1.0, 0]],
        )


def test_synthetic_intervention_is_bounded_and_never_claims_causality() -> None:
    runner = BoundedSyntheticInterventionRunner(intervention_budget=1)
    outcome = runner.run(
        _program("ARC2", "COPY"),
        (
            SyntheticIntervention(
                input_name="input_0",
                replacement_value=[[9]],
            ),
        ),
    )

    assert outcome.execution_scope == "SYNTHETIC_ONLY"
    assert outcome.causal_claim is None
    assert outcome.baseline_result.result_digest != (
        outcome.intervened_result.result_digest
    )
    with pytest.raises(IRContractError, match="^SUSPEND_RESOURCE"):
        runner.run(
            _program("ARC2", "COPY"),
            (
                SyntheticIntervention("input_0", [[8]]),
                SyntheticIntervention("input_0", [[7]]),
            ),
        )


def test_conformance_report_closes_all_d02c_gates_without_approval() -> None:
    report = build_causal_ir_conformance_report(
        _valid_vectors(),
        _invalid_vectors(),
    )

    assert report["valid_vector_pass_count"] == 51
    assert report["invalid_vector_pass_count"] == 15
    assert report["gate_results"] == {
        "DG-03": "PASS_TYPED_EXECUTABLE_IR_AND_STABLE_ERRORS",
        "DG-08": "PASS_PRIVILEGED_ROUTING_REJECTED",
        "DG-09": "PASS_PREDICTIVE_SCOPE_NO_CAUSAL_OVERCLAIM",
        "DG-12": "PASS_RESOURCE_OVERFLOW_SUSPENDS",
    }
    assert report["owner_approval_generated"] is False
    assert report["synthetic_fixture_only"] is True


def test_three_independent_processes_rebuild_identical_artifacts(
    tmp_path: Path,
) -> None:
    source = str(DISTILLATION_SOURCE)
    code = (
        "import hashlib,json,sys;"
        f"sys.path.insert(0,{source!r});"
        "from pathlib import Path;"
        "from hds_distill.verification import build_phase_d02c_artifacts;"
        "a=build_phase_d02c_artifacts(Path('.'));"
        "print(json.dumps({k:hashlib.sha256(v).hexdigest() "
        "for k,v in a.items()},sort_keys=True))"
    )
    outputs: list[str] = []
    for index, seed in enumerate(("1", "73", "99991")):
        cwd = tmp_path / f"process-{index}"
        cwd.mkdir()
        environment = dict(os.environ)
        environment["PYTHONHASHSEED"] = seed
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=cwd,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        outputs.append(result.stdout.strip())
    assert outputs[0] == outputs[1] == outputs[2]


def test_checked_d02c_artifacts_are_exact_rebuild_outputs() -> None:
    rebuilt = build_phase_d02c_artifacts(REPOSITORY_ROOT)

    assert len(rebuilt) == 9
    for relative_path, expected in rebuilt.items():
        assert (REPOSITORY_ROOT / relative_path).read_bytes() == expected


def test_interpreter_has_no_unsafe_or_external_imports_and_no_dynamic_exec() -> None:
    interpreter_path = DISTILLATION_SOURCE / "hds_distill" / "interpreter.py"
    tree = ast.parse(interpreter_path.read_text(encoding="utf-8"))
    imported_roots: set[str] = set()
    called_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(
                alias.name.split(".", maxsplit=1)[0] for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            if node.module:
                imported_roots.add(node.module.split(".", maxsplit=1)[0])
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called_names.add(node.func.id)

    assert imported_roots <= {
        "__future__",
        "collections",
        "dataclasses",
        "typing",
    }
    assert {"eval", "exec", "compile", "__import__"}.isdisjoint(called_names)
    source_text = interpreter_path.read_text(encoding="utf-8")
    assert "subprocess" not in source_text
    assert "socket" not in source_text
    assert "requests" not in source_text
    assert "arc3_agi_agent" not in source_text


def test_artifact_digest_summary_is_stable_in_process() -> None:
    first = build_phase_d02c_artifacts(REPOSITORY_ROOT)
    second = build_phase_d02c_artifacts(REPOSITORY_ROOT)

    assert {
        path: hashlib.sha256(payload).hexdigest() for path, payload in first.items()
    } == {path: hashlib.sha256(payload).hexdigest() for path, payload in second.items()}
    assert (
        json.loads(first["distillation/artifacts/reports/causal_ir_conformance.json"])[
            "phase_id"
        ]
        == "PH-D02C"
    )
