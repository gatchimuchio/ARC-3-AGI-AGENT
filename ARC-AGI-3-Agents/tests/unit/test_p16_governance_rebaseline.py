from __future__ import annotations

import hashlib
import json
from pathlib import Path

REQUIRED_ROLES = {
    "DEVELOPMENT_TRAIN",
    "DEVELOPMENT_VALIDATION",
    "CV_HOLDOUT",
    "LOCKED_FINAL",
    "OFFICIAL_PUBLIC",
    "OFFICIAL_PRIVATE",
}


def _canonical_digest(payload: dict[str, object]) -> str:
    body = dict(payload)
    body.pop("content_digest", None)
    canonical = json.dumps(
        body,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class TestP16GovernanceRebaseline:
    repository_root = Path(__file__).resolve().parents[3]
    phase_state_path = repository_root / "control" / "p16" / "P16_PHASE_STATE.json"
    evaluation_registry_path = (
        repository_root / "control" / "p16" / "EVALUATION_ROLE_REGISTRY.json"
    )

    def test_rev2_authority_documents_are_retained_exactly(self) -> None:
        expected = {
            (
                self.repository_root
                / "docs"
                / "architecture"
                / "ARC3_GENERIC_AUTONOMOUS_COMPLETION_SPEC_REV2.md"
            ): "9746e981e504e46b8563aa8a342aa567937762363d66a288ff8235a5c29591c2",
            (
                self.repository_root
                / "docs"
                / "roadmap"
                / "P16_P24_GENERIC_AUTONOMOUS_COMPLETION_ROADMAP_REV2.md"
            ): "c8897ce4b379865aea091b04cdf3a1f772a5f3765ef20744998e58d65ba6c687",
        }
        for path, digest in expected.items():
            assert path.is_file()
            assert hashlib.sha256(path.read_bytes()).hexdigest() == digest

    def test_all_p16_governance_documents_exist(self) -> None:
        required = (
            "docs/audit/ARC3_GENERIC_REAUDIT_REV2.md",
            "docs/security/IDENTITY_TAINT_THREAT_MODEL.md",
            "docs/evaluation/EVALUATION_ROLE_REGISTRY_SPEC.md",
            "docs/official/OFFICIAL_COMPLETION_PREDICATES.md",
            "control/p16/P16_PHASE_STATE.json",
            "control/p16/EVALUATION_ROLE_REGISTRY.json",
        )
        assert all((self.repository_root / path).is_file() for path in required)

    def test_p16_phase_state_is_content_bound_and_closed(self) -> None:
        state = json.loads(self.phase_state_path.read_text(encoding="utf-8"))
        assert state["status"] == "PASS"
        assert state["active_runtime_count"] == 1
        assert state["claim_overstatement_count"] == 0
        assert state["rev1_status"] == "HISTORICAL_NON_BLOCKING"
        assert state["runtime_changes_performed"] is False
        assert state["later_phases_activated"] is False
        assert state["failed_requirement_ids"] == []
        assert state["gates"] == {
            f"P16-{index:03d}": "PASS" for index in range(1, 7)
        }
        assert state["content_digest"] == _canonical_digest(state)

    def test_exactly_one_runtime_path_is_active(self) -> None:
        state = json.loads(self.phase_state_path.read_text(encoding="utf-8"))
        active = [
            item
            for item in state["runtime_paths"]
            if item["classification"] == "ACTIVE_RECONSTRUCTION_TARGET"
        ]
        assert len(active) == 1
        assert active[0]["id"] == "GENERIC_AGI_RUNTIME_V1"
        assert all(
            item["classification"] != "ACTIVE_RECONSTRUCTION_TARGET"
            for item in state["runtime_paths"]
            if item["id"] != "GENERIC_AGI_RUNTIME_V1"
        )

    def test_evaluation_registry_separates_all_six_roles(self) -> None:
        registry = json.loads(
            self.evaluation_registry_path.read_text(encoding="utf-8")
        )
        assert {item["id"] for item in registry["roles"]} == REQUIRED_ROLES
        assert registry["role_overlap_allowed_per_execution"] is False
        assert registry["cv_runtime_identity_shared_across_folds"] is False
        assert registry["locked_final_max_execution_count"] == 1
        assert registry["content_digest"] == _canonical_digest(registry)

        assets = {item["asset_id"]: item for item in registry["assets"]}
        assert assets["P12_SEALED_CUSTOM_ENV"]["access_state"] == (
            "HISTORICAL_CONSUMED"
        )
        assert assets["LOCKED_FINAL_REV2"]["access_state"] == "NOT_PROVISIONED"
        assert assets["ARC3_OFFICIAL_PUBLIC_CURRENT_ARTIFACT"][
            "access_state"
        ] == "NOT_OBSERVED"
        assert assets["ARC3_OFFICIAL_PRIVATE_CURRENT_ARTIFACT"][
            "access_state"
        ] == "NOT_OBSERVED"

    def test_claim_registry_does_not_promote_progress_to_completion(self) -> None:
        registry = (
            self.repository_root
            / "docs"
            / "architecture"
            / "AGI_CLAIM_REGISTRY.md"
        ).read_text(encoding="utf-8")
        assert "| `CLAIM_GENERICITY`" in registry
        assert "| `HISTORICAL_ONLY`" in next(
            line for line in registry.splitlines() if "`CLAIM_GENERICITY`" in line
        )
        for claim in (
            "STRUCTURAL_READY",
            "KNOWN_PUBLIC_REGRESSION",
            "MEMORY_CAUSAL",
            "P_VERSION_LEARNING_CAUSAL",
            "SEALED_SINGLE_ARTIFACT_COMPLETE",
            "COMPETITION_READY",
            "OFFICIAL_RUN_ACCEPTED",
            "OFFICIAL_PUBLIC_COMPLETE",
            "OFFICIAL_PRIVATE_COMPLETE",
            "OFFICIAL_FULL_COMPLETE",
        ):
            line = next(
                item for item in registry.splitlines() if f"`{claim}`" in item
            )
            assert "`SUPPORTED`" not in line

    def test_threat_model_distinguishes_dynamic_and_precomputed_coordinates(
        self,
    ) -> None:
        threat_model = (
            self.repository_root
            / "docs"
            / "security"
            / "IDENTITY_TAINT_THREAT_MODEL.md"
        ).read_text(encoding="utf-8")
        assert "`CURRENT_RENDER_COORDINATE`" in threat_model
        assert "`PRECOMPUTED_COORDINATE`" in threat_model
        assert "OrchestrationMetadata" in threat_model
        assert "runtime enforcement status: `PARTIAL_CURRENT`" in threat_model

    def test_official_predicates_require_score_bytes_and_exact_artifact(
        self,
    ) -> None:
        predicates = (
            self.repository_root
            / "docs"
            / "official"
            / "OFFICIAL_COMPLETION_PREDICATES.md"
        ).read_text(encoding="utf-8")
        for term in (
            "submission_status == COMPLETE",
            "output_bytes > 0",
            "score_returned",
            "exact_runtime_package_digest_verified",
            "PUBLIC_55",
            "PRIVATE_55",
            "FULL_110",
            "OFFICIAL_NOT_OBSERVED",
        ):
            assert term in predicates

    def test_rev1_is_explicitly_historical_non_blocking(self) -> None:
        for relative_path in (
            "docs/architecture/ARC3_AGI_ACCEPTANCE_SPEC_REV1.md",
            "docs/audit/EXTERNAL_AGI_CONFORMANCE_AUDIT_REV1.md",
        ):
            text = (self.repository_root / relative_path).read_text(encoding="utf-8")
            assert "HISTORICAL_NON_BLOCKING" in text
