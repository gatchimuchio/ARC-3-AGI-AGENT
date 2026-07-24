"""Fail-safe filesystem lifecycle for HDS-controlled P10 manifests."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from .instruction_body import (
    clear_p10_instruction_body_caches,
    load_instruction_body,
)
from .p_update import (
    CandidatePBundle,
    HDSPUpdateAuthority,
    PPromotionDirective,
    PPromotionReceipt,
    PRegressionReport,
    PRollbackDirective,
    PUpdateDecision,
    PUpdateProposal,
)
from .protocol import AuthorityViolation
from .schema import digest_object

P10_ACTIVE_MANIFEST_FILENAME = "p10_manifest.json"
P10_CANDIDATE_MANIFEST_FILENAME = "p10_candidate_manifest.json"
P10_PREVIOUS_STABLE_MANIFEST_FILENAME = (
    "p10_previous_stable_manifest.json"
)
P10_PROMOTED_MANIFEST_FILENAME = "p10_promoted_manifest.json"
P10_REJECTED_MANIFEST_FILENAME = "p10_rejected_manifest.json"
P10_MANIFEST_LIFECYCLE_SCHEMA_VERSION = "arc3-p10-manifest-lifecycle-v1"


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected object: {path}")
    return value


def _encoded(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _atomic_write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(_encoded(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _manifest_failures(
    bundle_dir: Path,
    manifest: Mapping[str, object],
    *,
    expected_lifecycle: str,
) -> tuple[str, ...]:
    failures: list[str] = []
    if manifest.get("runtime_identity_free") is not True:
        failures.append("P10_MANIFEST_IDENTITY_FLAG_INVALID")
    actual_lifecycle = manifest.get(
        "lifecycle",
        "ACTIVE",
    )
    if actual_lifecycle != expected_lifecycle:
        failures.append("P10_MANIFEST_LIFECYCLE_INVALID")
    bundles = manifest.get("bundles")
    if not isinstance(bundles, Mapping):
        return (*failures, "P10_MANIFEST_BUNDLES_INVALID")
    for variant in ("P-A", "P-B", "hybrid"):
        entry = bundles.get(variant)
        if not isinstance(entry, Mapping):
            failures.append(f"P10_MANIFEST_ENTRY_INVALID:{variant}")
            continue
        filename = entry.get("filename")
        if (
            not isinstance(filename, str)
            or not filename
            or Path(filename).name != filename
        ):
            failures.append(f"P10_MANIFEST_FILENAME_INVALID:{variant}")
            continue
        bundle_path = bundle_dir / filename
        if not bundle_path.is_file():
            failures.append(f"P10_MANIFEST_BUNDLE_MISSING:{variant}")
            continue
        if hashlib.sha256(bundle_path.read_bytes()).hexdigest() != entry.get(
            "sha256"
        ):
            failures.append(f"P10_MANIFEST_SHA256_MISMATCH:{variant}")
            continue
        body = load_instruction_body(bundle_path)
        if body.body_version != entry.get("body_version"):
            failures.append(f"P10_MANIFEST_VERSION_MISMATCH:{variant}")
        if body.digest() != entry.get("content_digest"):
            failures.append(f"P10_MANIFEST_DIGEST_MISMATCH:{variant}")
        if body.format_id != entry.get("format_id"):
            failures.append(f"P10_MANIFEST_FORMAT_MISMATCH:{variant}")
    return tuple(sorted(set(failures)))


def _hybrid_entry(manifest: Mapping[str, object]) -> Mapping[str, object]:
    bundles = manifest.get("bundles")
    if not isinstance(bundles, Mapping):
        raise TypeError("P10 manifest bundles invalid")
    entry = bundles.get("hybrid")
    if not isinstance(entry, Mapping):
        raise TypeError("P10 hybrid manifest entry invalid")
    return entry


@dataclass(frozen=True, slots=True)
class P10ManifestRollbackReceipt:
    receipt_id: str
    directive_digest: str
    decision_digest: str
    failed_active_manifest_digest: str
    restored_active_manifest_digest: str
    rejected_manifest_digest: str

    @property
    def digest(self) -> str:
        return digest_object(self)


def promote_p10_candidate_manifest(
    *,
    bundle_dir: Path,
    proposal: PUpdateProposal,
    candidate: CandidatePBundle,
    regression_report: PRegressionReport,
    decision: PUpdateDecision,
    directive: PPromotionDirective,
    authority: HDSPUpdateAuthority,
) -> PPromotionReceipt:
    """Promote one fully-gated candidate set; active is the commit point."""

    active_path = bundle_dir / P10_ACTIVE_MANIFEST_FILENAME
    candidate_path = bundle_dir / P10_CANDIDATE_MANIFEST_FILENAME
    active = _json(active_path)
    candidate_manifest = _json(candidate_path)
    active_digest = digest_object(active)
    candidate_manifest_digest = digest_object(candidate_manifest)
    failures = [
        *proposal.validate(),
        *candidate.validate(),
        *regression_report.validate(),
        *_manifest_failures(
            bundle_dir,
            active,
            expected_lifecycle="ACTIVE",
        ),
        *_manifest_failures(
            bundle_dir,
            candidate_manifest,
            expected_lifecycle="CANDIDATE",
        ),
    ]
    if not regression_report.promotion_ready:
        failures.extend(
            "P10_PROMOTION_GATE_FAILED:" + failure
            for failure in regression_report.promotion_failures
        )
    if proposal.source_p_digest != active_digest:
        failures.append("P10_PROMOTION_PROPOSAL_SOURCE_MISMATCH")
    if directive.expected_active_bundle_digest != active_digest:
        failures.append("P10_PROMOTION_ACTIVE_MANIFEST_CHANGED")
    if candidate.manifest_digest != candidate_manifest_digest:
        failures.append("P10_PROMOTION_CANDIDATE_MANIFEST_MISMATCH")
    if candidate.proposal_digest != proposal.digest:
        failures.append("P10_PROMOTION_PROPOSAL_MISMATCH")
    hybrid = _hybrid_entry(candidate_manifest)
    if hybrid.get("body_version") != candidate.body_version:
        failures.append("P10_PROMOTION_HYBRID_VERSION_MISMATCH")
    if hybrid.get("content_digest") != candidate.body_digest:
        failures.append("P10_PROMOTION_HYBRID_DIGEST_MISMATCH")
    if regression_report.candidate_bundle_digest != candidate.digest:
        failures.append("P10_PROMOTION_REGRESSION_CANDIDATE_MISMATCH")
    if failures:
        raise AuthorityViolation(";".join(sorted(set(failures))))

    previous_stable = {
        "schema_version": P10_MANIFEST_LIFECYCLE_SCHEMA_VERSION,
        "runtime_identity_free": True,
        "lifecycle": "PREVIOUS_STABLE",
        "manifest_digest": active_digest,
        "manifest": active,
    }
    promoted_active: dict[str, object] = {
        "schema_version": candidate_manifest.get("schema_version"),
        "runtime_identity_free": True,
        "lifecycle": "ACTIVE",
        "compiler_version": candidate_manifest.get("compiler_version"),
        "seed": candidate_manifest.get("seed"),
        "bundles": candidate_manifest.get("bundles"),
        "source_candidate_manifest_digest": candidate_manifest_digest,
        "previous_stable_manifest_digest": active_digest,
        "promotion_decision_digest": decision.digest,
        "promotion_directive_digest": directive.digest,
        "regression_report_digest": regression_report.digest,
    }
    promoted_active_digest = digest_object(promoted_active)
    promoted_candidate = {
        **candidate_manifest,
        "lifecycle": "PROMOTED",
        "promoted_active_manifest_digest": promoted_active_digest,
        "promotion_decision_digest": decision.digest,
        "promotion_directive_digest": directive.digest,
        "regression_report_digest": regression_report.digest,
    }
    registry_digest = digest_object(
        {
            "active": promoted_active_digest,
            "previous_stable": active_digest,
            "candidate": candidate.digest,
            "candidate_archive": digest_object(promoted_candidate),
        }
    )
    receipt = PPromotionReceipt(
        receipt_id="p10-promotion-receipt:"
        + digest_object(
            {
                "directive": directive.digest,
                "active": promoted_active_digest,
                "previous": active_digest,
            }
        )[:24],
        directive_digest=directive.digest,
        decision_digest=decision.digest,
        proposal_digest=proposal.digest,
        previous_active_bundle_digest=active_digest,
        promoted_bundle_digest=candidate.digest,
        previous_stable_bundle_digest=active_digest,
        registry_digest=registry_digest,
    )

    directive.consume(decision, authority)
    _atomic_write(
        bundle_dir / P10_PREVIOUS_STABLE_MANIFEST_FILENAME,
        previous_stable,
    )
    _atomic_write(
        bundle_dir / P10_PROMOTED_MANIFEST_FILENAME,
        promoted_candidate,
    )
    _atomic_write(candidate_path, promoted_candidate)
    _atomic_write(active_path, promoted_active)
    clear_p10_instruction_body_caches()
    if digest_object(_json(active_path)) != promoted_active_digest:
        raise RuntimeError("P10_PROMOTION_ACTIVE_VERIFY_FAILED")
    return receipt


def archive_current_promoted_manifest(bundle_dir: Path) -> str:
    """Preserve the promoted candidate before a later compile reuses its slot."""

    promoted = _json(bundle_dir / P10_CANDIDATE_MANIFEST_FILENAME)
    failures = _manifest_failures(
        bundle_dir,
        promoted,
        expected_lifecycle="PROMOTED",
    )
    if failures:
        raise ValueError(";".join(failures))
    _atomic_write(
        bundle_dir / P10_PROMOTED_MANIFEST_FILENAME,
        promoted,
    )
    return digest_object(promoted)


def rollback_p10_active_manifest(
    *,
    bundle_dir: Path,
    failed_active: CandidatePBundle,
    decision: PUpdateDecision,
    directive: PRollbackDirective,
    authority: HDSPUpdateAuthority,
) -> P10ManifestRollbackReceipt:
    """Restore the byte-equivalent previous stable manifest via HDS grant."""

    active_path = bundle_dir / P10_ACTIVE_MANIFEST_FILENAME
    previous_path = bundle_dir / P10_PREVIOUS_STABLE_MANIFEST_FILENAME
    active = _json(active_path)
    previous_wrapper = _json(previous_path)
    previous = previous_wrapper.get("manifest")
    if not isinstance(previous, dict):
        raise AuthorityViolation("P10_ROLLBACK_PREVIOUS_MANIFEST_INVALID")
    active_digest = digest_object(active)
    previous_digest = digest_object(previous)
    failures = [
        *failed_active.validate(),
        *_manifest_failures(
            bundle_dir,
            active,
            expected_lifecycle="ACTIVE",
        ),
        *_manifest_failures(
            bundle_dir,
            previous,
            expected_lifecycle="ACTIVE",
        ),
    ]
    if failed_active.lifecycle != "ACTIVE":
        failures.append("P10_ROLLBACK_FAILED_BUNDLE_NOT_ACTIVE")
    if failed_active.manifest_digest != active_digest:
        failures.append("P10_ROLLBACK_ACTIVE_MANIFEST_MISMATCH")
    hybrid = _hybrid_entry(active)
    if hybrid.get("body_version") != failed_active.body_version:
        failures.append("P10_ROLLBACK_HYBRID_VERSION_MISMATCH")
    if hybrid.get("content_digest") != failed_active.body_digest:
        failures.append("P10_ROLLBACK_HYBRID_DIGEST_MISMATCH")
    if previous_wrapper.get("lifecycle") != "PREVIOUS_STABLE":
        failures.append("P10_ROLLBACK_PREVIOUS_LIFECYCLE_INVALID")
    if previous_wrapper.get("manifest_digest") != previous_digest:
        failures.append("P10_ROLLBACK_PREVIOUS_DIGEST_INVALID")
    if directive.rollback_bundle_digest != previous_digest:
        failures.append("P10_ROLLBACK_TARGET_MISMATCH")
    if failures:
        raise AuthorityViolation(";".join(sorted(set(failures))))

    rejected = {
        "schema_version": P10_MANIFEST_LIFECYCLE_SCHEMA_VERSION,
        "runtime_identity_free": True,
        "lifecycle": "REJECTED",
        "manifest_digest": active_digest,
        "manifest": active,
        "rollback_decision_digest": decision.digest,
        "rollback_directive_digest": directive.digest,
    }
    rejected_digest = digest_object(rejected)
    receipt = P10ManifestRollbackReceipt(
        receipt_id="p10-rollback-receipt:"
        + digest_object(
            {
                "directive": directive.digest,
                "failed": active_digest,
                "restored": previous_digest,
            }
        )[:24],
        directive_digest=directive.digest,
        decision_digest=decision.digest,
        failed_active_manifest_digest=active_digest,
        restored_active_manifest_digest=previous_digest,
        rejected_manifest_digest=rejected_digest,
    )

    directive.consume(decision, authority)
    _atomic_write(
        bundle_dir / P10_REJECTED_MANIFEST_FILENAME,
        rejected,
    )
    _atomic_write(active_path, previous)
    clear_p10_instruction_body_caches()
    if digest_object(_json(active_path)) != previous_digest:
        raise RuntimeError("P10_ROLLBACK_ACTIVE_VERIFY_FAILED")
    return receipt


def promotion_receipt_mapping(
    receipt: PPromotionReceipt,
) -> dict[str, object]:
    return {
        "schema_version": P10_MANIFEST_LIFECYCLE_SCHEMA_VERSION,
        **asdict(receipt),
        "receipt_digest": receipt.digest,
    }


__all__ = [
    "P10_ACTIVE_MANIFEST_FILENAME",
    "P10_CANDIDATE_MANIFEST_FILENAME",
    "P10_MANIFEST_LIFECYCLE_SCHEMA_VERSION",
    "P10_PREVIOUS_STABLE_MANIFEST_FILENAME",
    "P10_PROMOTED_MANIFEST_FILENAME",
    "P10_REJECTED_MANIFEST_FILENAME",
    "P10ManifestRollbackReceipt",
    "archive_current_promoted_manifest",
    "promote_p10_candidate_manifest",
    "promotion_receipt_mapping",
    "rollback_p10_active_manifest",
]
