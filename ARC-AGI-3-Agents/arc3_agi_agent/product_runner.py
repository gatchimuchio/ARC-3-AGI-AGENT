"""Blocking product runner for ARC3CompletionAgent acceptance."""

from __future__ import annotations

import argparse
import json
import logging
import os
from collections.abc import Callable, Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

from arc_agi import Arcade, OperationMode  # type: ignore[import-untyped]

from .generic_competition_runner import run_sequential_competition
from .generic_hds import HDSConfiguration
from .generic_session import (
    CognitiveSession,
    ResourceContract,
    create_cognitive_session,
)
from .initial_state_compiler import InitialStateBundle
from .local_capability import active_dev_mechanism_families
from .product_capability import load_product_initial_state
from .product_governance import (
    ARC3_DEVELOPMENT_ACTION_BUDGET,
    ARC3_KNOWN_SUCCESS_ACTION_CEILING,
    ARC3_OFFICIAL_SAMPLE_GAME_TARGET,
    ARC3_OFFICIAL_SAMPLE_LEVEL_TARGET,
    ARC3_PRODUCT_ENDPOINT,
    ARC3_PRODUCT_ID,
    ARC3_PRODUCT_NO_PROGRESS_LIMIT,
)
from .product_release import (
    PRODUCT_RELEASE_STAGE,
    LoadedProductReleaseBundle,
    load_default_product_release_bundle,
    load_product_release_bundle,
)
from .runtime_identity import build_runtime_identity
from .schema import digest_object

ARC3_PRODUCT_RUNNER_VERSION = "arc3-completion-product-runner-v1.0"

logger = logging.getLogger(__name__)


def _selected_product_hds_configuration(
    *,
    initial_state: InitialStateBundle,
    action_budget: int,
) -> HDSConfiguration:
    if action_budget == initial_state.j0.resource_budget:
        return initial_state.j0
    return replace(
        initial_state.j0,
        resource_budget=action_budget,
        stop_after_no_progress=min(
            action_budget,
            ARC3_PRODUCT_NO_PROGRESS_LIMIT,
        ),
    )


def create_product_session(
    *,
    action_budget: int = ARC3_DEVELOPMENT_ACTION_BUDGET,
    mode: str = "COMPETITION",
    initial_state: InitialStateBundle | None = None,
) -> CognitiveSession:
    """Load the one compiled P/J0/M0 product identity into a new session."""

    initial = initial_state or load_product_initial_state()
    selected_j0 = _selected_product_hds_configuration(
        initial_state=initial,
        action_budget=action_budget,
    )
    return create_cognitive_session(
        p_bundle=initial.p_bundle.body,
        p_ir_program=initial.p_bundle.program,
        mode=mode,
        hds_configuration=selected_j0,
        initial_memory_records=initial.m0,
        resource_contract=ResourceContract(
            action_budget_per_episode=action_budget,
        ),
    )


def _require_product_session_binding(
    session: CognitiveSession,
    *,
    action_budget: int,
    initial_state: InitialStateBundle | None = None,
) -> None:
    """Fail closed unless the session is the packaged P/J0/M0 product."""

    initial = initial_state or load_product_initial_state()
    expected_j0 = _selected_product_hds_configuration(
        initial_state=initial,
        action_budget=action_budget,
    )
    expected_m0 = {record.memory_id: digest_object(record) for record in initial.m0}
    active_memory = {
        record.memory_id: digest_object(record) for record in session.memory.snapshot()
    }
    expected_identity = build_runtime_identity(
        p_bundle=initial.p_bundle.body,
        p_ir_program=initial.p_bundle.program,
        hds_configuration=expected_j0,
        initial_memory_records=initial.m0,
    )
    failures: list[str] = []
    if session.instruction_body.digest() != initial.p_bundle.body.digest():
        failures.append("PRODUCT_SESSION_P_BODY_MISMATCH")
    if session.p_ir_program != initial.p_bundle.program:
        failures.append("PRODUCT_SESSION_P_IR_MISMATCH")
    if session.hds_config != expected_j0:
        failures.append("PRODUCT_SESSION_J0_MISMATCH")
    if session.resource_contract.action_budget_per_episode != action_budget:
        failures.append("PRODUCT_SESSION_RESOURCE_CONTRACT_MISMATCH")
    if any(active_memory.get(key) != value for key, value in expected_m0.items()):
        failures.append("PRODUCT_SESSION_M0_MISMATCH")
    if session.runtime_identity != expected_identity:
        failures.append("PRODUCT_SESSION_RUNTIME_IDENTITY_MISMATCH")
    failures.extend(session.state_owner_violations())
    if failures:
        raise RuntimeError(";".join(sorted(set(failures))))


