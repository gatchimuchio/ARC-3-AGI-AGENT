from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from arc3_agi_agent.generic_compute import (
    ParametricRelationalInstructionBody,
)
from arc3_agi_agent.generic_env import MechanismWorld
from arc3_agi_agent.generic_runtime import GenericAGIRuntime
from arc3_agi_agent.generic_session import (
    ResourceContract,
    create_cognitive_session,
)
from arc3_agi_agent.generic_types import GenericObservation
from arc3_agi_agent.p_ir import (
    compatibility_p_ir_program,
    p_ir_program_from_dict,
    p_ir_program_logical_digest,
    p_ir_program_to_dict,
)
from arc3_agi_agent.p_ir_abi import L0_ABI_VERSION
from arc3_agi_agent.p_ir_interpreter import (
    FixedL0PIRInterpreter,
    PIRExecutionContext,
)
from arc3_agi_agent.p_ir_types import PIRNode, TypedDAG
from arc3_agi_agent.p_ir_validator import (
    require_valid_p_ir_program,
    validate_p_ir_program,
)
from arc3_agi_agent.taint import COORDINATE_PROVENANCE_CURRENT_RENDER


def _observation() -> GenericObservation:
    return GenericObservation(
        signature="p20a-observation",
        available_actions=(11, 29),
        rendered_layers=(
            (
                (0, 0, 0, 0, 0),
                (0, 2, 2, 0, 0),
                (0, 2, 2, 0, 3),
                (0, 0, 0, 0, 3),
                (0, 0, 0, 0, 0),
            ),
        ),
        terminal_state="NOT_FINISHED",
        action_payload_schema=((29, ("x", "y")),),
    )


def _replace_representation_node(
    node_id: str,
    replacement: PIRNode,
) -> object:
    program = compatibility_p_ir_program()
    graph = program.representation_graph
    nodes = tuple(
        replacement if item.node_id == node_id else item
        for item in graph.nodes
    )
    return replace(program, representation_graph=replace(graph, nodes=nodes))


def test_same_l0_two_representation_programs() -> None:
    interpreter = FixedL0PIRInterpreter()
    context = PIRExecutionContext(
        observation=_observation(),
        goal_tokens=("goal:progress",),
    )
    spatial = interpreter.execute(
        compatibility_p_ir_program(projection_mode="spatial-relational"),
        context,
    )
    minimal = interpreter.execute(
        compatibility_p_ir_program(projection_mode="topology-minimal"),
        context,
    )

    assert interpreter.interpreter_version == "arc3-p-ir-interpreter-v1"
    assert spatial.representation.digest_value != minimal.representation.digest_value
    assert spatial.program_logical_digest != minimal.program_logical_digest
    assert spatial.action_bindings == minimal.action_bindings


def test_representation_change_changes_compute() -> None:
    reports = []
    for mode in ("spatial-relational", "topology-minimal"):
        session = create_cognitive_session(
            p_bundle=ParametricRelationalInstructionBody(),
            p_ir_program=compatibility_p_ir_program(projection_mode=mode),
            resource_contract=ResourceContract(action_budget_per_episode=4),
        )
        runtime = GenericAGIRuntime(
            MechanismWorld((11, 29), (0,), required_progress=1),
            session,
            session.begin_episode(),
        )
        reports.append(runtime.run())

    first = reports[0].cycles[0].compute_result
    second = reports[1].cycles[0].compute_result
    assert first.representation.digest_value != second.representation.digest_value
    assert first.p_ir_logical_digest != second.p_ir_logical_digest
    assert first.digest() != second.digest()


def test_unknown_opcode_rejected() -> None:
    program = compatibility_p_ir_program()
    original = program.representation_graph.nodes[0]
    invalid = _replace_representation_node(
        original.node_id,
        replace(original, opcode="ARBITRARY_PYTHON"),
    )

    with pytest.raises(ValueError, match="P_IR_UNKNOWN_OPCODE"):
        require_valid_p_ir_program(invalid)  # type: ignore[arg-type]


