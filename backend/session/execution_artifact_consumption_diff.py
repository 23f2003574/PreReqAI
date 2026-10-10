from dataclasses import (
    dataclass,
)

from types import (
    MappingProxyType,
)

from .execution_artifact_consumption_reconciliation_error import (
    ExecutionArtifactConsumptionReconciliationError,
)


@dataclass(frozen=True)
class ExecutionArtifactConsumptionDiff:
    """
    Immutable result of comparing a consumption session's currently
    tracked artifacts against a recorded snapshot.

    The diff is a value object only. It performs no comparison or
    reconciliation of its own; computing, applying, and looking up
    diffs is the responsibility of an execution artifact consumption
    reconciliation service.

    Attributes:
        consumption_id: The identifier of the compared consumption
            session
        added: The artifacts currently tracked that the snapshot did
            not record, in the order the session currently tracks
            them
        removed: The artifacts the snapshot recorded that are no
            longer tracked, in the order the snapshot recorded them
        changed: The artifacts tracked both now and by the snapshot
            whose current version differs from the snapshot's, keyed
            by artifact ID to a (snapshot_version, current_version)
            pair
    """

    consumption_id: str

    added: tuple

    removed: tuple

    changed: dict

    def __post_init__(self):
        self._require_text(self.consumption_id, "consumption ID")

        added = self._normalize_ids(self.added, "added")
        removed = self._normalize_ids(self.removed, "removed")
        changed = self._normalize_changed(self.changed)

        overlap = (set(added) & set(removed)) | (set(added) & changed.keys()) | (set(removed) & changed.keys())

        if overlap:
            raise ExecutionArtifactConsumptionReconciliationError(
                f"Cannot build an execution artifact consumption diff with artifact IDs "
                f"{sorted(overlap)!r} appearing in more than one of added, removed, or changed."
            )

        object.__setattr__(self, "added", added)
        object.__setattr__(self, "removed", removed)
        object.__setattr__(self, "changed", MappingProxyType(changed))

    def _normalize_ids(self, value, field_name: str) -> tuple:
        if value is None:
            raise ExecutionArtifactConsumptionReconciliationError(
                f"Cannot build an execution artifact consumption diff with a None {field_name}."
            )

        ids = list(value)

        if not all(isinstance(artifact_id, str) and artifact_id.strip() for artifact_id in ids):
            raise ExecutionArtifactConsumptionReconciliationError(
                f"Cannot build an execution artifact consumption diff with a blank or non-string artifact "
                f"ID in {field_name}."
            )

        normalized = tuple(ids)

        if len(set(normalized)) != len(normalized):
            raise ExecutionArtifactConsumptionReconciliationError(
                f"Cannot build an execution artifact consumption diff with duplicate artifact IDs in "
                f"{field_name}."
            )

        return normalized

    def _normalize_changed(self, value) -> dict:
        if not isinstance(value, dict):
            raise ExecutionArtifactConsumptionReconciliationError(
                "Cannot build an execution artifact consumption diff with a non-dict changed."
            )

        normalized = {}

        for artifact_id, versions in value.items():
            if not isinstance(artifact_id, str) or not artifact_id.strip():
                raise ExecutionArtifactConsumptionReconciliationError(
                    "Cannot build an execution artifact consumption diff with a blank or non-string "
                    "artifact ID in changed."
                )

            versions_tuple = tuple(versions)

            if len(versions_tuple) != 2 or not all(
                isinstance(version, int) and not isinstance(version, bool) and version >= 1
                for version in versions_tuple
            ):
                raise ExecutionArtifactConsumptionReconciliationError(
                    f"Cannot build an execution artifact consumption diff with an invalid changed entry "
                    f"for artifact ID {artifact_id!r}: expected a (snapshot_version, current_version) pair "
                    f"of positive integers."
                )

            if versions_tuple[0] == versions_tuple[1]:
                raise ExecutionArtifactConsumptionReconciliationError(
                    f"Cannot build an execution artifact consumption diff with a changed entry for "
                    f"artifact ID {artifact_id!r} whose snapshot_version and current_version are equal."
                )

            normalized[artifact_id] = versions_tuple

        return normalized

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionArtifactConsumptionReconciliationError(
                f"Cannot build an execution artifact consumption diff with an empty or blank {field_name}."
            )
