from __future__ import annotations

import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from arc3_agi_agent.local_score_oracle import (
    LEGACY_SOURCE,
    ORACLE_ADAPTER_VERSION,
    build_local_score_oracle,
    main,
    normalize_p10_report,
    score_game,
)


def sample_games() -> list[tuple[str, int]]:
    return [
        (f"g{index:02d}-sample", 8 if index < 8 else 7)
        for index in range(25)
    ]


def write_sample_zip(path: Path) -> None:
    with ZipFile(path, "w") as archive:
        for game_id, level_count in sample_games():
            title = game_id.split("-", 1)[0].upper()
            archive.writestr(
                f"environment_files/{title.casefold()}/sample/metadata.json",
                json.dumps(
                    {
                        "game_id": game_id,
                        "title": title,
                        "baseline_actions": [10] * level_count,
                    }
                ),
            )


def p10_report() -> dict[str, object]:
    reports: list[dict[str, object]] = []
    environments: list[dict[str, object]] = []
    for game_id, level_count in sample_games():
        reports.append(
            {
                "game_id": game_id,
                "actions": level_count * 10,
                "levels_completed": level_count,
                "win_levels": level_count,
                "terminal_state": "WIN",
                "max_action_exhausted": False,
                "instruction_body_versions": ["p10-test-v1"],
                "instruction_body_digests": ["test-digest"],
                "visual_operator_version": "visual-test-v1",
            }
        )
        environments.append(
            {
                "id": game_id,
                "runs": [
                    {
                        "guid": f"nondeterministic-{game_id}",
                        "levels_completed": level_count,
                        "level_actions": [10] * level_count,
                    }
                ],
            }
        )
    return {
        "phase": "P10",
        "operation_mode": "offline",
        "environment_count": 25,
        "completed_count": 25,
        "completed_levels": 183,
        "total_levels": 183,
        "error_count": 0,
        "max_actions": 450,
        "instruction_variant": "hybrid",
        "reports": reports,
        "errors": [],
        "local_scorecard": {
            "card_id": "nondeterministic-card",
            "environments": environments,
        },
    }


class LocalScoreOracleTests(unittest.TestCase):
    def test_legacy_rhae_equations_and_completion_ceiling(self) -> None:
        complete = score_game([10, 20], [10, 20], 2)
        partial = score_game([10, 20], [10, 0], 1)
        efficient = score_game([10, 20], [1, 1], 2)

        self.assertEqual(complete["level_scores_percent"], [100.0, 100.0])
        self.assertEqual(complete["game_score_percent"], 100.0)
        self.assertEqual(partial["game_score_percent"], 33.333333333)
        self.assertEqual(efficient["level_scores_percent"], [115.0, 115.0])
        self.assertEqual(efficient["game_score_percent"], 100.0)

    def test_completed_level_without_action_count_fails_closed(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "COMPLETED_LEVEL_ACTION_COUNT_MISSING",
        ):
            score_game([10, 20], [], 1)

    def test_complete_p10_report_scores_25_games_and_183_levels(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sample_zip = root / "sample.zip"
            report_path = root / "p10.json"
            write_sample_zip(sample_zip)
            report_path.write_text(
                json.dumps(p10_report()),
                encoding="utf-8",
            )

            oracle = build_local_score_oracle(
                sample_zip,
                report_path,
            )

        self.assertEqual(
            oracle["adapter_version"],
            ORACLE_ADAPTER_VERSION,
        )
        self.assertEqual(oracle["legacy_source"], LEGACY_SOURCE)
        self.assertEqual(oracle["oracle"]["game_count"], 25)
        self.assertEqual(oracle["oracle"]["level_count"], 183)
        current = oracle["current_local_result"]
        self.assertEqual(current["completed_levels"], 183)
        self.assertEqual(current["official_rhae_score_percent"], 100.0)
        self.assertEqual(current["error_count"], 0)
        self.assertEqual(len(oracle["games"]), 25)

    def test_runtime_scorecard_identity_does_not_change_score_digest(
        self,
    ) -> None:
        first = p10_report()
        second = copy.deepcopy(first)
        second["local_scorecard"]["card_id"] = "other-card"
        for environment in second["local_scorecard"]["environments"]:
            environment["runs"][0]["guid"] = "other-guid"

        first_normalized = normalize_p10_report(first)
        second_normalized = normalize_p10_report(second)

        self.assertEqual(
            first_normalized["scoring_input_digest"],
            second_normalized["scoring_input_digest"],
        )
        self.assertEqual(
            first_normalized["results"],
            second_normalized["results"],
        )

    def test_missing_game_is_rejected_before_score_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sample_zip = root / "sample.zip"
            report_path = root / "p10.json"
            write_sample_zip(sample_zip)
            report = p10_report()
            report["reports"].pop()
            report["local_scorecard"]["environments"].pop()
            report["environment_count"] = 24
            report["completed_count"] = 24
            report["completed_levels"] = 176
            report["total_levels"] = 176
            report_path.write_text(
                json.dumps(report),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ValueError,
                "EVALUATION_GAME_MISMATCH",
            ):
                build_local_score_oracle(sample_zip, report_path)

    def test_failed_game_without_scorecard_run_is_scored_zero(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sample_zip = root / "sample.zip"
            report_path = root / "p10.json"
            write_sample_zip(sample_zip)
            report = p10_report()
            failed = report["reports"].pop()
            failed_environment = report["local_scorecard"][
                "environments"
            ][-1]
            failed_environment["runs"] = []
            report["errors"] = [
                {
                    "game_id": failed["game_id"],
                    "error_type": "RuntimeError",
                    "message": "synthetic failure",
                }
            ]
            report["completed_count"] = 24
            report["completed_levels"] = 176
            report["total_levels"] = 176
            report["error_count"] = 1
            report_path.write_text(
                json.dumps(report),
                encoding="utf-8",
            )

            oracle = build_local_score_oracle(
                sample_zip,
                report_path,
            )

        current = oracle["current_local_result"]
        self.assertEqual(current["completed_levels"], 176)
        self.assertEqual(current["error_count"], 1)
        self.assertEqual(current["official_rhae_score_percent"], 96.0)

    def test_cli_writes_json_and_markdown_only_after_validation(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sample_zip = root / "sample.zip"
            report_path = root / "p10.json"
            output = root / "oracle.json"
            markdown = root / "oracle.md"
            write_sample_zip(sample_zip)
            report_path.write_text(
                json.dumps(p10_report()),
                encoding="utf-8",
            )

            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                result = main(
                    [
                        "--sample-zip",
                        str(sample_zip),
                        "--p10-report",
                        str(report_path),
                        "--output",
                        str(output),
                        "--markdown",
                        str(markdown),
                    ]
                )

            artifact = json.loads(output.read_text(encoding="utf-8"))
            rendered = markdown.read_text(encoding="utf-8")
        self.assertEqual(result, 0)
        self.assertEqual(
            artifact["current_local_result"][
                "official_rhae_score_percent"
            ],
            100.0,
        )
        self.assertIn("current official RHAE: 100.000000%", rendered)
        self.assertIn("score digest:", rendered)
        self.assertIn("rhae_percent=100.000000", stream.getvalue())


if __name__ == "__main__":
    unittest.main()
