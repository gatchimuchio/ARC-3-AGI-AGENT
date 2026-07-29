"""Content-bound runtime version lineage and migration gates."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Final

from .runtime_identity import RuntimeIdentity
from .schema import digest_object

VERSION_LINEAGE_VERSION: Final = "arc3-runtime-version-lineage-v1"
P_MIGRATION_DISPOSITIONS: Final = frozenset(
    {"NOT_REQUIRED", "MIGRATED", "REJECTED"}
)
_COMMIT = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")


@dataclass(frozen=True, slots=True)
class CodeUpdateManifest:
    external_commit: str
    source_tree_digest: str
    from_l0_abi_version: str
    to_l0_abi_version: str
    p_migration_disposition: str
    migrated_p_logical_digest: str
    full_regression_passed: bool

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not _COMMIT.fullmatch(self.external_commit):
            failures.append("VERSION_LINEAGE_EXTERNAL_COMMIT_INVALID")
        if not self.source_tree_digest:
            failures.append("VERSION_LINEAGE_SOURCE_DIGEST_MISSING")
        if not self.from_l0_abi_version or not self.to_l0_abi_version:
            failures.append("VERSION_LINEAGE_ABI_VERSION_MISSING")
        if self.p_migration_disposition not in P_MIGRATION_DISPOSITIONS:
            failures.append("VERSION_LINEAGE_P_MIGRATION_INVALID")
        changed = self.from_l0_abi_version != self.to_l0_abi_version
        if changed and self.p_migration_disposition not in {
            "MIGRATED",
            "REJECTED",
        }:
            failures.append("VERSION_LINEAGE_ABI_MIGRATION_REQUIRED")
        if (
            changed
            and self.p_migration_disposition == "MIGRATED"
            and not self.migrated_p_logical_digest
        ):
            failures.append("VERSION_LINEAGE_MIGRATED_P_MISSING")
        if not changed and self.p_migration_disposition != "NOT_REQUIRED":
            failures.append("VERSION_LINEAGE_SPURIOUS_P_MIGRATION")
        if self.full_regression_passed is not True:
            failures.append("VERSION_LINEAGE_FULL_REGRESSION_REQUIRED")
        return tuple(sorted(set(failures)))

    def digest(self) -> str:
        failures = self.validate()
        if failures:
            raise ValueError(";".join(failures))
        return "code-update:" + digest_object(self)


@dataclass(frozen=True, slots=True)
class MemorySchemaMigration:
    migration_id: str
    from_schema_version: str
    to_schema_version: str
    deterministic: bool
    full_regression_passed: bool

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if (
            not self.migration_id
            or not self.from_schema_version
            or not self.to_schema_version
        ):
            failures.append("MEMORY_MIGRATION_METADATA_MISSING")
        if self.from_schema_version == self.to_schema_version:
            failures.append("MEMORY_MIGRATION_SCHEMA_UNCHANGED")
        if self.deterministic is not True:
            failures.append("MEMORY_MIGRATION_NONDETERMINISTIC")
        if self.full_regression_passed is not True:
            failures.append("MEMORY_MIGRATION_REGRESSION_REQUIRED")
        return tuple(sorted(set(failures)))

    def digest(self) -> str:
        failures = self.validate()
        if failures:
            raise ValueError(";".join(failures))
        return "memory-schema-migration:" + digest_object(self)


@dataclass(frozen=True, slots=True)
class RuntimeVersion:
    version_id: str
    parent_version_id: str | None
    status: str
    runtime_identity: RuntimeIdentity
    initial_state_logical_digest: str
    p_logical_digest: str
    code_commit: str
    l0_abi_version: str
    memory_schema_version: str
    transition_digest: str
    version_digest: str

    @property
    def runtime_identity_digest(self) -> str:
        return self.runtime_identity.digest()


@dataclass(frozen=True, slots=True)
class VersionLineageEvent:
    ordinal: int
    operation: str
    source_version_id: str
    target_version_id: str
    transition_digest: str
    previous_event_digest: str
    event_digest: str


def _version_digest(
    *,
    version_id: str,
    parent_version_id: str | None,
    runtime_identity_digest: str,
    initial_state_logical_digest: str,
    p_logical_digest: str,
    code_commit: str,
    l0_abi_version: str,
    memory_schema_version: str,
    transition_digest: str,
) -> str:
    return "runtime-version:" + digest_object(
        {
            "version_id": version_id,
            "parent_version_id": parent_version_id,
            "runtime_identity_digest": runtime_identity_digest,
            "initial_state_logical_digest": initial_state_logical_digest,
            "p_logical_digest": p_logical_digest,
            "code_commit": code_commit,
            "l0_abi_version": l0_abi_version,
            "memory_schema_version": memory_schema_version,
            "transition_digest": transition_digest,
        }
    )


@dataclass(slots=True)
class VersionLineage:
    _versions: list[RuntimeVersion] = field(default_factory=list, repr=False)
    _events: list[VersionLineageEvent] = field(
        default_factory=list,
        repr=False,
    )

    @classmethod
    def bootstrap(
        cls,
        *,
        version_id: str,
        runtime_identity: RuntimeIdentity,
        initial_state_logical_digest: str,
        p_logical_digest: str,
        code_commit: str,
        memory_schema_version: str,
    ) -> VersionLineage:
        identity_failures = runtime_identity.validate()
        if identity_failures:
            raise ValueError(";".join(identity_failures))
        if (
            not version_id
            or not initial_state_logical_digest
            or not p_logical_digest
            or not memory_schema_version
        ):
            raise ValueError("VERSION_LINEAGE_GENESIS_METADATA_MISSING")
        if not _COMMIT.fullmatch(code_commit):
            raise ValueError("VERSION_LINEAGE_EXTERNAL_COMMIT_INVALID")
        transition = "runtime-version-genesis"
        version = RuntimeVersion(
            version_id=version_id,
            parent_version_id=None,
            status="ACTIVE",
            runtime_identity=runtime_identity,
            initial_state_logical_digest=initial_state_logical_digest,
            p_logical_digest=p_logical_digest,
            code_commit=code_commit,
            l0_abi_version=runtime_identity.l0_abi_version,
            memory_schema_version=memory_schema_version,
            transition_digest=transition,
            version_digest=_version_digest(
                version_id=version_id,
                parent_version_id=None,
                runtime_identity_digest=runtime_identity.digest(),
                initial_state_logical_digest=initial_state_logical_digest,
                p_logical_digest=p_logical_digest,
                code_commit=code_commit,
                l0_abi_version=runtime_identity.l0_abi_version,
                memory_schema_version=memory_schema_version,
                transition_digest=transition,
            ),
        )
        return cls(_versions=[version])

    @property
    def versions(self) -> tuple[RuntimeVersion, ...]:
        return tuple(self._versions)

    @property
    def events(self) -> tuple[VersionLineageEvent, ...]:
        return tuple(self._events)

    @property
    def active(self) -> RuntimeVersion:
        active = tuple(
            item for item in self._versions if item.status == "ACTIVE"
        )
        if len(active) != 1:
            raise RuntimeError("VERSION_LINEAGE_ACTIVE_COUNT_INVALID")
        return active[0]

    @property
    def active_runtime_count(self) -> int:
        return sum(item.status == "ACTIVE" for item in self._versions)

    def _append_event(
        self,
        *,
        operation: str,
        source_version_id: str,
        target_version_id: str,
        transition_digest: str,
    ) -> None:
        ordinal = len(self._events)
        previous = (
            self._events[-1].event_digest
            if self._events
            else "runtime-version-lineage-genesis"
        )
        event_digest = "runtime-version-event:" + digest_object(
            {
                "ordinal": ordinal,
                "operation": operation,
                "source_version_id": source_version_id,
                "target_version_id": target_version_id,
                "transition_digest": transition_digest,
                "previous_event_digest": previous,
            }
        )
        self._events.append(
            VersionLineageEvent(
                ordinal=ordinal,
                operation=operation,
                source_version_id=source_version_id,
                target_version_id=target_version_id,
                transition_digest=transition_digest,
                previous_event_digest=previous,
                event_digest=event_digest,
            )
        )

    def append_successor(
        self,
        *,
        version_id: str,
        runtime_identity: RuntimeIdentity,
        initial_state_logical_digest: str,
        p_logical_digest: str,
        memory_schema_version: str,
        code_update: CodeUpdateManifest,
        memory_migration: MemorySchemaMigration | None = None,
    ) -> RuntimeVersion:
        parent = self.active
        if (
            not version_id
            or not initial_state_logical_digest
            or not p_logical_digest
            or not memory_schema_version
        ):
            raise ValueError("VERSION_LINEAGE_TARGET_METADATA_MISSING")
        if any(item.version_id == version_id for item in self._versions):
            raise ValueError("VERSION_LINEAGE_VERSION_ID_REUSED")
        identity_failures = runtime_identity.validate()
        code_failures = code_update.validate()
        if identity_failures or code_failures:
            raise ValueError(";".join((*identity_failures, *code_failures)))
        if code_update.from_l0_abi_version != parent.l0_abi_version:
            raise PermissionError("VERSION_LINEAGE_PARENT_ABI_MISMATCH")
        if code_update.to_l0_abi_version != runtime_identity.l0_abi_version:
            raise PermissionError("VERSION_LINEAGE_TARGET_ABI_MISMATCH")
        if code_update.source_tree_digest != runtime_identity.code_tree_digest:
            raise PermissionError("VERSION_LINEAGE_SOURCE_DIGEST_MISMATCH")
        if (
            code_update.p_migration_disposition == "MIGRATED"
            and code_update.migrated_p_logical_digest != p_logical_digest
        ):
            raise PermissionError("VERSION_LINEAGE_MIGRATED_P_MISMATCH")
        schema_changed = (
            memory_schema_version != parent.memory_schema_version
        )
        if schema_changed:
            if memory_migration is None:
                raise PermissionError("MEMORY_SCHEMA_MIGRATION_REQUIRED")
            failures = memory_migration.validate()
            if failures:
                raise ValueError(";".join(failures))
            if (
                memory_migration.from_schema_version
                != parent.memory_schema_version
                or memory_migration.to_schema_version
                != memory_schema_version
            ):
                raise PermissionError("MEMORY_SCHEMA_MIGRATION_BINDING_INVALID")
        elif memory_migration is not None:
            raise ValueError("MEMORY_SCHEMA_MIGRATION_SPURIOUS")
        transition_digest = "runtime-transition:" + digest_object(
            {
                "parent": parent.version_digest,
                "code_update": code_update.digest(),
                "memory_migration": (
                    memory_migration.digest()
                    if memory_migration is not None
                    else "NOT_REQUIRED"
                ),
                "target_identity": runtime_identity.digest(),
                "target_initial_state": initial_state_logical_digest,
                "target_p": p_logical_digest,
            }
        )
        rejected = code_update.p_migration_disposition == "REJECTED"
        status = "REJECTED" if rejected else "ACTIVE"
        version = RuntimeVersion(
            version_id=version_id,
            parent_version_id=parent.version_id,
            status=status,
            runtime_identity=runtime_identity,
            initial_state_logical_digest=initial_state_logical_digest,
            p_logical_digest=p_logical_digest,
            code_commit=code_update.external_commit,
            l0_abi_version=runtime_identity.l0_abi_version,
            memory_schema_version=memory_schema_version,
            transition_digest=transition_digest,
            version_digest=_version_digest(
                version_id=version_id,
                parent_version_id=parent.version_id,
                runtime_identity_digest=runtime_identity.digest(),
                initial_state_logical_digest=initial_state_logical_digest,
                p_logical_digest=p_logical_digest,
                code_commit=code_update.external_commit,
                l0_abi_version=runtime_identity.l0_abi_version,
                memory_schema_version=memory_schema_version,
                transition_digest=transition_digest,
            ),
        )
        if not rejected:
            parent_index = self._versions.index(parent)
            previous = replace(parent, status="PREVIOUS_STABLE")
            self._versions[parent_index] = previous
        self._versions.append(version)
        self._append_event(
            operation="REJECT" if rejected else "ACTIVATE",
            source_version_id=parent.version_id,
            target_version_id=version.version_id,
            transition_digest=transition_digest,
        )
        if self.active_runtime_count != 1:
            raise RuntimeError("VERSION_LINEAGE_ACTIVE_COUNT_INVALID")
        return version

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not self._versions or self.active_runtime_count != 1:
            failures.append("VERSION_LINEAGE_ACTIVE_COUNT_INVALID")
        ids = {item.version_id for item in self._versions}
        if len(ids) != len(self._versions):
            failures.append("VERSION_LINEAGE_DUPLICATE_VERSION")
        if self._versions and self._versions[0].parent_version_id is not None:
            failures.append("VERSION_LINEAGE_GENESIS_PARENT_INVALID")
        seen: set[str] = set()
        runtime_digests: set[str] = set()
        for item in self._versions:
            identity_failures = item.runtime_identity.validate()
            failures.extend(identity_failures)
            if item.status not in {
                "ACTIVE",
                "PREVIOUS_STABLE",
                "REJECTED",
            }:
                failures.append("VERSION_LINEAGE_STATUS_INVALID")
            if not _COMMIT.fullmatch(item.code_commit):
                failures.append("VERSION_LINEAGE_EXTERNAL_COMMIT_INVALID")
            if item.l0_abi_version != item.runtime_identity.l0_abi_version:
                failures.append("VERSION_LINEAGE_RUNTIME_ABI_MISMATCH")
            if (
                not item.initial_state_logical_digest
                or not item.p_logical_digest
                or not item.memory_schema_version
                or not item.transition_digest
            ):
                failures.append("VERSION_LINEAGE_VERSION_METADATA_MISSING")
            if item.runtime_identity_digest in runtime_digests:
                failures.append("VERSION_LINEAGE_RUNTIME_IDENTITY_REUSED")
            if (
                item.parent_version_id is not None
                and item.parent_version_id not in seen
            ):
                failures.append("VERSION_LINEAGE_PARENT_UNKNOWN")
            expected_version_digest = _version_digest(
                version_id=item.version_id,
                parent_version_id=item.parent_version_id,
                runtime_identity_digest=item.runtime_identity_digest,
                initial_state_logical_digest=(
                    item.initial_state_logical_digest
                ),
                p_logical_digest=item.p_logical_digest,
                code_commit=item.code_commit,
                l0_abi_version=item.l0_abi_version,
                memory_schema_version=item.memory_schema_version,
                transition_digest=item.transition_digest,
            )
            if item.version_digest != expected_version_digest:
                failures.append("VERSION_LINEAGE_VERSION_DIGEST_INVALID")
            seen.add(item.version_id)
            runtime_digests.add(item.runtime_identity_digest)
        if len(self._events) != max(0, len(self._versions) - 1):
            failures.append("VERSION_LINEAGE_EVENT_COUNT_INVALID")
        by_id = {item.version_id: item for item in self._versions}
        event_targets: set[str] = set()
        previous = "runtime-version-lineage-genesis"
        for ordinal, event in enumerate(self._events):
            if event.ordinal != ordinal:
                failures.append("VERSION_LINEAGE_EVENT_ORDINAL_INVALID")
            if event.previous_event_digest != previous:
                failures.append("VERSION_LINEAGE_EVENT_CHAIN_INVALID")
            target = by_id.get(event.target_version_id)
            if (
                target is None
                or event.source_version_id != target.parent_version_id
                or event.transition_digest != target.transition_digest
            ):
                failures.append("VERSION_LINEAGE_EVENT_BINDING_INVALID")
            if event.target_version_id in event_targets:
                failures.append("VERSION_LINEAGE_EVENT_TARGET_REUSED")
            if event.operation not in {"ACTIVATE", "REJECT"}:
                failures.append("VERSION_LINEAGE_EVENT_OPERATION_INVALID")
            expected_event_digest = "runtime-version-event:" + digest_object(
                {
                    "ordinal": event.ordinal,
                    "operation": event.operation,
                    "source_version_id": event.source_version_id,
                    "target_version_id": event.target_version_id,
                    "transition_digest": event.transition_digest,
                    "previous_event_digest": event.previous_event_digest,
                }
            )
            if event.event_digest != expected_event_digest:
                failures.append("VERSION_LINEAGE_EVENT_DIGEST_INVALID")
            previous = event.event_digest
            event_targets.add(event.target_version_id)
        return tuple(sorted(set(failures)))

    def digest(self) -> str:
        failures = self.validate()
        if failures:
            raise RuntimeError(";".join(failures))
        return "version-lineage:" + digest_object(
            {
                "version": VERSION_LINEAGE_VERSION,
                "versions": self.versions,
                "events": self.events,
            }
        )


__all__ = [
    "P_MIGRATION_DISPOSITIONS",
    "VERSION_LINEAGE_VERSION",
    "CodeUpdateManifest",
    "MemorySchemaMigration",
    "RuntimeVersion",
    "VersionLineage",
    "VersionLineageEvent",
]
