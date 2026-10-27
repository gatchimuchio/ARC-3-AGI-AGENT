"""Build the local C2-105 action-plan cap candidate from pinned v29."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BASE_DIR = (
    ROOT
    / "出力/ARC3-RUN-003-local/C2-060-outputcap-20480-context139264"
    / "source/cap20k-context139264"
)
BASE_NOTEBOOK = BASE_DIR / "submission.ipynb"
BASE_METADATA = BASE_DIR / "kernel-metadata.json"
OUTPUT_DIR = ROOT / "出力/ARC3-RUN-003-local/C2-105-action-plan-cap8"
EVIDENCE_DIR = ROOT / "運用/証拠/ARC26-UNIFIED"
QUOTA_REJECTION = (
    "運用/証拠/ARC26-UNIFIED/"
    "ARC3-C2-089-action-cap-v1-kernel-push-rejection-20261027T163826Z.json"
)

EXPECTED_BASE_NOTEBOOK_SHA256 = (
    "d610d79e44e0974cf18f3f29c9521c7407e4c6fa047d38456f1a9a67f8a65e26"
)
EXPECTED_METADATA_SHA256 = (
    "e31a7418a9430d0a343cac1dad9e408a3bafa64970d830d3f1be82742ed49372"
)
KERNEL_SLUG = "tecchannn/arc3-model-guided-c2-025"
CAP = 8


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def replace_once(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ValueError(f"Expected one patch anchor, found {count}: {old!r}")
    return text.replace(old, new, 1)


def parse_hunk(line: str) -> tuple[int, int, int, int] | None:
    match = re.match(
        r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@",
        line,
    )
    if not match:
        return None
    old_start = int(match.group(1))
    old_count = int(match.group(2) or 1)
    new_start = int(match.group(3))
    new_count = int(match.group(4) or 1)
    return old_start, old_count, new_start, new_count


def update_python_sandbox_hunks(patch_text: str) -> tuple[str, dict[str, Any]]:
    lines = patch_text.splitlines(keepends=True)
    section_start = next(
        (
            i
            for i, line in enumerate(lines)
            if line.startswith(
                "diff --git a/ARC3-Inference/inference/agent/python_tool_sandbox.py "
            )
        ),
        None,
    )
    if section_start is None:
        raise ValueError("Pinned patch lacks python_tool_sandbox.py section")

    section_end = next(
        (
            i
            for i in range(section_start + 1, len(lines))
            if lines[i].startswith("diff --git ")
        ),
        len(lines),
    )

    shift = 0
    updated: list[str] = []
    records: list[dict[str, int]] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        parsed = parse_hunk(line) if section_start < i < section_end else None
        if parsed is None:
            updated.append(line)
            i += 1
            continue

        old_start, old_count, new_start, old_new_count = parsed
        j = i + 1
        actual_old = 0
        actual_new = 0
        while j < section_end and not lines[j].startswith("@@ "):
            body = lines[j]
            if body.startswith("diff --git "):
                break
            if body.startswith(" "):
                actual_old += 1
                actual_new += 1
            elif body.startswith("-") and not body.startswith("---"):
                actual_old += 1
            elif body.startswith("+") and not body.startswith("+++"):
                actual_new += 1
            elif body.startswith("\\"):
                pass
            else:
                raise ValueError(f"Unexpected line in unified diff hunk: {body[:100]!r}")
            j += 1

        if actual_old != old_count:
            raise ValueError(
                f"Old hunk count mismatch at {old_start}: "
                f"header={old_count}, body={actual_old}"
            )

        target = old_start in {350, 363}
        adjusted_start = new_start + shift if old_start > 350 else new_start
        adjusted_count = actual_new if target else old_new_count
        if target:
            delta = actual_new - old_new_count
            if delta <= 0:
                raise ValueError(f"Expected added lines in hunk {old_start}, got {delta}")
            shift += delta
            records.append(
                {
                    "old_start": old_start,
                    "new_start_before": new_start,
                    "new_start_after": adjusted_start,
                    "old_count": old_count,
                    "new_count_before": old_new_count,
                    "new_count_after": adjusted_count,
                    "added_lines": delta,
                }
            )

        suffix = line.rstrip("\r\n")
        header = re.sub(
            r"^(@@ -\d+(?:,\d+)? \+)\d+(?:,\d+)?( @@.*)$",
            rf"\g<1>{adjusted_start},{adjusted_count}\g<2>",
            suffix,
        )
        updated.append(header + ("\r\n" if line.endswith("\r\n") else "\n"))
        i += 1

    if [row["old_start"] for row in records] != [350, 363]:
        raise ValueError(f"Unexpected modified hunks: {records}")

    result = "".join(updated)
    validate_all_hunks(result)
    return result, {"modified_hunks": records, "downstream_new_start_shift": shift}


def validate_all_hunks(patch_text: str) -> None:
    lines = patch_text.splitlines()
    for i, line in enumerate(lines):
        parsed = parse_hunk(line)
        if parsed is None:
            continue
        _, old_expected, _, new_expected = parsed
        old_actual = 0
        new_actual = 0
        j = i + 1
        while j < len(lines) and not lines[j].startswith(("@@ ", "diff --git ")):
            body = lines[j]
            if body.startswith(" "):
                old_actual += 1
                new_actual += 1
            elif body.startswith("-") and not body.startswith("---"):
                old_actual += 1
            elif body.startswith("+") and not body.startswith("+++"):
                new_actual += 1
            elif not body.startswith("\\"):
                raise ValueError(f"Malformed unified diff line: {body[:100]!r}")
            j += 1
        if (old_actual, new_actual) != (old_expected, new_expected):
            raise ValueError(
                f"Unified diff hunk mismatch at line {i + 1}: "
                f"expected {(old_expected, new_expected)}, "
                f"found {(old_actual, new_actual)}"
            )


def exercise_cap_boundaries() -> None:
    def cap_plan(requested: list[int], already_executed: int) -> tuple[list[int], bool]:
        remaining = CAP - already_executed
        truncated = False
        if requested:
            if remaining <= 0:
                raise RuntimeError("plan refused at exhausted cap")
            truncated = len(requested) > remaining
            if truncated:
                requested = requested[:remaining]
        return requested, truncated

    assert cap_plan(list(range(8)), 0) == (list(range(8)), False)
    assert cap_plan(list(range(12)), 0) == (list(range(8)), True)
    assert cap_plan(list(range(8)), 4) == (list(range(4)), True)
    assert cap_plan([], 8) == ([], False)
    try:
        cap_plan([1], 8)
    except RuntimeError:
        pass
    else:
        raise AssertionError("exhausted action plan was not refused")


def main() -> None:
    base_bytes = BASE_NOTEBOOK.read_bytes()
    metadata_bytes = BASE_METADATA.read_bytes()
    base_sha = sha256(base_bytes)
    metadata_sha = sha256(metadata_bytes)
    if base_sha != EXPECTED_BASE_NOTEBOOK_SHA256:
        raise ValueError(f"Unexpected base Notebook hash: {base_sha}")
    if metadata_sha != EXPECTED_METADATA_SHA256:
        raise ValueError(f"Unexpected metadata hash: {metadata_sha}")

    metadata = json.loads(metadata_bytes.decode("utf-8"))
    if metadata.get("id") != KERNEL_SLUG:
        raise ValueError(f"Unexpected kernel id: {metadata.get('id')!r}")
    if not metadata.get("is_private"):
        raise ValueError("The pinned source kernel must remain private")

    original_text = base_bytes.decode("utf-8")
    notebook = json.loads(original_text)
    original_cells = json.loads(original_text)["cells"]
    cell = "".join(notebook["cells"][3]["source"])
    magic = "%%writefile /kaggle/harness-changes.patch\n"
    if not cell.startswith(magic):
        raise ValueError("Pinned Notebook cell 3 magic does not match")
    patch_text = cell[len(magic) :]

    repeated_anchor = (
        "+        class RepeatedActionInStateError(BaseException):\n"
        "+            pass\n"
        "+\n"
    )
    repeated_addition = (
        "+        class ActionPlanLimitError(BaseException):\n"
        "+            pass\n"
        "+\n"
        "+        _MAX_ACTIONS_PER_SNIPPET = 8\n"
        "+        _actions_executed_in_snippet = 0\n"
        "+\n"
    )
    patch_text = replace_once(patch_text, repeated_anchor, repeated_anchor + repeated_addition)
    patch_text = replace_once(
        patch_text,
        "         def action(actions):\n",
        "         def action(actions):\n"
        "+            nonlocal _actions_executed_in_snippet\n",
    )
    patch_text = replace_once(
        patch_text,
        "             normalized_actions = _normalize_actions(actions)\n",
        "             normalized_actions = _normalize_actions(actions)\n"
        "+            _remaining_actions = _MAX_ACTIONS_PER_SNIPPET - _actions_executed_in_snippet\n"
        "+            _plan_was_truncated = False\n"
        "+            if normalized_actions:\n"
        "+                if _remaining_actions <= 0:\n"
        "+                    raise ActionPlanLimitError(\n"
        "+                        \"No actions from this call ran: this snippet reached the 8-action \"\n"
        "+                        \"limit. Re-read current_frame and replan in a fresh snippet.\"\n"
        "+                    )\n"
        "+                _plan_was_truncated = len(normalized_actions) > _remaining_actions\n"
        "+                if _plan_was_truncated:\n"
        "+                    normalized_actions = normalized_actions[:_remaining_actions]\n"
        "+\n",
    )
    patch_text = replace_once(
        patch_text,
        "             action_results.append(action_result)\n",
        "             action_results.append(action_result)\n"
        "+            _executed_for_cap = action_result.get(\"executed_actions\")\n"
        "+            if isinstance(_executed_for_cap, list):\n"
        "+                _actions_executed_in_snippet += len(_executed_for_cap)\n"
        "+            elif action_result.get(\"executed\"):\n"
        "+                _actions_executed_in_snippet += 1\n",
    )
    patch_text = replace_once(
        patch_text,
        "             return action_result\n",
        "+            if _plan_was_truncated and not _terminal_state:\n"
        "+                raise ActionPlanLimitError(\n"
        "+                    \"Only a prefix ran before the 8-action per-snippet limit; the remaining \"\n"
        "+                    \"plan did not run. Re-read current_frame and replan in a fresh snippet.\"\n"
        "+                )\n"
        "             return action_result\n",
    )
    patch_text = replace_once(
        patch_text,
        "+            TerminalStateActionError,\n",
        "+            TerminalStateActionError,\n"
        "+            ActionPlanLimitError,\n",
    )

    updated_patch, hunk_details = update_python_sandbox_hunks(patch_text)
    notebook["cells"][3]["source"] = (magic + updated_patch).splitlines(keepends=True)
    changed_cells = [
        index
        for index, (before, after) in enumerate(zip(original_cells, notebook["cells"]))
        if before != after
    ]
    if changed_cells != [3]:
        raise ValueError(f"Expected only Notebook cell 3 to change, got {changed_cells}")

    exercise_cap_boundaries()
    notebook_text = json.dumps(notebook, ensure_ascii=False, indent=1) + "\n"
    if OUTPUT_DIR.exists() and any(OUTPUT_DIR.iterdir()):
        raise FileExistsError(f"Refusing to overwrite candidate directory: {OUTPUT_DIR}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_notebook = OUTPUT_DIR / "submission.ipynb"
    output_metadata = OUTPUT_DIR / "kernel-metadata.json"
    output_notebook.write_text(notebook_text, encoding="utf-8", newline="\n")
    shutil.copyfile(BASE_METADATA, output_metadata)

    # Parse the saved artifacts again so the evidence describes disk contents.
    saved_notebook = json.loads(output_notebook.read_text(encoding="utf-8"))
    saved_metadata = output_metadata.read_bytes()
    if len(saved_notebook["cells"]) != len(original_cells):
        raise ValueError("Notebook cell count changed")

    observed_trace_grouping = {
        "method": "Count type=action records grouped by analysis_step; not asserted as exact Python-call boundaries.",
        "v28": {
            "analysis_steps": 95,
            "steps_over_8": 12,
            "actions_in_over_8_steps": 145,
            "actions_after_step_8": 49,
        },
        "v29": {
            "analysis_steps": 106,
            "steps_over_8": 15,
            "actions_in_over_8_steps": 180,
            "actions_after_step_8": 60,
        },
        "interpretation": "Diagnostic motivation only; the action trace does not predict replanned model behavior or score.",
    }

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    evidence = {
        "schema": "arc3-candidate-build.v1",
        "candidate": "C2-105 action-plan cap 8",
        "observed_at_utc": timestamp,
        "base": {
            "kernel_slug": KERNEL_SLUG,
            "kernel_version": 29,
            "kernel_status_observed": "COMPLETE",
            "notebook_sha256": base_sha,
            "metadata_sha256": metadata_sha,
        },
        "candidate": {
            "notebook_path": str(output_notebook.relative_to(ROOT)),
            "notebook_sha256": sha256(output_notebook.read_bytes()),
            "metadata_path": str(output_metadata.relative_to(ROOT)),
            "metadata_sha256": sha256(saved_metadata),
            "changed_notebook_cells": changed_cells,
            "patched_file": "ARC3-Inference/inference/agent/python_tool_sandbox.py",
            "action_limit_per_python_snippet": CAP,
            "hunk_validation": hunk_details,
            "private_score": "NOT_MEASURED",
            "official_score": "NOT_MEASURED",
        },
        "trace_motivation": observed_trace_grouping,
        "private_push": {
            "status": "NOT_ATTEMPTED",
            "fresh_gpu_capacity_evidence_required_before_retry": True,
            "last_rejection_evidence": QUOTA_REJECTION,
            "last_observed_error": "Maximum weekly GPU quota of 30.00 hours reached.",
        },
        "official_submission_or_quota_use": False,
        "boundary_preflight": "PASS",
        "limitations": [
            "Synthetic cap-boundary assertions only; no real game was run.",
            "No Kaggle private kernel execution or score was measured.",
            "No official competition rerun or submission was made.",
        ],
    }
    evidence_path = EVIDENCE_DIR / f"ARC3-C2-105-action-plan-cap8-prepared-{timestamp}.json"
    evidence_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "candidate_notebook": str(output_notebook.relative_to(ROOT)),
                "candidate_notebook_sha256": evidence["candidate"]["notebook_sha256"],
                "evidence": str(evidence_path.relative_to(ROOT)),
                "evidence_sha256": sha256(evidence_path.read_bytes()),
                "hunks": hunk_details,
                "boundary_preflight": "PASS",
                "private_push": "NOT_ATTEMPTED",
                "official_submission_or_quota_use": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