def run_arc3_completion_product(
    *,
    arcade: Any | None = None,
    agent_factory: Callable[..., Any] | None = None,
    session_factory: Callable[[], CognitiveSession] | None = None,
    action_budget: int = ARC3_DEVELOPMENT_ACTION_BUDGET,
    session_mode: str = "COMPETITION",
    release_bundle: LoadedProductReleaseBundle | None = None,
) -> dict[str, object]:
    """Run the one product path and evaluate the actual product endpoint."""

    if agent_factory is None:
        from agents.templates.arc3_completion_agent import ARC3CompletionAgent

        agent_factory = ARC3CompletionAgent
    selected_initial_state = (
        release_bundle.initial_state
        if release_bundle is not None
        else load_product_initial_state()
    )
    source_session_factory = session_factory
    if source_session_factory is None:

        def source_session_factory() -> CognitiveSession:
            return create_product_session(
                action_budget=action_budget,
                mode=session_mode,
                initial_state=selected_initial_state,
            )

    created_sessions: list[CognitiveSession] = []

    def selected_session_factory() -> CognitiveSession:
        session = source_session_factory()
        if not isinstance(session, CognitiveSession):
            raise TypeError("ARC3_PRODUCT_COGNITIVE_SESSION_REQUIRED")
        _require_product_session_binding(
            session,
            action_budget=action_budget,
            initial_state=selected_initial_state,
        )
        created_sessions.append(session)
        return session

    report = run_sequential_competition(
        arcade=arcade,
        agent_factory=agent_factory,
        session_factory=selected_session_factory,
    )
    if len(created_sessions) != 1:
        raise RuntimeError("ARC3_PRODUCT_SESSION_COUNT_INVALID")
    product_session = created_sessions[0]
    initial = selected_initial_state
    result_rows = report.get("results", ())
    if not isinstance(result_rows, list):
        raise TypeError("ARC3_PRODUCT_RESULT_ROWS_INVALID")
    citation_count = sum(
        int(row.get("memory_citation_count", 0))
        for row in result_rows
        if isinstance(row, dict)
    )
    citation_ids = tuple(
        sorted(
            {
                str(memory_id)
                for row in result_rows
                if isinstance(row, dict)
                for memory_id in row.get("memory_citation_ids", ())
            }
        )
    )
    product_seed_citation_ids = tuple(
        item for item in citation_ids if item.startswith("product-seed:")
    )
    active_dev_families = (
        () if release_bundle is not None else active_dev_mechanism_families()
    )
    release_families: tuple[Mapping[str, object], ...] = ()
    if release_bundle is not None:
        raw_release_families = release_bundle.mechanism_family_registry.get("families")
        if not isinstance(raw_release_families, list) or not all(
            isinstance(item, Mapping) for item in raw_release_families
        ):
            raise TypeError("ARC3_PRODUCT_RELEASE_FAMILY_REGISTRY_INVALID")
        release_families = tuple(
            {str(key): value for key, value in item.items()}
            for item in raw_release_families
        )
    action_id_counts: dict[str, int] = {}
    for row in result_rows:
        if not isinstance(row, dict):
            continue
        row_counts = row.get("action_id_counts", {})
        if not isinstance(row_counts, dict):
            raise TypeError("ARC3_PRODUCT_ACTION_ID_COUNTS_INVALID")
        for action_id, count in row_counts.items():
            key = str(action_id)
            action_id_counts[key] = action_id_counts.get(key, 0) + int(count)
    memory_causal_behavior_change_count = sum(
        int(row.get("memory_causal_behavior_change_count", 0))
        for row in result_rows
        if isinstance(row, dict)
    )
    memory_causal_witness_refs = tuple(
        sorted(
            {
                str(witness)
                for row in result_rows
                if isinstance(row, dict)
                for witness in row.get("memory_causal_witness_refs", ())
            }
        )
    )
    report.update(ARC3_PRODUCT_ENDPOINT.metrics(report))
    report.update(
        {
            "product_runner_version": ARC3_PRODUCT_RUNNER_VERSION,
            "product_capability_status": (
                "PRODUCT_RELEASE_BUNDLE_LOADED"
                if release_bundle is not None
                else "PRODUCT_CAPABILITY_BUNDLE_LOADED"
            ),
            "product_bundle_stage": (
                PRODUCT_RELEASE_STAGE if release_bundle is not None else "ACTIVE_DEV"
            ),
            "product_release_bundle_loaded": release_bundle is not None,
            "product_release_bundle_id": (
                release_bundle.descriptor.get("product_bundle_id")
                if release_bundle is not None
                else None
            ),
            "product_release_bundle_logical_digest": (
                release_bundle.logical_digest if release_bundle is not None else None
            ),
            "product_release_bundle_sha256": (
                release_bundle.package_sha256 if release_bundle is not None else None
            ),
            "product_initial_state_logical_digest": initial.logical_digest,
            "product_p_logical_digest": initial.p_bundle.logical_digest(),
            "product_p_program_id": initial.p_bundle.program.program_id,
            "product_p_body_format": initial.p_bundle.body.format_id(),
            "product_p_body_version": initial.p_bundle.body.body_version(),
            "product_p_compiler_mode": (initial.p_bundle.compiler_report.mode),
            "product_bundle_j0_digest": "j0:" + digest_object(initial.j0),
            "product_j0_digest": ("j0:" + digest_object(product_session.hds_config)),
            "product_m0_digest": "m0:" + digest_object(initial.m0),
            "product_m0_record_count": len(initial.m0),
            "product_runtime_identity_digest": (
                product_session.runtime_identity.digest()
            ),
            "p_j0_m0_runtime_identity_bound": True,
            "product_memory_citation_count": citation_count,
            "product_memory_citation_ids": citation_ids,
            "product_teacher_seed_citation_count": len(product_seed_citation_ids),
            "product_teacher_seed_citation_ids": (product_seed_citation_ids),
            "product_teacher_structure_cited": bool(product_seed_citation_ids),
            "product_active_dev_mechanism_family_count": len(active_dev_families),
            "product_active_dev_mechanism_family_ids": tuple(
                family.family_id for family in active_dev_families
            ),
            "product_active_dev_mechanism_family_digests": tuple(
                family.logical_digest() for family in active_dev_families
            ),
            "product_release_frozen_mechanism_family_count": len(release_families),
            "product_release_frozen_mechanism_family_ids": tuple(
                str(family.get("family_id")) for family in release_families
            ),
            "product_release_frozen_mechanism_family_digests": tuple(
                str(family.get("release_logical_digest")) for family in release_families
            ),
            "product_action_id_counts": {
                action_id: action_id_counts[action_id]
                for action_id in sorted(
                    action_id_counts,
                    key=int,
                )
            },
            "product_memory_causal_behavior_change_count": (
                memory_causal_behavior_change_count
            ),
            "product_memory_causal_witness_refs": (memory_causal_witness_refs),
            "compatibility_p_ir_active": False,
            "hybrid_baseline_instruction_body_active": False,
        }
    )
    return report


