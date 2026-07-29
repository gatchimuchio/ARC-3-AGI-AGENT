from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from arc3_agi_agent.authority_state import AuthorityState
from arc3_agi_agent.canonical_artifact import (
    build_canonical_zip,
    logical_digest,
    physical_digest,
)
from arc3_agi_agent.generic_compute import ParametricRelationalInstructionBody
from arc3_agi_agent.generic_env import MechanismWorld
from arc3_agi_agent.generic_memory import (
    MemoryMutationProposal,
    SemanticMemory,
    semantic_record,
)
from arc3_agi_agent.generic_session import (
    CognitiveSession,
    ResourceContract,
    create_cognitive_session,
)
from arc3_agi_agent.memory_backend import (
    MEMORY_BACKEND_SCHEMA_VERSION,
    InMemoryBackend,
    SQLiteEventBackend,
)
from arc3_agi_agent.memory_image import MemoryImage
from arc3_agi_agent.schema import canonical_json


def _session_and_decision(
    backend: InMemoryBackend | SQLiteEventBackend,
    *,
    max_active: int = 2048,
):
    session = create_cognitive_session(
        p_bundle=ParametricRelationalInstructionBody(),
        resource_contract=ResourceContract(action_budget_per_episode=8),
        memory_backend=backend,
    )
    session.memory.max_active = max_active
    session.begin_episode()
    observation = MechanismWorld(
        (11,),
        (0,),
        required_progress=1,
    ).observe()
    memory_view = session.memory.view()
    frame = session.hds.frame(
        observation,
        memory_view,
        remaining_budget=8,
    )
    command = session.hds.issue_compute(frame, observation, memory_view)
    result = session.compute.compute(
        command=command,
        observation=observation,
        memory=session.memory,
        instruction_body=session.instruction_body,
    )
    decision = session.hds.judge(
        frame=frame,
        observation=observation,
        result=result,
    )
    assert decision.memory_update_authorized is True
    return session, decision


def _proposal(identifier: str) -> MemoryMutationProposal:
    record = semantic_record(
        memory_id=identifier,
        kind="HYPOTHESIS",
        statement=f"atomic hypothesis {identifier}",
        semantic_tokens=("goal:progress", f"test:{identifier}"),
        evidence=(f"event:{identifier}",),
        counter_evidence=("counter:none-observed",),
        scope=("p18-test",),
        falsification_condition="a later event contradicts this hypothesis",
    )
    return MemoryMutationProposal(
        operation="ADD",
        target_id=identifier,
        record=record,
        evidence=record.evidence,
        counter_evidence=record.counter_evidence,
        scope=record.scope,
        falsification_condition=record.falsification_condition,
        reason="exercise atomic memory",
    )


def _stage(
    session: CognitiveSession,
    decision: object,
    proposals: tuple[MemoryMutationProposal, ...],
    *,
    idempotency_key: str,
):
    authorizations = tuple(
        session.hds.authorize_memory(
            decision,  # type: ignore[arg-type]
            proposal,
            memory_version=session.memory.version,
        )
        for proposal in proposals
    )
    return session.memory.prepare_batch(
        expected_version=session.memory.version,
        proposals=proposals,
        authorizations=authorizations,
        idempotency_key=idempotency_key,
    )


def test_prepare_has_no_live_side_effect() -> None:
    backend = InMemoryBackend()
    session, decision = _session_and_decision(backend)
    before = session.memory.view()
    staged = _stage(
        session,
        decision,
        (_proposal("prepare-only"),),
        idempotency_key="prepare-only",
    )

    assert session.memory.view().digest == before.digest
    assert session.memory.version == before.version
    assert backend.events() == ()
    assert staged.next_image.digest() != backend.current_image().digest()


