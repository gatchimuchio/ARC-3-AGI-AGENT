from __future__ import annotations

from dataclasses import dataclass

import pytest

from arc3_agi_agent.compiled_policy import CompiledAutonomousInstructionBody
from arc3_agi_agent.generic_compute import HybridRelationalInstructionBody
from arc3_agi_agent.generic_session import (
    CognitiveSession,
    ResourceContract,
    create_cognitive_session,
)
from arc3_agi_agent.identity_boundary import IdentityBoundary
from arc3_agi_agent.product_capability import (
    PRODUCT_CAPABILITY_PROGRAM_ID,
    load_product_initial_state,
)
from arc3_agi_agent.product_runner import (
    ARC3_DEVELOPMENT_ACTION_BUDGET,
    ARC3_KNOWN_SUCCESS_ACTION_CEILING,
    create_product_session,
    product_process_exit_code,
    run_arc3_completion_product,
)
from arc3_agi_agent.runtime_identity import build_runtime_identity


@dataclass(frozen=True)
class _EnvironmentInfo:
    game_id: str


class _Session:
    def close(self) -> None:
        return None


class _Environment:
    def __init__(self, game_id: str) -> None:
        self.game_id = game_id
        self._session = _Session()


class _Arcade:
    def __init__(self) -> None:
        self.game_ids = ("sample-a", "sample-b")

    def get_environments(self) -> list[_EnvironmentInfo]:
        return [_EnvironmentInfo(game_id=value) for value in self.game_ids]

    def open_scorecard(self, *, tags: list[str]) -> str:
        assert tags == ["agent", "genericagi", "sequential"]
        return "product-card"

    def make(
        self,
        game_id: str,
        *,
        scorecard_id: str,
        save_recording: bool,
        include_frame_data: bool,
    ) -> _Environment:
        assert scorecard_id == "product-card"
        assert save_recording is False
        assert include_frame_data is True
        return _Environment(game_id)

    def close_scorecard(self, card_id: str) -> object:
        assert card_id == "product-card"
        return object()


@dataclass(frozen=True)
class _RuntimeReport:
    actions_executed: int
    progress_count: int
    final_state: str = "WIN"
    stop_reason: str = "GOAL_REACHED"


class _ProductAgent:
    progress_values: tuple[int, ...] = (91, 92)
    call_count = 0

    def __init__(self, **kwargs: object) -> None:
        assert kwargs["record"] is False
        self.runtime_report: _RuntimeReport | None = None

    def main(self) -> None:
        progress = self.progress_values[type(self).call_count]
        type(self).call_count += 1
        self.runtime_report = _RuntimeReport(
            actions_executed=128,
            progress_count=progress,
        )


def test_product_session_closes_known_budget_impossibility() -> None:
    session = create_product_session()
    initial = load_product_initial_state()

    assert ARC3_DEVELOPMENT_ACTION_BUDGET == 4096
    assert ARC3_KNOWN_SUCCESS_ACTION_CEILING == 1519
    assert ARC3_DEVELOPMENT_ACTION_BUDGET >= ARC3_KNOWN_SUCCESS_ACTION_CEILING
    assert session.resource_contract.action_budget_per_episode == 4096
    assert session.hds_config.resource_budget == 4096
    assert session.hds_config.stop_after_no_progress == 650
    assert session.instruction_body.digest() == initial.p_bundle.body.digest()
    assert session.p_ir_program == initial.p_bundle.program
    assert session.hds_config == initial.j0
    active_ids = {record.memory_id for record in session.memory.snapshot()}
    assert {record.memory_id for record in initial.m0} <= active_ids
    assert session.runtime_identity == build_runtime_identity(
        p_bundle=initial.p_bundle.body,
        p_ir_program=initial.p_bundle.program,
        hds_configuration=initial.j0,
        initial_memory_records=initial.m0,
    )