def test_type_mismatch_rejected() -> None:
    program = compatibility_p_ir_program()
    original = program.representation_graph.nodes[0]
    invalid = _replace_representation_node(
        original.node_id,
        replace(original, output_type="Mask"),
    )

    failures = validate_p_ir_program(invalid)  # type: ignore[arg-type]
    assert any("P_IR_OUTPUT_TYPE_MISMATCH" in item for item in failures)
    assert any("P_IR_TYPE_MISMATCH" in item for item in failures)


def test_p_ir_typecheck() -> None:
    assert validate_p_ir_program(compatibility_p_ir_program()) == ()


def test_cycle_rejected() -> None:
    program = compatibility_p_ir_program()
    original = program.representation_graph.nodes[0]
    invalid = _replace_representation_node(
        original.node_id,
        replace(original, inputs=("objects",)),
    )

    failures = validate_p_ir_program(invalid)  # type: ignore[arg-type]
    assert "P_IR_GRAPH_CYCLE:representation.v1" in failures


def test_resource_bound_rejected() -> None:
    program = compatibility_p_ir_program()
    invalid = replace(
        program,
        resource_manifest=replace(program.resource_manifest, max_nodes=1),
    )

    with pytest.raises(
        ValueError,
        match="P_IR_RESOURCE_MAX_NODES_EXCEEDED",
    ):
        require_valid_p_ir_program(invalid)


def test_dynamic_coordinate_opcode() -> None:
    observation = _observation()
    result = FixedL0PIRInterpreter().execute(
        compatibility_p_ir_program(),
        PIRExecutionContext(
            observation=observation,
            goal_tokens=("goal:progress",),
        ),
    )
    coordinate_bindings = tuple(
        item for item in result.action_bindings if item.payload_items
    )

    assert coordinate_bindings
    assert all(
        item.coordinate_provenance
        == COORDINATE_PROVENANCE_CURRENT_RENDER
        for item in coordinate_bindings
    )
    assert all(item.validate(observation) == () for item in coordinate_bindings)


def test_no_arbitrary_python() -> None:
    program = compatibility_p_ir_program()
    graph = program.representation_graph
    node = graph.nodes[-1]
    contaminated = replace(
        node,
        parameters=(
            ("projection_mode", "spatial-relational"),
            ("python", "__import__('os').system('id')"),
        ),
    )
    invalid_graph = TypedDAG(
        graph_id=graph.graph_id,
        graph_kind=graph.graph_kind,
        nodes=(*graph.nodes[:-1], contaminated),
        outputs=graph.outputs,
    )
    invalid = replace(program, representation_graph=invalid_graph)

    failures = validate_p_ir_program(invalid)
    assert any("P_IR_ARBITRARY_CODE_SURFACE" in item for item in failures)


def test_abi_mismatch_rejected() -> None:
    program = compatibility_p_ir_program()
    invalid = replace(program, l0_abi_version="arc3-l0-abi-v999")

    assert L0_ABI_VERSION == "arc3-l0-abi-v1"
    with pytest.raises(ValueError, match="P_IR_ABI_VERSION_UNSUPPORTED"):
        require_valid_p_ir_program(invalid)


def test_interpreter_deterministic() -> None:
    program = compatibility_p_ir_program()
    context = PIRExecutionContext(
        observation=_observation(),
        goal_tokens=("goal:progress",),
    )
    interpreter = FixedL0PIRInterpreter()

    first = interpreter.execute(program, context)
    second = interpreter.execute(program, context)
    restored = p_ir_program_from_dict(p_ir_program_to_dict(program))

    assert first == second
    assert first.execution_digest == second.execution_digest
    assert restored == program
    assert p_ir_program_logical_digest(restored) == (
        p_ir_program_logical_digest(program)
    )


def test_p20a_phase_state_is_content_bound() -> None:
    root = Path(__file__).resolve().parents[3]
    path = root / "control" / "p20a" / "P20A_PHASE_STATE.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    expected_digest = data.pop("content_digest")
    actual_digest = hashlib.sha256(
        json.dumps(
            data,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    assert expected_digest == actual_digest
    assert data["status"] == "PASS"
    assert data["failed_requirement_ids"] == []
    assert set(data["gates"].values()) == {"PASS"}
    assert data["metrics"]["arbitrary_code_surface"] == 0
    assert data["metrics"]["representation_swappable"] is True
