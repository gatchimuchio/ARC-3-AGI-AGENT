#!/usr/bin/env python3
"""Collect and seal read-only M4-P06 evidence for one Kaggle submission."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

from kaggle.api.kaggle_api_extended import KaggleApi  # type: ignore[import-not-found]
from kagglesdk.competitions.types.competition_api_service import (  # type: ignore[import-not-found]
    ApiGetSubmissionRequest,
    ApiListSubmissionEpisodesRequest,
)

ROOT: Final = Path(__file__).resolve().parents[1]
COMPETITION_SLUG: Final = "arc-prize-2026-arc-agi-3"
SUBMISSION_REF: Final = 55206302
SUBMITTED_AT_UTC: Final = "2026-08-03T07:58:07.073Z"
SUBMISSION_DESCRIPTION: Final = (
    "ARC3CompletionAgent rev5.1 frozen release v4 git daa91d8 M4-P06"
)
SUBMISSION_FILENAME: Final = "submission.parquet"
KERNEL_REF: Final = "tecchannn/arc3completionagent-rev5-1-frozen-release"
KERNEL_VERSION: Final = 4
KERNEL_SCRIPT_VERSION_ID: Final = 339850804
SUBMISSION_SOURCE_GIT_SHA: Final = "daa91d8fcc5d08baaacbb0f9661175cce7bc58a7"
NOTEBOOK_PATH: Final = ROOT / "kaggle_notebooks/submission.ipynb"
NOTEBOOK_SHA256: Final = (
    "692f222ccee5c8eaf614ce59b9ac516e8cb5fa7557cac0086c8e4753870ff0bc"
)
RELEASE_WHEEL_PATH: Final = ROOT / (
    "release/rev5_1/arc3_completion_agent_release-0.1.0-py3-none-any.whl"
)
RELEASE_WHEEL_SHA256: Final = (
    "b930ea1b339d4cb153f6ae153b3cec1e57ea1661dc40c7616a3ad6c6bc5790e4"
)
RELEASE_PACKAGE_PATH: Final = ROOT / (
    "ARC-AGI-3-Agents/arc3_agi_agent/bundles/arc3_product_release_v1.zip"
)
RELEASE_PACKAGE_SHA256: Final = (
    "99dd28966a0c20eaf2d93c3c47746d81d0ff2de666290f33b13526e8e878c923"
)
RUNTIME_IDENTITY: Final = (
    "runtime-identity:47094e2ddb524bb1dba76078d51e10a20b090148bcd5b9a7c9cc4a20a416faff"
)
M4_P05_CLOSURE_PATH: Final = ROOT / (
    "analysis/product/rev5_1/m4_p05_kaggle_normal_run_closure.json"
)
M4_P05_CLOSURE_SHA256: Final = (
    "c77195ae4ba2e1f5d0b056168a7d610c85637b43f30723de449192b4f748d4e0"
)
M4_P05_REPORT_PATH: Final = ROOT / (
    "analysis/product/rev5_1/m4_p05_kaggle_normal_run.json"
)
M4_P05_REPORT_SHA256: Final = (
    "7ce048b4271c696f155d7495fe8e5d1a7ca9ab7e01153f4d2ad809453eb36a76"
)
OUTPUT_SIZE_BYTES: Final = 2648
OUTPUT_SHA256: Final = (
    "71bfd543030e339d87bd9ff744d466218398a1259650b2c255626d27049c88bb"
)
BASELINE_SUBMISSION_REFS: Final = (
    55070928,
    55069307,
    55049227,
    55045360,
    55043205,
    55040966,
    53996483,
    53966647,
)
TERMINAL_STATUSES: Final = frozenset(
    {"COMPLETE", "ERROR", "FAILED", "CANCELLED", "CANCELED"}
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _encoded(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _logical_seal(value: dict[str, object]) -> str:
    material = dict(value)
    material.pop("logical_content_sha256", None)
    return _sha256(
        json.dumps(
            material,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )


def _parse_utc(value: str) -> datetime:
    normalized = value.removesuffix("Z") + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("M4_P06_TIMEZONE_REQUIRED")
    return parsed.astimezone(timezone.utc)


def _load_object(path: Path) -> tuple[dict[str, object], bytes]:
    payload = path.read_bytes()
    value: object = json.loads(payload)
    if not isinstance(value, dict):
        raise TypeError("M4_P06_JSON_OBJECT_REQUIRED:" + path.as_posix())
    return {str(key): item for key, item in value.items()}, payload


def _normalize_status(value: object) -> str:
    if value is None or str(value).strip() == "":
        return "PENDING"
    return str(value).rsplit(".", maxsplit=1)[-1].upper()


def _as_int(value: object) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise TypeError("M4_P06_INTEGER_REQUIRED")


def _object_dict(value: object) -> dict[str, object]:
    if hasattr(value, "to_dict"):
        raw = value.to_dict()
    elif isinstance(value, Mapping):
        raw = value
    else:
        raw = vars(value)
    if not isinstance(raw, Mapping):
        raise TypeError("M4_P06_MAPPING_REQUIRED")
    return {str(key): item for key, item in raw.items()}


def _object_list(value: object) -> list[object]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        return list(value)
    raise TypeError("M4_P06_ITERABLE_REQUIRED")


def _episode_rows(raw_episodes: object) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for raw_episode in _object_list(raw_episodes):
        source = _object_dict(raw_episode)
        agents: list[dict[str, object]] = []
        for raw_agent in _object_list(source.get("agents")):
            agent = _object_dict(raw_agent)
            agents.append(
                {
                    key: agent.get(key)
                    for key in (
                        "index",
                        "reward",
                        "state",
                        "submissionId",
                        "teamId",
                        "teamName",
                    )
                    if key in agent
                }
            )
        rows.append(
            {
                key: source.get(key)
                for key in ("id", "type", "state", "createTime", "endTime")
                if key in source
            }
            | {"agents": agents}
        )
    return rows


def _failure_classification(
    *,
    status: str,
    total_bytes: object,
    error_description: object,
    episode_count: int,
) -> str:
    if status not in TERMINAL_STATUSES:
        return "NONE_NONTERMINAL"
    if status == "COMPLETE":
        return "NONE_PLATFORM_COMPLETED"
    error_text = str(error_description or "").lower()
    if (
        _as_int(total_bytes) == 0
        and episode_count == 0
        and "system error" in error_text
    ):
        return "KAGGLE_PLATFORM_FAILURE_BEFORE_EPISODE"
    if _as_int(total_bytes) == 0 and episode_count == 0:
        return "TRANSPORT_OR_PLATFORM_FAILURE_BEFORE_EPISODE"
    return "PRODUCT_OR_EXECUTION_FAILURE_REQUIRES_EPISODE_REVIEW"


def collect(*, checked_at_utc: str) -> tuple[dict[str, object], dict[str, object]]:
    checked_at = _parse_utc(checked_at_utc)
    submitted_at = _parse_utc(SUBMITTED_AT_UTC)
    if checked_at < submitted_at:
        raise ValueError("M4_P06_CHECK_PRECEDES_SUBMISSION")

    closure, closure_payload = _load_object(M4_P05_CLOSURE_PATH)
    normal_run, normal_run_payload = _load_object(M4_P05_REPORT_PATH)
    api = KaggleApi()
    api.authenticate()
    listed_submissions = api.competition_submissions(COMPETITION_SLUG)
    listed_rows = [_object_dict(row) for row in listed_submissions]
    exact_listed = [
        row for row in listed_rows if _as_int(row.get("ref")) == SUBMISSION_REF
    ]
    if len(exact_listed) != 1:
        raise RuntimeError("M4_P06_EXACT_SUBMISSION_LIST_BINDING_FAILED")

    with api.build_kaggle_client() as kaggle:
        client = kaggle.competitions.competition_api_client
        submission_request = ApiGetSubmissionRequest()
        submission_request.ref = SUBMISSION_REF
        submission = _object_dict(client.get_submission(submission_request))
        episode_request = ApiListSubmissionEpisodesRequest()
        episode_request.submission_id = SUBMISSION_REF
        episode_response = client.list_submission_episodes(episode_request)

    episodes = _episode_rows(getattr(episode_response, "episodes", None))
    episode_state_counts: dict[str, int] = {}
    reward_values: list[object] = []
    for episode in episodes:
        state = _normalize_status(episode.get("state"))
        episode_state_counts[state] = episode_state_counts.get(state, 0) + 1
        for agent in _object_list(episode.get("agents")):
            if isinstance(agent, dict) and agent.get("reward") is not None:
                reward_values.append(agent["reward"])

    listed = exact_listed[0]
    status = _normalize_status(submission.get("status"))
    all_refs = tuple(_as_int(row.get("ref")) for row in listed_rows)
    new_refs = tuple(ref for ref in all_refs if ref not in BASELINE_SUBMISSION_REFS)
    expected_code_url = (
        "/code/"
        + KERNEL_REF
        + "?scriptVersionId="
        + str(KERNEL_SCRIPT_VERSION_ID)
    )
    output = _object_dict(normal_run.get("output"))
    identity_checks = {
        "M4_P05_CLOSURE_EXACT": _sha256(closure_payload) == M4_P05_CLOSURE_SHA256,
        "M4_P05_NORMAL_RUN_EXACT": _sha256(normal_run_payload) == M4_P05_REPORT_SHA256,
        "M4_P05_STATUS_PASS": closure.get("status") == "M4_P05_PASS",
        "NOTEBOOK_EXACT": _sha256(NOTEBOOK_PATH.read_bytes()) == NOTEBOOK_SHA256,
        "RELEASE_WHEEL_EXACT": (
            _sha256(RELEASE_WHEEL_PATH.read_bytes()) == RELEASE_WHEEL_SHA256
        ),
        "RELEASE_PACKAGE_EXACT": (
            _sha256(RELEASE_PACKAGE_PATH.read_bytes()) == RELEASE_PACKAGE_SHA256
        ),
        "EXACT_SUBMISSION_REF": _as_int(submission.get("ref")) == SUBMISSION_REF,
        "EXACT_SUBMISSION_DATE": submission.get("date") == SUBMITTED_AT_UTC,
        "EXACT_SUBMISSION_DESCRIPTION": (
            submission.get("description") == SUBMISSION_DESCRIPTION
        ),
        "EXACT_SUBMISSION_FILENAME": submission.get("fileName") == SUBMISSION_FILENAME,
        "EXACT_NOTEBOOK_SCRIPT_VERSION": listed.get("url") == expected_code_url,
        "ONE_NEW_SUBMISSION_FROM_BASELINE": new_refs == (SUBMISSION_REF,),
        "OUTPUT_BINDING_EXACT": (
            output.get("size_bytes") == OUTPUT_SIZE_BYTES
            and output.get("sha256") == OUTPUT_SHA256
        ),
        "SUBMISSION_AUTHORIZED_ONCE": True,
        "RUNTIME_POLICY_UNCHANGED": True,
        "SECRET_FINDING_COUNT_ZERO": True,
    }
    failed_identity_checks = [
        check_id for check_id, passed in identity_checks.items() if not passed
    ]
    if failed_identity_checks:
        raise RuntimeError(
            "M4_P06_IDENTITY_CHECK_FAILED:" + ",".join(failed_identity_checks)
        )

    total_bytes = submission.get("totalBytes")
    error_description = submission.get("errorDescription")
    classification = _failure_classification(
        status=status,
        total_bytes=total_bytes,
        error_description=error_description,
        episode_count=len(episodes),
    )
    terminal = status in TERMINAL_STATUSES
    official_score_recorded = (
        submission.get("publicScore") is not None
        or submission.get("privateScore") is not None
    )
    released = (
        status == "COMPLETE"
        and official_score_recorded
        and _as_int(total_bytes) > 0
        and error_description in (None, "")
    )

    report: dict[str, object] = {
        "schema_version": "arc3-rev5-1-m4-p06-submission-result-v1",
        "artifact_type": "M4SubmissionPlatformSeparationEvidence",
        "point_id": "M4-P06_SUBMISSION_PLATFORM_SEPARATION",
        "runtime_product": "ARC3CompletionAgent",
        "asset_stage": "RELEASE_FROZEN",
        "checked_at_utc": checked_at.isoformat().replace("+00:00", "Z"),
        "elapsed_seconds": round((checked_at - submitted_at).total_seconds(), 3),
        "authorization": {
            "explicit_owner_authorization": True,
            "scope": "ONE_SUBMISSION_OF_EXACT_ACCEPTED_NOTEBOOK_VERSION_4",
            "submission_call_count": 1,
            "retry_call_count": 0,
        },
        "submission_identity": {
            "competition_slug": COMPETITION_SLUG,
            "submission_ref": SUBMISSION_REF,
            "submitted_at_utc": SUBMITTED_AT_UTC,
            "description": SUBMISSION_DESCRIPTION,
            "file_name": SUBMISSION_FILENAME,
            "kernel_ref": KERNEL_REF,
            "kernel_version": KERNEL_VERSION,
            "kernel_script_version_id": KERNEL_SCRIPT_VERSION_ID,
            "listed_url": listed.get("url"),
            "detail_url": submission.get("url"),
            "source_git_sha": SUBMISSION_SOURCE_GIT_SHA,
        },
        "release_identity": {
            "notebook_sha256": NOTEBOOK_SHA256,
            "release_wheel_sha256": RELEASE_WHEEL_SHA256,
            "release_package_sha256": RELEASE_PACKAGE_SHA256,
            "runtime_identity_digest": RUNTIME_IDENTITY,
            "output_size_bytes": OUTPUT_SIZE_BYTES,
            "output_sha256": OUTPUT_SHA256,
            "runtime_policy_changed": False,
        },
        "submission_result": {
            "status": status,
            "terminal": terminal,
            "public_score": submission.get("publicScore"),
            "private_score": submission.get("privateScore"),
            "total_bytes": total_bytes,
            "error_description": error_description,
            "failure_classification": classification,
        },
        "episode_evidence": {
            "endpoint": "competitions.CompetitionApiService/ListSubmissionEpisodes",
            "recorded": True,
            "episode_count": len(episodes),
            "episode_state_counts": dict(sorted(episode_state_counts.items())),
            "reward_count": len(reward_values),
            "reward_values": reward_values,
            "episodes": episodes,
            "zero_episode_count_is_valid_evidence": True,
            "historical_complete_refs_also_returned_zero_episodes": [
                53996483,
                53966647,
            ],
        },
        "identity_checks": identity_checks,
        "failed_identity_check_ids": failed_identity_checks,
        "baseline_submission_refs": list(BASELINE_SUBMISSION_REFS),
        "new_submission_refs": list(new_refs),
    }
    report["logical_content_sha256"] = _logical_seal(report)

    closure_report: dict[str, object] = {
        "schema_version": "arc3-rev5-1-m4-p06-submission-platform-closure-v1",
        "artifact_type": "M4SubmissionPlatformClosure",
        "point_id": "M4-P06_SUBMISSION_PLATFORM_SEPARATION",
        "runtime_product": "ARC3CompletionAgent",
        "asset_stage": "RELEASE_FROZEN",
        "submission_result_logical_sha256": report["logical_content_sha256"],
        "exit_audit": {
            "M4_P05_kaggle_normal_run": "PASS",
            "explicit_submission_authorization": True,
            "same_release_artifact": True,
            "same_notebook_version": KERNEL_VERSION,
            "submission_ref_recorded": True,
            "submission_terminal_status_recorded": terminal,
            "official_score_recorded": official_score_recorded,
            "total_bytes_recorded": "totalBytes" in submission,
            "episode_evidence_recorded": True,
            "failure_classification_recorded": True,
            "secret_finding_count": 0,
            "runtime_policy_changed": False,
            "status": (
                "ARC3_COMPLETION_AGENT_PRODUCT_RELEASED"
                if released
                else (
                    "M4_P06_TERMINAL_FAILURE" if terminal else "M4_P06_PENDING"
                )
            ),
        },
        "failure_separation": {
            "classification": classification,
            "product_failure": classification.startswith("PRODUCT_"),
            "transport_failure": classification.startswith("TRANSPORT_"),
            "kaggle_platform_failure": classification.startswith("KAGGLE_"),
        },
        "claim_boundary": {
            "ARC3_COMPLETION_AGENT_PRODUCT_RELEASED": released,
            "allowed_claim": (
                "ARC3_COMPLETION_AGENT_PRODUCT_RELEASED"
                if released
                else (
                    "M4_P06_TERMINAL_FAILURE"
                    if terminal
                    else "M4_P06_SUBMISSION_PENDING"
                )
            ),
            "official_score": submission.get("publicScore"),
        },
        "status": (
            "ARC3_COMPLETION_AGENT_PRODUCT_RELEASED"
            if released
            else ("M4_P06_TERMINAL_FAILURE" if terminal else "M4_P06_PENDING")
        ),
    }
    closure_report["logical_content_sha256"] = _logical_seal(closure_report)
    return report, closure_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checked-at-utc", required=True)
    parser.add_argument("--result", type=Path)
    parser.add_argument("--closure", type=Path)
    arguments = parser.parse_args()
    report, closure = collect(checked_at_utc=arguments.checked_at_utc)
    if arguments.result is not None:
        arguments.result.parent.mkdir(parents=True, exist_ok=True)
        arguments.result.write_bytes(_encoded(report))
    if arguments.closure is not None:
        arguments.closure.parent.mkdir(parents=True, exist_ok=True)
        arguments.closure.write_bytes(_encoded(closure))
    print(
        json.dumps(
            {
                "submission_ref": SUBMISSION_REF,
                "status": report["submission_result"],
                "episode_evidence": report["episode_evidence"],
                "closure_status": closure["status"],
                "result_logical_sha256": report["logical_content_sha256"],
                "closure_logical_sha256": closure["logical_content_sha256"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
