from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from arc3_agi_agent.p10_batch_checkpoint import (
    P10CheckpointMismatch,
    assemble_checkpointed_report,
    build_batch_conditions,
    load_game_checkpoint,
    write_game_checkpoint,
)
from p10_checkpoint_worker import run_p10_checkpoint_worker
from p10_main import run_p10_checkpointed_offline_samples


def _write_environment_metadata(root: Path, game_ids: list[str]) -> None:
    for index, game_id in enumerate(game_ids):
        path = root / f"g{index:02d}" / "sample" / "metadata.json"
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(
                {
                    "game_id": game_id,
                    "title": f"G{index:02d}",
                    "baseline_actions": [10, 10],
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        implementation = path.with_name(f"g{index:02d}.py")
        implementation.write_text(
            f"GAME_ID = {game_id!r}\n",
            encoding="utf-8",
        )


def _single_game_result(
    game_id: str,
    *,
    card_id: str = "nondeterministic-card",
    run_guid: str = "nondeterministic-run",
) -> dict[str, object]:
    report = {
        "game_id": game_id,
        "actions": 20,
        "levels_completed": 2,
        "win_levels": 2,
        "terminal_state": "WIN",
        "complete": True,
        "max_action_exhausted": False,
    }
    return {
        "phase": "P10",
        "operation_mode": "offline",
        "environment_count": 1,
        "completed_count": 1,
        "complete_game_count": 1,
        "completed_levels": 2,
        "total_levels": 2,
        "all_complete": True,
        "error_count": 0,
        "max_actions": 64,
        "instruction_variant": "hybrid",
        "instruction_lifecycle": "active",
        "reports": [report],
        "errors": [],
        "local_scorecard": {
            "card_id": card_id,
            "environments": [
                {
                    "id": game_id,
                    "actions": 20,
                    "completed": True,
                    "level_count": 2,
                    "levels_completed": 2,
                    "resets": 0,
                    "score": 100.0,
                    "runs": [
                        {
                            "guid": run_guid,
                            "actions": 20,
                            "completed": True,
                            "level_actions": [10, 10],
                            "levels_completed": 2,
                            "score": 100.0,
                            "state": "WIN",
                        }
                    ],
                }
            ],
        },
    }


class P10BatchCheckpointTests(unittest.TestCase):
    def test_parallel_worker_binds_one_game_to_full_sample_conditions(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            environments = root / "environments"
            checkpoint_dir = root / "checkpoints"
            game_ids = ["g00-sample", "g01-sample"]
            _write_environment_metadata(environments, game_ids)
            with (
                patch(
                    "p10_checkpoint_worker._resolve_p10_batch_game_ids",
                    return_value=game_ids,
                ),
                patch(
                    "p10_checkpoint_worker.active_p10_manifest_digest",
                    return_value="active-manifest",
                ),
                patch(
                    "p10_checkpoint_worker.run_p10_offline_samples",
                    return_value=_single_game_result(game_ids[0]),
                ) as run,
            ):
                executed = run_p10_checkpoint_worker(
                    environments_dir=environments,
                    checkpoint_dir=checkpoint_dir,
                    game_id=game_ids[0],
                    max_actions=64,
                )
                reused = run_p10_checkpoint_worker(
                    environments_dir=environments,
                    checkpoint_dir=checkpoint_dir,
                    game_id=game_ids[0],
                    max_actions=64,
                    resume=True,
                )

        self.assertEqual(executed["status"], "EXECUTED")
        self.assertEqual(reused["status"], "REUSED")
        self.assertEqual(
            executed["conditions_digest"],
            reused["conditions_digest"],
        )
        self.assertEqual(run.call_count, 1)

    def test_checkpoint_round_trip_and_oracle_compatible_assembly(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            environments = root / "environments"
            checkpoint_dir = root / "checkpoints"
            game_ids = ["g00-sample", "g01-sample"]
            _write_environment_metadata(environments, game_ids)
            conditions = build_batch_conditions(
                environments_dir=environments,
                game_ids=game_ids,
                max_actions=64,
                instruction_variant="hybrid",
                instruction_lifecycle="active",
                active_manifest_digest="active-manifest",
            )
            for game_id in game_ids:
                write_game_checkpoint(
                    checkpoint_dir=checkpoint_dir,
                    conditions=conditions,
                    game_id=game_id,
                    result=_single_game_result(game_id),
                )
            assembled = assemble_checkpointed_report(
                checkpoint_dir=checkpoint_dir,
                conditions=conditions,
                reused_game_ids=[game_ids[0]],
            )

        self.assertTrue(assembled["all_complete"])
        self.assertEqual(assembled["environment_count"], 2)
        self.assertEqual(assembled["completed_levels"], 4)
        self.assertEqual(assembled["total_levels"], 4)
        self.assertEqual(
            len(assembled["local_scorecard"]["environments"]),
            2,
        )
        self.assertEqual(
            assembled["checkpointing"]["reused_game_count"],
            1,
        )
        self.assertTrue(
            all(
                run["guid"].startswith("checkpoint-run:")
                for environment in assembled["local_scorecard"][
                    "environments"
                ]
                for run in environment["runs"]
            )
        )

    def test_resume_rejects_any_condition_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            environments = root / "environments"
            checkpoint_dir = root / "checkpoints"
            game_ids = ["g00-sample"]
            _write_environment_metadata(environments, game_ids)
            original = build_batch_conditions(
                environments_dir=environments,
                game_ids=game_ids,
                max_actions=64,
                instruction_variant="hybrid",
                instruction_lifecycle="active",
                active_manifest_digest="active-manifest",
            )
            write_game_checkpoint(
                checkpoint_dir=checkpoint_dir,
                conditions=original,
                game_id=game_ids[0],
                result=_single_game_result(game_ids[0]),
            )
            changed = build_batch_conditions(
                environments_dir=environments,
                game_ids=game_ids,
                max_actions=65,
                instruction_variant="hybrid",
                instruction_lifecycle="active",
                active_manifest_digest="active-manifest",
            )
            with self.assertRaisesRegex(
                P10CheckpointMismatch,
                "P10_CHECKPOINT_CONDITIONS_MISMATCH",
            ):
                load_game_checkpoint(
                    checkpoint_dir=checkpoint_dir,
                    conditions=changed,
                    game_id=game_ids[0],
                )

            tampered = copy.deepcopy(original)
            tampered["max_actions"] = 65
            with self.assertRaisesRegex(
                P10CheckpointMismatch,
                "P10_CHECKPOINT_CONDITIONS_DIGEST_INVALID",
            ):
                load_game_checkpoint(
                    checkpoint_dir=checkpoint_dir,
                    conditions=tampered,
                    game_id=game_ids[0],
                )

    def test_environment_implementation_drift_changes_conditions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            environments = root / "environments"
            game_ids = ["g00-sample"]
            _write_environment_metadata(environments, game_ids)
            before = build_batch_conditions(
                environments_dir=environments,
                game_ids=game_ids,
                max_actions=64,
                instruction_variant="hybrid",
                instruction_lifecycle="active",
                active_manifest_digest="active-manifest",
            )
            implementation = environments / "g00/sample/g00.py"
            implementation.write_text(
                "GAME_ID = 'changed'\n",
                encoding="utf-8",
            )
            after = build_batch_conditions(
                environments_dir=environments,
                game_ids=game_ids,
                max_actions=64,
                instruction_variant="hybrid",
                instruction_lifecycle="active",
                active_manifest_digest="active-manifest",
            )
        self.assertNotEqual(
            before["environment_inventory_digest"],
            after["environment_inventory_digest"],
        )
        self.assertNotEqual(
            before["conditions_digest"],
            after["conditions_digest"],
        )

    def test_aggregate_is_stable_across_scorecard_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            environments = root / "environments"
            game_ids = ["g00-sample"]
            _write_environment_metadata(environments, game_ids)
            conditions = build_batch_conditions(
                environments_dir=environments,
                game_ids=game_ids,
                max_actions=64,
                instruction_variant="hybrid",
                instruction_lifecycle="active",
                active_manifest_digest="active-manifest",
            )
            outputs = []
            for index in range(2):
                checkpoint_dir = root / f"checkpoints-{index}"
                write_game_checkpoint(
                    checkpoint_dir=checkpoint_dir,
                    conditions=conditions,
                    game_id=game_ids[0],
                    result=_single_game_result(
                        game_ids[0],
                        card_id=f"card-{index}",
                        run_guid=f"run-{index}",
                    ),
                )
                assembled = assemble_checkpointed_report(
                    checkpoint_dir=checkpoint_dir,
                    conditions=conditions,
                )
                outputs.append(assembled)
        self.assertEqual(outputs[0], outputs[1])

    def test_runner_resumes_without_reexecuting_finished_games(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            environments = root / "environments"
            checkpoint_dir = root / "checkpoints"
            game_ids = ["g00-sample", "g01-sample"]
            _write_environment_metadata(environments, game_ids)

            def run_one(**kwargs: object) -> dict[str, object]:
                requested = kwargs["requested_games"]
                self.assertIsInstance(requested, list)
                return _single_game_result(requested[0])

            with (
                patch(
                    "p10_main._resolve_p10_batch_game_ids",
                    return_value=game_ids,
                ),
                patch(
                    "p10_main.active_p10_manifest_digest",
                    return_value="active-manifest",
                ),
                patch(
                    "p10_main.run_p10_offline_samples",
                    side_effect=run_one,
                ) as run,
            ):
                first = run_p10_checkpointed_offline_samples(
                    environments_dir=environments,
                    checkpoint_dir=checkpoint_dir,
                    all_samples=True,
                    max_actions=64,
                )
                self.assertEqual(run.call_count, 2)
                run.reset_mock()
                second = run_p10_checkpointed_offline_samples(
                    environments_dir=environments,
                    checkpoint_dir=checkpoint_dir,
                    all_samples=True,
                    max_actions=64,
                    resume=True,
                )
                self.assertEqual(run.call_count, 0)

        self.assertTrue(first["all_complete"])
        self.assertTrue(second["all_complete"])
        self.assertEqual(
            second["checkpointing"]["reused_game_count"],
            2,
        )


if __name__ == "__main__":
    unittest.main()
