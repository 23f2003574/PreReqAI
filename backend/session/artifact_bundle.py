from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4

from .execution_artifact_bundle_error import (
    ExecutionArtifactBundleError,
)


@dataclass(frozen=True)
class ArtifactBundle:
    """
    Immutable group of execution artifact versions meant to be
    consumed together, atomically, as a single unit.

    The bundle is a value object only. It performs no verification
    of its own; creating, verifying, listing, and removing bundles is
    the responsibility of an execution artifact bundle service.

    Attributes:
        bundle_id: The bundle's unique identifier
        session_id: The identifier of the execution session the
            bundle was created for
        version_ids: The versions grouped into this bundle, in the
            order they were given
        created_at: When this bundle was created
        status: The bundle's lifecycle stage, fixed at creation
    """

    session_id: str

    version_ids: tuple

    bundle_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    status: str = "CREATED"

    def __post_init__(self):
        self._require_text(self.bundle_id, "bundle ID")
        self._require_text(self.session_id, "session ID")
        self._require_text(self.status, "status")

        if self.version_ids is None:
            raise ExecutionArtifactBundleError("Cannot build an artifact bundle with None version_ids.")

        version_ids = tuple(self.version_ids)

        if not version_ids:
            raise ExecutionArtifactBundleError("Cannot build an artifact bundle with no versions.")

        for version_id in version_ids:
            self._require_text(version_id, "version ID")

        object.__setattr__(self, "version_ids", version_ids)

        if not isinstance(self.created_at, datetime):
            raise ExecutionArtifactBundleError(
                "Cannot build an artifact bundle with a non-datetime created_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactBundleError(
                f"Cannot build an artifact bundle with an empty or blank {field_name}."
            )
