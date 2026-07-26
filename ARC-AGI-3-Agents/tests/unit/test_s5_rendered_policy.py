from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path

import numpy as np

from arc3_agi_agent.s5_policy import (
    S5_HISTORY_LIMIT,
    S5HistoryRecord,
    load_s5_rendered_policy_body,
    s5_feature_vector_from_render,
)
from arc3_agi_agent.s5_runner import run_s5_rendered_policy
from arc3_agi_agent.schema import forbidden_runtime_paths

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_ROOT = REPOSITORY_ROOT / "ARC-AGI-3-Agents"
CORPUS_PATH = (
    REPOSITORY_ROOT
    / "analysis"
    / "teacher"
    / "S5_RENDERED_POLICY_TRAINING_CORPUS.npz"
)
RUNTIME_MODULES = (
    "s5_authority.py",
    "s5_compute.py",
    "s5_policy.py",
    "s5_runner.py",
    "s5_runtime.py",
    "s5_score_adapter.py",
)


def _history_before(
    arrays: dict[str, np.ndarray],
    index: int,
) -> tuple[S5HistoryRecord, ...]:
    ordinal = arrays["game_ordinal"][index]
    history: tuple[S5HistoryRecord, ...] = ()
    start = max(0, index - S5_HISTORY_LIMIT)
    for prior in range(start, index):
        if arrays["game_ordinal"][prior] != ordinal:
            continue
        action_id = int(arrays["actions"][prior])
        horizontal = int(arrays["targets"][prior, 0])
        vertical = int(arrays["targets"][prior, 1])
        palette = (
            int(arrays["frames"][prior, vertical, horizontal])
            if action_id == 6
            else 0
        )
        changed = bool(
            np.any(
                arrays["frames"][prior]
                != arrays["frames"][prior + 1]
            )
        )
        history = (
            *history,
            S5HistoryRecord(
                action_id=action_id,
                horizontal=horizontal,
                vertical=vertical,
                target_palette=palette,
                visible_change=changed,
                compatibility_reset=bool(
                    arrays["level_compatibility_reset"][prior]
                ),
            ),
        )[-S5_HISTORY_LIMIT:]
    return history


class S5RenderedPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with np.load(CORPUS_PATH, allow_pickle=False) as loaded:
            cls.arrays = {
                name: np.array(loaded[name], copy=True)
                for name in loaded.files
            }
        cls.body = load_s5_rendered_policy_body()

    def test_bundle_is_valid_immutable_and_example_free(self) -> None:
        self.assertEqual(self.body.validate(), ())
        self.assertEqual(self.body.parameter_count, 4_269_485)
        self.assertFalse(
            self.body._manifest[
                "runtime_artifact_contains_training_examples"
            ]
        )
        self.assertEqual(
            forbidden_runtime_paths(self.body._manifest),
            (),
        )
        for head in (
            *self.body.action_heads.values(),
            self.body.horizontal_head,
            self.body.vertical_head,
        ):
            self.assertFalse(head.weight0.flags.writeable)
            self.assertFalse(head.bias0.flags.writeable)
            self.assertFalse(head.weight1.flags.writeable)
            self.assertFalse(head.bias1.flags.writeable)

    def test_passive_history_changes_same_render_decision(self) -> None:
        first = 9
        second = 10
        self.assertTrue(
            np.array_equal(
                self.arrays["frames"][first],
                self.arrays["frames"][second],
            )
        )
        self.assertTrue(
            np.array_equal(
                self.arrays["available"][first],
                self.arrays["available"][second],
            )
        )
        surface = tuple(
            int(item)
            for item in np.flatnonzero(
                self.arrays["available"][first]
            )
        )
        head = self.body.action_heads[surface]
        first_features = s5_feature_vector_from_render(
            self.arrays["frames"][first],
            surface,
            _history_before(self.arrays, first),
        )
        second_features = s5_feature_vector_from_render(
            self.arrays["frames"][second],
            surface,
            _history_before(self.arrays, second),
        )
        self.assertFalse(
            np.array_equal(first_features, second_features)
        )
        self.assertEqual(head.predict(first_features)[0], 6)
        self.assertEqual(head.predict(second_features)[0], 3)

    def test_selected_teacher_rows_keep_action_and_pointer_labels(self) -> None:
        selected = (0, 9, 10, 535, 536, 5000, 10732)
        for index in selected:
            with self.subTest(index=index):
                surface = tuple(
                    int(item)
                    for item in np.flatnonzero(
                        self.arrays["available"][index]
                    )
                )
                features = s5_feature_vector_from_render(
                    self.arrays["frames"][index],
                    surface,
                    _history_before(self.arrays, index),
                )
                action_id = self.body.action_heads[surface].predict(
                    features
                )[0]
                self.assertEqual(
                    action_id,
                    int(self.arrays["actions"][index]),
                )
                if action_id == 6:
                    self.assertEqual(
                        self.body.horizontal_head.predict(features)[0],
                        int(self.arrays["targets"][index, 0]),
                    )
                    self.assertEqual(
                        self.body.vertical_head.predict(features)[0],
                        int(self.arrays["targets"][index, 1]),
                    )

    def test_runtime_modules_do_not_import_teacher_or_analysis(self) -> None:
        for filename in RUNTIME_MODULES:
            path = PACKAGE_ROOT / "arc3_agi_agent" / filename
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
            imports = {
                node.module or ""
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom)
            }
            imports.update(
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
                for alias in node.names
            )
            self.assertFalse(
                any("teacher" in item for item in imports),
                filename,
            )
            self.assertNotIn("analysis/teacher", source)
            self.assertNotIn("environment_files/", source)

    def test_manifest_has_no_identity_routing_surface(self) -> None:
        manifest_path = (
            PACKAGE_ROOT
            / "arc3_agi_agent"
            / "bundles"
            / "s5_rendered_policy_v1.json"
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        serialized = json.dumps(manifest, sort_keys=True).casefold()
        for forbidden in (
            "game_id",
            "task_id",
            "level_id",
            "replay_index",
            "answer_map",
            "fixed_action_sequence",
            "literal_coordinate_table",
            "source_state",
            "hidden_state",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_runner_rejects_invalid_deterministic_seed(self) -> None:
        for seed in (-1, 2**32, True):
            with self.subTest(seed=seed), self.assertRaisesRegex(
                ValueError,
                "S5_DETERMINISTIC_SEED_INVALID",
            ):
                run_s5_rendered_policy(
                    environments_dir=Path("not-read"),
                    deterministic_seed=seed,
                )


if __name__ == "__main__":
    unittest.main()