def test_max_active_failure_is_atomic() -> None:
    backend = InMemoryBackend()
    session, decision = _session_and_decision(backend, max_active=1)
    before = session.memory.view()

    with pytest.raises(
        RuntimeError,
        match="SEMANTIC_MEMORY_ACTIVE_BUDGET_EXCEEDED",
    ):
        _stage(
            session,
            decision,
            (_proposal("alpha"), _proposal("beta")),
            idempotency_key="max-active-failure",
        )

    assert session.memory.view().digest == before.digest
    assert backend.events() == ()


def test_backend_failure_preserves_live_digest() -> None:
    backend = InMemoryBackend(fault_phase="AFTER_EVENT_STAGE")
    session, decision = _session_and_decision(backend)
    before = session.memory.view()
    staged = _stage(
        session,
        decision,
        (_proposal("backend-failure"),),
        idempotency_key="backend-failure",
    )

    with pytest.raises(RuntimeError, match="AFTER_EVENT_STAGE"):
        session.memory.commit_prepared(staged)

    assert session.memory.view().digest == before.digest
    assert backend.events() == ()
    backend.set_fault(None)
    receipts = session.memory.commit_prepared(staged)
    assert len(receipts) == 1


def test_event_and_state_atomic_commit() -> None:
    backend = InMemoryBackend()
    session, decision = _session_and_decision(backend)
    staged = _stage(
        session,
        decision,
        (_proposal("batch-a"), _proposal("batch-b")),
        idempotency_key="atomic-batch",
    )

    receipts = session.memory.commit_prepared(staged)

    assert session.memory.version == 1
    assert len(session.memory.view().active) == 2
    assert len(session.memory.event_ledger()) == 1
    assert len(session.memory.provenance()) == 2
    assert len(receipts) == 2
    assert len({item.event_digest for item in receipts}) == 1
    assert backend.current_image().digest() == staged.next_image.digest()


def test_idempotent_replay() -> None:
    backend = InMemoryBackend()
    session, decision = _session_and_decision(backend)
    staged = _stage(
        session,
        decision,
        (_proposal("idempotent"),),
        idempotency_key="idempotent",
    )
    first = session.memory.commit_prepared(staged)
    second = session.memory.commit_prepared(staged)
    backend_replay = backend.commit(
        expected_version=staged.expected_version,
        event_batch=staged.event_batch,
        next_image=staged.next_image,
        idempotency_key=staged.idempotency_key,
    )

    assert first == second
    assert session.memory.version == 1
    assert len(backend.events()) == 1
    assert backend_replay.idempotent_replay is True


def test_crash_after_prepare(tmp_path: Path) -> None:
    path = tmp_path / "after-prepare.sqlite3"
    backend = SQLiteEventBackend(path)
    session, decision = _session_and_decision(backend)
    before = session.memory.view()
    _stage(
        session,
        decision,
        (_proposal("prepared-not-committed"),),
        idempotency_key="prepared-not-committed",
    )
    backend.close()

    restarted_backend = SQLiteEventBackend(path)
    restarted = SemanticMemory(
        AuthorityState("restart-after-prepare"),
        backend=restarted_backend,
    )

    assert restarted.view().digest == before.digest
    assert restarted.event_ledger() == ()
    restarted_backend.close()


def test_crash_during_commit(tmp_path: Path) -> None:
    path = tmp_path / "during-commit.sqlite3"
    backend = SQLiteEventBackend(path, fault_phase="AFTER_EVENT_STAGE")
    session, decision = _session_and_decision(backend)
    before = session.memory.view()
    staged = _stage(
        session,
        decision,
        (_proposal("crash-during-commit"),),
        idempotency_key="crash-during-commit",
    )

    with pytest.raises(RuntimeError, match="AFTER_EVENT_STAGE"):
        session.memory.commit_prepared(staged)
    backend.close()

    restarted_backend = SQLiteEventBackend(path)
    restarted = SemanticMemory(
        AuthorityState("restart-during-commit"),
        backend=restarted_backend,
    )
    assert restarted.view().digest == before.digest
    assert restarted.event_ledger() == ()
    restarted_backend.close()