def _default_environments_dir() -> Path:
    candidates = (
        Path(__file__).resolve().parents[2] / "environment_files",
        Path.cwd() / "environment_files",
        Path.cwd().parent / "environment_files",
    )
    return next(
        (candidate for candidate in candidates if candidate.is_dir()),
        candidates[0],
    )


def _selected_offline_environments(
    arcade: Arcade,
    requested_games: tuple[str, ...],
) -> tuple[Any, ...]:
    environments = tuple(
        sorted(arcade.get_environments(), key=lambda item: item.game_id)
    )
    if not requested_games:
        return environments
    by_id = {item.game_id.casefold(): item for item in environments}
    by_title = {item.title.casefold(): item for item in environments}
    selected: list[Any] = []
    selected_ids: set[str] = set()
    for requested in requested_games:
        key = requested.casefold()
        environment = by_id.get(key) or by_title.get(key)
        if environment is None:
            raise ValueError(f"ARC3_PRODUCT_UNKNOWN_OFFLINE_GAME:{requested}")
        if environment.game_id not in selected_ids:
            selected.append(environment)
            selected_ids.add(environment.game_id)
    return tuple(selected)


class _SelectedOfflineArcade:
    """Orchestration-only diagnostic selection over one official Arcade."""

    def __init__(self, arcade: Arcade, environments: tuple[Any, ...]) -> None:
        self._arcade = arcade
        self._environments = environments

    def get_environments(self) -> list[Any]:
        return list(self._environments)

    def open_scorecard(self, *, tags: list[str]) -> str:
        return cast(str, self._arcade.open_scorecard(tags=tags))

    def make(
        self,
        game_id: str,
        *,
        scorecard_id: str,
        save_recording: bool,
        include_frame_data: bool,
    ) -> object | None:
        return cast(
            object | None,
            self._arcade.make(
                game_id,
                scorecard_id=scorecard_id,
                save_recording=save_recording,
                include_frame_data=include_frame_data,
            ),
        )

    def close_scorecard(self, card_id: str) -> object | None:
        return cast(object | None, self._arcade.close_scorecard(card_id))