def test_product_bundle_is_compiled_identity_free_p_j0_m0() -> None:
    initial = load_product_initial_state()
    program = initial.p_bundle.program
    opcodes = {
        node.opcode
        for graph in (
            program.representation_graph,
            program.model_graph,
            program.candidate_graph,
        )
        for node in graph.nodes
    }

    assert initial.validate() == ()
    assert initial.p_bundle.compiler_report.mode == "PRODUCT"
    assert initial.p_bundle.compiler_report.selected_evidence_count == 183
    assert program.program_id == PRODUCT_CAPABILITY_PROGRAM_ID
    assert "compatibility" not in program.program_id.casefold()
    assert isinstance(initial.p_bundle.body, CompiledAutonomousInstructionBody)
    assert not isinstance(initial.p_bundle.body, HybridRelationalInstructionBody)
    assert len(initial.m0) == 8
    assert all(record.memory_id.startswith("product-seed:") for record in initial.m0)
    assert {
        "HISTORY_INPUT",
        "TEMPORAL_DIFF",
        "TRANSFORM_CANONICALIZE",
        "OBJECT_TRACK",
        "COUNTER_MODEL",
        "COMPOSE_MODEL",
        "FILTER_PRECONDITION",
        "MAKE_PROBE",
    } <= opcodes
    assert (
        IdentityBoundary().inspect_decision_context(
            program,
            initial.j0,
            initial.m0,
        )
        == ()
    )


def test_product_runner_reports_endpoint_metrics_without_false_completion() -> None:
    _ProductAgent.call_count = 0

    report = run_arc3_completion_product(
        arcade=_Arcade(),
        agent_factory=_ProductAgent,
    )

    assert report["product_id"] == "ARC3CompletionAgent"
    assert report["product_action_budget_per_game"] == 4096
    assert report["known_success_action_ceiling"] == 1519
    assert report["known_budget_impossibility"] is False
    assert report["product_game_started_count"] == 2
    assert report["product_game_win_count"] == 2
    assert report["product_level_completion_count"] == 183
    endpoint_failure_count = report["product_endpoint_failure_count"]
    assert isinstance(endpoint_failure_count, int)
    assert endpoint_failure_count > 0
    endpoint_failures = report["product_endpoint_failures"]
    assert isinstance(endpoint_failures, tuple)
    assert "PRODUCT_ADVERTISED_GAME_COUNT_MISMATCH" in endpoint_failures
    assert report["known_sample_regression_established"] is False
    assert report["product_completion_established"] is False
    assert report["product_baseline_executable"] is False
    assert report["product_status"] == "KNOWN_SAMPLE_REGRESSION_INCOMPLETE"
    assert report["product_capability_status"] == (
        "PRODUCT_CAPABILITY_BUNDLE_LOADED"
    )
    assert report["p_j0_m0_runtime_identity_bound"] is True
    assert report["compatibility_p_ir_active"] is False
    assert report["hybrid_baseline_instruction_body_active"] is False
    assert report["product_p_compiler_mode"] == "PRODUCT"
    assert report["product_p_program_id"] == PRODUCT_CAPABILITY_PROGRAM_ID


def test_product_runner_rejects_p_removal_from_the_product_path() -> None:
    def ablated_session_factory() -> CognitiveSession:
        return create_cognitive_session(
            p_bundle=HybridRelationalInstructionBody(),
            resource_contract=ResourceContract(
                action_budget_per_episode=4096,
            ),
        )

    with pytest.raises(RuntimeError, match="PRODUCT_SESSION_P_BODY_MISMATCH"):
        run_arc3_completion_product(
            arcade=_Arcade(),
            agent_factory=_ProductAgent,
            session_factory=ablated_session_factory,
        )


def test_hidden_score_incompleteness_is_not_a_competition_transport_error() -> None:
    incomplete = {"known_sample_regression_established": False}

    assert product_process_exit_code(
        mode="competition",
        report=incomplete,
    ) == 0
    assert product_process_exit_code(
        mode="offline",
        report=incomplete,
    ) == 2
