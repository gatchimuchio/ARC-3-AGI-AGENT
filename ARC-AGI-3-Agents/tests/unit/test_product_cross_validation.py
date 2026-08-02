from __future__ import annotations

import pytest

from arc3_agi_agent.product_capability import load_product_initial_state
from arc3_agi_agent.product_cross_validation import (
    PRODUCT_CV_ACTION_BUDGET,
    PRODUCT_CV_FOLD_COUNT,
    PRODUCT_CV_GAME_COUNT,
    PRODUCT_CV_NO_PROGRESS_LIMIT,
    create_product_cv_session,
    product_cv_partition,
)
from arc3_agi_agent.product_runner import create_product_session


def test_product_cv_partition_is_disjoint_and_complete() -> None:
    all_holdouts: list[int] = []
    for fold_index in range(PRODUCT_CV_FOLD_COUNT):
        training, holdout = product_cv_partition(fold_index)

        assert len(training) == 20
        assert len(holdout) == 5
        assert not set(training).intersection(holdout)
        assert set(training).union(holdout) == set(range(PRODUCT_CV_GAME_COUNT))
        all_holdouts.extend(holdout)

    assert sorted(all_holdouts) == list(range(PRODUCT_CV_GAME_COUNT))


@pytest.mark.parametrize("fold_index", [-1, 5, True])
def test_product_cv_partition_rejects_invalid_fold(fold_index: int) -> None:
    with pytest.raises(ValueError, match="PRODUCT_CV_FOLD_INDEX_INVALID"):
        product_cv_partition(fold_index)


def test_product_cv_session_preserves_product_j0_m0_stack() -> None:
    initial = load_product_initial_state()

    cv_session = create_product_cv_session(
        initial.p_bundle,
        action_budget=PRODUCT_CV_ACTION_BUDGET,
        no_progress_limit=PRODUCT_CV_NO_PROGRESS_LIMIT,
    )
    product_session = create_product_session(
        action_budget=PRODUCT_CV_ACTION_BUDGET,
        mode="VALIDATION",
    )

    assert cv_session.instruction_body.digest() == initial.p_bundle.body.digest()
    assert cv_session.p_ir_program == initial.p_bundle.program
    assert cv_session.hds_config.resource_budget == PRODUCT_CV_ACTION_BUDGET
    assert cv_session.hds_config.stop_after_no_progress == PRODUCT_CV_NO_PROGRESS_LIMIT
    assert cv_session.runtime_identity == product_session.runtime_identity
    assert cv_session.state_owner_violations() == ()