def run_arc3_completion_offline(
    *,
    environments_dir: Path,
    requested_games: tuple[str, ...] = (),
    recordings_dir: Path | None = None,
    action_budget: int = ARC3_DEVELOPMENT_ACTION_BUDGET,
    release_bundle: LoadedProductReleaseBundle | None = None,
) -> dict[str, object]:
    """Run the product C/J/M/P path against official bundled environments."""

    resolved_environments_dir = environments_dir.resolve()
    if not resolved_environments_dir.is_dir():
        raise FileNotFoundError(
            "ARC3_PRODUCT_ENVIRONMENT_DIRECTORY_MISSING:"
            + str(resolved_environments_dir)
        )
    if os.getenv("OPERATION_MODE", "").strip().casefold() == "competition":
        raise PermissionError("ARC3_PRODUCT_OFFLINE_COMPETITION_ENV_FORBIDDEN")
    output_dir = (
        recordings_dir.resolve()
        if recordings_dir is not None
        else resolved_environments_dir.parent / "recordings" / "product-rev4"
    )
    arcade = Arcade(
        operation_mode=OperationMode.OFFLINE,
        environments_dir=str(resolved_environments_dir),
        recordings_dir=str(output_dir),
    )
    if arcade.operation_mode is not OperationMode.OFFLINE:
        raise RuntimeError("ARC3_PRODUCT_OFFLINE_MODE_NOT_EFFECTIVE")
    available_count = len(arcade.get_environments())
    selected = _selected_offline_environments(arcade, requested_games)
    report = run_arc3_completion_product(
        arcade=_SelectedOfflineArcade(arcade, selected),
        action_budget=action_budget,
        session_mode="VALIDATION",
        release_bundle=release_bundle,
    )
    report.update(
        {
            "operation_mode": arcade.operation_mode.value,
            "offline_environment_available_count": available_count,
            "offline_environment_selected_count": len(selected),
            "offline_environment_source": "BUNDLED_OFFICIAL_SAMPLES",
        }
    )
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the endpoint-driven ARC3CompletionAgent product."
    )
    parser.add_argument(
        "--mode",
        choices=("offline", "competition"),
        default="offline",
    )
    parser.add_argument(
        "--environments-dir",
        type=Path,
        default=_default_environments_dir(),
    )
    parser.add_argument("--recordings-dir", type=Path)
    parser.add_argument("--game", action="append", default=[])
    parser.add_argument(
        "--action-budget",
        type=int,
        default=ARC3_DEVELOPMENT_ACTION_BUDGET,
    )
    parser.add_argument("--report", type=Path)
    parser.add_argument("--release-descriptor", type=Path)
    parser.add_argument("--release-bundle", type=Path)
    parser.add_argument("--release-frozen", action="store_true")
    return parser


