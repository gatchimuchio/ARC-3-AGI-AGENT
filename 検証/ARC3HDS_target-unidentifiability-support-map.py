from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = ROOT / "検証/ARC3HDS_target-unidentifiability-audit.py"
SPEC = importlib.util.spec_from_file_location("c2_103_target_audit", AUDIT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Could not load target audit from {AUDIT_PATH}")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


GAME = "tn36-ef4dde99"
TARGET_STEPS = 14
FEATURE_PATHS = {
    "component_area": ("作用前公開状態", "作用点同色4連結成分面積"),
    "color_count": ("作用前公開状態", "色種類数"),
    "local_layout": ("作用前公開状態", "対象局所配置"),
}


def _at_path(value: Any, path: tuple[str, ...]) -> Any:
    for part in path:
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _experience_view(experience: Any, source_step: int | None) -> dict[str, Any]:
    raw = experience.原入力 if isinstance(experience.原入力, dict) else {}
    return {
        "experience_ref": experience.経験識別子,
        "source_public_step": source_step,
        "action_number": _at_path(raw, ("作用", "番号")),
        "observed_response": _at_path(raw, ("公開応答区分",)),
        "features": {
            name: _at_path(raw, path) for name, path in FEATURE_PATHS.items()
        },
    }


def run(artifacts: Path) -> dict[str, Any]:
    AUDIT._install_diagnostic_projection()
    state_path, _, rows = AUDIT._ABLA.load_rows(artifacts, GAME)
    if len(rows) < TARGET_STEPS:
        raise RuntimeError(f"Expected {TARGET_STEPS} public transitions, got {len(rows)}")

    bridge = AUDIT.VisualHDSBridge(
        update_budget=TARGET_STEPS,
        query_budget=TARGET_STEPS,
        hds_seconds_budget=120.0,
    )
    if bridge.prior_report.get("loaded_count") != 5:
        raise RuntimeError(f"Expected five prior observations: {bridge.prior_report}")

    source_step_by_ref: dict[str, int] = {}
    records: list[dict[str, Any]] = []
    for row in rows[:TARGET_STEPS]:
        step = row["public_step_before"]
        update = copy.deepcopy(row["projected_update_input"])
        query = bridge._call("query", AUDIT._ABLA.query_input(update))
        if query.get("bridge_status") != "queried":
            raise RuntimeError(f"HDS query failed at public step {step}: {query}")
        if query.get("authorization") is not False:
            raise RuntimeError(f"HDS authorization changed at public step {step}")

        engine = bridge._hds.エンジン
        experiences = engine.台帳.取得("観測台帳")
        experience_by_ref = {item.経験識別子: item for item in experiences}
        for record in query.get("target_unidentifiable_evidence", []):
            support_refs = record.get("support_refs", [])
            selected = [experience_by_ref[ref] for ref in support_refs if ref in experience_by_ref]
            records.append(
                {
                    "query_public_step": step,
                    "action_number": _at_path(update, ("作用", "番号")),
                    "observed_response_after_action": _at_path(
                        update, ("公開応答区分",)
                    ),
                    "unidentifiable_record": record,
                    "support_experience_count": len(selected),
                    "support_experiences": [
                        _experience_view(item, source_step_by_ref.get(item.経験識別子))
                        for item in selected
                    ],
                }
            )

        update.pop(AUDIT.POST_ACTION_FEATURE, None)
        before_refs = set(experience_by_ref)
        updated = bridge._call("update", update)
        if updated.get("bridge_status") != "updated":
            raise RuntimeError(f"HDS update failed at public step {step}: {updated}")
        after = engine.台帳.取得("観測台帳")
        new_experiences = [item for item in after if item.経験識別子 not in before_refs]
        if len(new_experiences) != 1:
            raise RuntimeError(
                f"Expected one experience at public step {step}, got {len(new_experiences)}"
            )
        source_step_by_ref[new_experiences[0].経験識別子] = step

    referenced = {
        item["experience_ref"]
        for record in records
        for item in record["support_experiences"]
    }
    unresolved = sorted(ref for ref in referenced if ref not in source_step_by_ref)
    return {
        "schema": "arc3-hds-target-unidentifiability-support-map.v1",
        "game": GAME,
        "public_input_state_sha256": AUDIT.sha256(state_path),
        "transitions_replayed": TARGET_STEPS,
        "prior_count": bridge.prior_report.get("loaded_count"),
        "query_before_each_update": True,
        "post_action_effect_excluded_from_updates": True,
        "action_authorization_false": True,
        "target_unidentifiable_query_count": len(records),
        "distinct_support_experience_refs": len(referenced),
        "support_refs_without_public_step_mapping": unresolved,
        "records": records,
        "score_effect": "NOT_MEASURED",
        "official_submission_or_kernel_run": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Map target-scoped HDS support refs to the public transition that created each experience."
    )
    parser.add_argument("--artifacts", type=Path, default=AUDIT.DEFAULT_ARTIFACTS)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.artifacts)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "output_path": str(args.output.resolve()),
                "output_sha256": AUDIT.sha256(args.output),
                "target_unidentifiable_query_count": result[
                    "target_unidentifiable_query_count"
                ],
                "distinct_support_experience_refs": result[
                    "distinct_support_experience_refs"
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