def test_restart_rebuild_from_ledger(tmp_path: Path) -> None:
    path = tmp_path / "restart.sqlite3"
    backend = SQLiteEventBackend(path)
    session, decision = _session_and_decision(backend)
    staged = _stage(
        session,
        decision,
        (_proposal("restart-a"), _proposal("restart-b")),
        idempotency_key="restart-batch",
    )
    session.memory.commit_prepared(staged)
    expected_view = session.memory.view()
    expected_image = backend.current_image()
    expected_events = tuple(
        item.digest() for item in backend.events()
    )
    backend.close()

    restarted_backend = SQLiteEventBackend(path)
    restarted = SemanticMemory(
        AuthorityState("restart-ledger"),
        backend=restarted_backend,
    )

    assert restarted.view().digest == expected_view.digest
    assert restarted_backend.rebuild().digest() == expected_image.digest()
    assert tuple(
        item.digest() for item in restarted.event_ledger()
    ) == expected_events
    restarted_backend.close()


def test_checkpoint_rebuild() -> None:
    backend = InMemoryBackend(
        checkpoint_interval=2,
        retained_checkpoints=2,
    )
    session, decision = _session_and_decision(backend)
    for index in range(5):
        proposal = _proposal(f"checkpoint-{index}")
        authorization = session.hds.authorize_memory(
            decision,
            proposal,
            memory_version=session.memory.version,
        )
        session.memory.apply_authorized(proposal, authorization)

    rebuilt = backend.rebuild()

    assert rebuilt.digest() == backend.current_image().digest()
    assert backend.checkpoint_count() == 2
    assert backend.full_copy_snapshot_count() < session.memory.version
    assert session.memory.full_copy_snapshot_per_version is False


def test_schema_migration(tmp_path: Path) -> None:
    path = tmp_path / "legacy.sqlite3"
    image = MemoryImage.empty()
    SQLiteEventBackend.create_legacy_v0(path, image)

    backend = SQLiteEventBackend(path)

    assert backend.migration_applied is True
    assert backend.schema_version == MEMORY_BACKEND_SCHEMA_VERSION
    assert backend.current_image().digest() == image.digest()
    assert backend.journal_mode == "WAL"
    backend.close()


def test_nan_inf_rejected() -> None:
    with pytest.raises(ValueError):
        canonical_json({"value": float("nan")})
    with pytest.raises(ValueError):
        canonical_json({"value": float("inf")})

    memory = SemanticMemory(AuthorityState("non-finite"))
    invalid = semantic_record(
        memory_id="invalid-float",
        kind="HYPOTHESIS",
        statement="non-finite payload must be rejected",
        semantic_tokens=("test:non-finite",),
        evidence=("test",),
        falsification_condition="always invalid",
        payload={"value": float("-inf")},
    )
    with pytest.raises(ValueError):
        memory.seed_active((invalid,))


def test_logical_and_package_digest_separated() -> None:
    logical_value = {"program": ["OBSERVE", "PREDICT"], "version": 1}
    logical = logical_digest(logical_value)
    first_package = build_canonical_zip(
        {"manifest.json": canonical_json(logical_value).encode("utf-8")}
    )
    repeated_package = build_canonical_zip(
        {"manifest.json": canonical_json(logical_value).encode("utf-8")}
    )
    expanded_package = build_canonical_zip(
        {
            "audit.txt": b"physical-only audit member",
            "manifest.json": canonical_json(logical_value).encode("utf-8"),
        }
    )

    assert first_package == repeated_package
    assert logical == logical_digest(logical_value)
    assert physical_digest(first_package) != physical_digest(expanded_package)
    assert logical != physical_digest(first_package)


def test_p18_phase_state_is_content_bound() -> None:
    root = Path(__file__).resolve().parents[3]
    path = root / "control" / "p18" / "P18_PHASE_STATE.json"
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
    assert data["metrics"]["cross_game_semantic_promotion"] == "DISABLED"