def product_process_exit_code(
    *,
    mode: str,
    report: dict[str, object],
) -> int:
    """Keep hidden score incompleteness distinct from transport failure."""

    if mode not in {"offline", "competition"}:
        raise ValueError("ARC3_PRODUCT_PROCESS_MODE_INVALID")
    if mode == "competition":
        return 0
    return 0 if report.get("known_sample_regression_established") is True else 2


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    arguments = _parser().parse_args()
    if (arguments.release_descriptor is None) != (arguments.release_bundle is None):
        raise ValueError("ARC3_PRODUCT_RELEASE_ARTIFACT_PAIR_REQUIRED")
    if arguments.release_frozen and arguments.release_descriptor is not None:
        raise ValueError("ARC3_PRODUCT_RELEASE_SELECTION_AMBIGUOUS")
    release_bundle = (
        load_default_product_release_bundle()
        if arguments.release_frozen
        else (
            load_product_release_bundle(
                descriptor_path=arguments.release_descriptor,
                package_path=arguments.release_bundle,
            )
            if arguments.release_descriptor is not None
            and arguments.release_bundle is not None
            else None
        )
    )
    if arguments.mode == "offline":
        report = run_arc3_completion_offline(
            environments_dir=arguments.environments_dir,
            requested_games=tuple(arguments.game),
            recordings_dir=arguments.recordings_dir,
            action_budget=arguments.action_budget,
            release_bundle=release_bundle,
        )
    else:
        if arguments.game:
            raise ValueError("ARC3_PRODUCT_COMPETITION_GAME_FILTER_FORBIDDEN")
        report = run_arc3_completion_product(
            action_budget=arguments.action_budget,
            release_bundle=release_bundle,
        )
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    print(encoded)
    if arguments.report is not None:
        arguments.report.parent.mkdir(parents=True, exist_ok=True)
        arguments.report.write_text(
            encoded + "\n",
            encoding="utf-8",
            newline="\n",
        )
    # The official scorecard, rather than local sample completion, owns the
    # hidden result. Do not turn a closed competition run into a system error
    # merely because hidden games differ from the local sample endpoint.
    return product_process_exit_code(
        mode=str(arguments.mode),
        report=report,
    )


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ARC3_DEVELOPMENT_ACTION_BUDGET",
    "ARC3_KNOWN_SUCCESS_ACTION_CEILING",
    "ARC3_OFFICIAL_SAMPLE_GAME_TARGET",
    "ARC3_OFFICIAL_SAMPLE_LEVEL_TARGET",
    "ARC3_PRODUCT_ID",
    "ARC3_PRODUCT_RUNNER_VERSION",
    "create_product_session",
    "product_process_exit_code",
    "run_arc3_completion_offline",
    "run_arc3_completion_product",
]
