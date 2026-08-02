#!/usr/bin/env python3
"""Build or verify the deterministic rev4 current-authority manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Final

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH: Final = Path("docs/strategy/REV4_CURRENT_AUTHORITY_MANIFEST.json")
PRODUCT_ID: Final = "ARC3_COMPLETION_AGI_AGENT_PRODUCT_REV4"
ACTIVE_MILESTONE: Final = "M0_PRODUCT_BASELINE_AND_BLOCKER_CLOSURE"

AUTHORITY_ENTRIES: Final[tuple[tuple[str, str], ...]] = (
    ("AGENTS.md", "CURRENT_EXECUTION_CONTROL"),
    ("README.md", "PRODUCT_OPERATOR_DOCUMENTATION"),
    (
        "ARC-AGI-3-Agents/README.md",
        "PRODUCT_PACKAGE_OPERATOR_DOCUMENTATION",
    ),
    (
        "docs/architecture/AGI三主体統合設計正本_v0_2.md",
        "NORMATIVE_AGI_ARCHITECTURE",
    ),
    (
        "docs/references/HDS_FRAMEWORK_rev3_1a_INTERNAL.md",
        "NORMATIVE_HDS_SPECIFICATION",
    ),
    (
        "docs/architecture/工学的AGI実装仕様書_v0_2.md",
        "NORMATIVE_ENGINEERING_SPECIFICATION",
    ),
    (
        "docs/strategy/ARC3_AGIエージェント_製品仕様書_rev4.md",
        "ARC3_PRODUCT_SPECIFICATION",
    ),
    (
        "docs/roadmap/ARC3_AGIエージェント_製品開発ロードマップ_rev4.md",
        "ARC3_PRODUCT_ROADMAP",
    ),
    ("control/rev4/CURRENT_TASK.json", "SOLE_CURRENT_SELECTOR"),
    (
        "control/rev4/LEGACY_REV3_CLASSIFICATION.json",
        "LEGACY_AUTHORITY_BOUNDARY",
    ),
    (
        "docs/strategy/contracts/REV4_PRODUCT_GOVERNANCE_CONTRACT_V1.json",
        "MACHINE_GOVERNANCE_CONTRACT",
    ),
    (
        "control/rev3/REV3_CURRENT_SELECTOR.json",
        "HISTORICAL_REV3_SELECTOR_SNAPSHOT",
    ),
    (
        "docs/strategy/REV3_CURRENT_AUTHORITY_MANIFEST.json",
        "HISTORICAL_REV3_AUTHORITY_SNAPSHOT",
    ),
    (
        "ARC-AGI-3-Agents/arc3_agi_agent/rev3_governance.py",
        "HISTORICAL_REV3_RUNTIME_BOUNDARY",
    ),
    (
        "scripts/validate_rev3_governance.py",
        "HISTORICAL_REV3_SNAPSHOT_VALIDATOR",
    ),
    (
        "ARC-AGI-3-Agents/agents/templates/arc3_completion_agent.py",
        "PRODUCT_ENTRYPOINT",
    ),
    (
        "ARC-AGI-3-Agents/agents/templates/generic_agi_agent.py",
        "PRODUCT_RUNTIME_ENTRYPOINT_BASE",
    ),
    (
        "ARC-AGI-3-Agents/arc3_agi_agent/generic_competition_runner.py",
        "PRODUCT_SEQUENTIAL_ORCHESTRATOR",
    ),
    (
        "ARC-AGI-3-Agents/arc3_agi_agent/product_governance.py",
        "PRODUCT_ENDPOINT_CONTRACT",
    ),
    (
        "ARC-AGI-3-Agents/arc3_agi_agent/product_runner.py",
        "PRODUCT_ACCEPTANCE_RUNNER",
    ),
    ("ARC-AGI-3-Agents/pyproject.toml", "PRODUCT_PACKAGE_ENTRYPOINT"),
    (
        "scripts/validate_rev4_product_governance.py",
        "CURRENT_GOVERNANCE_VALIDATOR",
    ),
    (
        "scripts/refresh_rev4_authority_manifest.py",
        "CURRENT_MANIFEST_BUILDER",
    ),
    (
        "scripts/measure_product_resource_bounds.py",
        "PRODUCT_RESOURCE_BOUND_MEASUREMENT",
    ),
    (
        "analysis/product/rev4/product_resource_bounds.json",
        "PRODUCT_RESOURCE_BOUND_EVIDENCE",
    ),
    (
        "ARC-AGI-3-Agents/tests/unit/test_product_runner.py",
        "PRODUCT_RUNNER_ACCEPTANCE_TEST",
    ),
    (
        "ARC-AGI-3-Agents/tests/unit/test_product_governance.py",
        "PRODUCT_GOVERNANCE_ACCEPTANCE_TEST",
    ),
    (
        "ARC-AGI-3-Agents/tests/unit/test_generic_competition_runner.py",
        "PRODUCT_ORCHESTRATOR_REGRESSION_TEST",
    ),
    (
        "ARC-AGI-3-Agents/tests/unit/test_competition_generic_agent.py",
        "PRODUCT_ADAPTER_REGRESSION_TEST",
    ),
    (
        "ARC-AGI-3-Agents/tests/integration/test_product_offline_runner.py",
        "PRODUCT_OFFLINE_INTEGRATION_TEST",
    ),
    (
        "ARC-AGI-3-Agents/tests/unit/test_rev3_strategy_rebaseline.py",
        "CURRENT_HISTORICAL_BOUNDARY_REGRESSION_TEST",
    ),
)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _encoded(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def build_manifest(root: Path) -> dict[str, object]:
    entries: list[dict[str, str]] = []
    for relative, role in AUTHORITY_ENTRIES:
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(f"REV4_AUTHORITY_FILE_MISSING:{relative}")
        entries.append(
            {
                "path": relative,
                "role": role,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    body: dict[str, object] = {
        "schema_version": "arc3-rev4-current-authority-manifest-v1",
        "product_id": PRODUCT_ID,
        "active_milestone": ACTIVE_MILESTONE,
        "current_selector_path": "control/rev4/CURRENT_TASK.json",
        "legacy_rev3_classification_path": (
            "control/rev4/LEGACY_REV3_CLASSIFICATION.json"
        ),
        "generated_by": "scripts/refresh_rev4_authority_manifest.py",
        "digest_excluded_fields": ["content_digest"],
        "entry_count": len(entries),
        "entries": entries,
    }
    digest = hashlib.sha256(_canonical_json(body).encode("utf-8")).hexdigest()
    return {
        **body,
        "content_digest": "rev4-current-authority-manifest:" + digest,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=REPOSITORY_ROOT)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    manifest = build_manifest(root)
    expected = _encoded(manifest)
    path = root / MANIFEST_PATH
    if arguments.write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(expected)
        status = "WRITTEN"
        ok = True
    else:
        ok = path.is_file() and path.read_bytes() == expected
        status = "PASS" if ok else "STALE"
    print(
        json.dumps(
            {
                "entry_count": len(AUTHORITY_ENTRIES),
                "manifest_path": MANIFEST_PATH.as_posix(),
                "status": status,
            },
            sort_keys=True,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
