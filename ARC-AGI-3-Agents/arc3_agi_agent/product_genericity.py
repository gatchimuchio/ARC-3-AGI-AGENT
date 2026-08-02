"""Executable development genericity checks for the active product identity."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

from .generic_env import TRANSFORMATION_FAMILIES, transformed_worlds
from .generic_runtime import GenericAGIRuntime
from .product_capability import load_product_initial_state
from .product_runner import create_product_session
from .schema import digest_object

PRODUCT_GENERICITY_SCHEMA_VERSION: Final = (
    "arc3-product-active-genericity-v1"
)
PRODUCT_GENERICITY_DIGEST_PREFIX: Final = "arc3-product-active-genericity:"
PRODUCT_TRANSFORMATION_ACTION_BUDGET: Final = 24


def run_active_product_transformation_evaluation(
    *,
    seed: int = 0,
    action_budget: int = PRODUCT_TRANSFORMATION_ACTION_BUDGET,
    output_path: Path | None = None,
) -> dict[str, object]:
    """Run the packaged P/J0/M0 identity in seven semantic micro-worlds."""

    initial = load_product_initial_state()
    session = create_product_session(
        action_budget=action_budget,
        mode="VALIDATION",
    )
    runtime_identity_digest = session.runtime_identity.digest()
    p_body_digest = session.instruction_body.digest()
    results: list[dict[str, object]] = []
    for family, world in transformed_worlds(seed=seed):
        handle = session.begin_episode()
        report = GenericAGIRuntime(
            world,
            session,
            handle,
        ).run()
        receipt = session.end_episode(
            handle,
            succeeded=report.final_state == "WIN",
            reason=report.stop_reason,
        )
        results.append(
            {
                "family": family,
                "environment_executed": True,
                "completed": report.final_state == "WIN",
                "final_state": report.final_state,
                "progress_count": report.progress_count,
                "actions_executed": report.actions_executed,
                "stop_reason": report.stop_reason,
                "failure_signatures": report.failure_signatures,
                "identity_boundary_passed": report.identity_boundary_passed,
                "runtime_identity_digest": report.runtime_identity_digest,
                "run_report_digest": report.digest(),
                "memory_promoted": receipt.promoted,
            }
        )
    completed = sum(bool(item["completed"]) for item in results)
    same_runtime_identity = all(
        item["runtime_identity_digest"] == runtime_identity_digest
        for item in results
    )
    identity_boundary_passed = all(
        item["identity_boundary_passed"] is True for item in results
    )
    product_identity_bound = (
        p_body_digest == initial.p_bundle.body.digest()
        and session.p_ir_program == initial.p_bundle.program
        and session.state_owner_violations() == ()
    )
    passed = (
        len(results) == len(TRANSFORMATION_FAMILIES)
        and completed == len(TRANSFORMATION_FAMILIES)
        and same_runtime_identity
        and identity_boundary_passed
        and product_identity_bound
    )
    body: dict[str, object] = {
        "schema_version": PRODUCT_GENERICITY_SCHEMA_VERSION,
        "evaluation_role": "DEVELOPMENT_SEMANTIC_TRANSFORMATION",
        "allowed_claim": "ACTIVE_PRODUCT_TRANSFORMATION_STRESS",
        "final_generic_claim": "NOT_AUTHORIZED",
        "locked_evaluator": False,
        "evaluator_known_to_developer": True,
        "seed": seed,
        "action_budget_per_environment": action_budget,
        "product_initial_state_logical_digest": initial.logical_digest,
        "active_p_body_digest": p_body_digest,
        "active_p_program_logical_digest": (
            initial.p_bundle.manifest.program_logical_digest
        ),
        "runtime_identity_digest": runtime_identity_digest,
        "same_runtime_identity_for_all_environments": same_runtime_identity,
        "product_p_j0_m0_identity_bound": product_identity_bound,
        "identity_boundary_passed": identity_boundary_passed,
        "transformation_completion": {
            "completed": completed,
            "required": len(TRANSFORMATION_FAMILIES),
        },
        "semantic_environment_completion_executed": True,
        "results": results,
        "status": "PASS" if passed else "FAIL",
        "failed_requirement_ids": (
            [] if passed else ["M3_ACTIVE_PRODUCT_TRANSFORMATION_COMPLETION"]
        ),
        "product_completion_allowed": False,
    }
    report = {
        **body,
        "content_digest": PRODUCT_GENERICITY_DIGEST_PREFIX + digest_object(body),
    }
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(
                report,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return report


__all__ = [
    "PRODUCT_GENERICITY_DIGEST_PREFIX",
    "PRODUCT_GENERICITY_SCHEMA_VERSION",
    "PRODUCT_TRANSFORMATION_ACTION_BUDGET",
    "run_active_product_transformation_evaluation",
]
