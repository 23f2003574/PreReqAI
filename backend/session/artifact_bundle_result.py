from dataclasses import (
    dataclass,
)

from .execution_artifact_bundle_error import (
    ExecutionArtifactBundleError,
)


@dataclass(frozen=True)
class ArtifactBundleResult:
    """
    Immutable outcome of verifying whether every version in a bundle
    currently has a verified integrity checksum.

    Attributes:
        bundle_id: The identifier of the bundle that was verified
        complete: Whether every version in the bundle is verified
    """

    bundle_id: str

    complete: bool

    def __post_init__(self):
        if self.bundle_id is None or not self.bundle_id.strip():
            raise ExecutionArtifactBundleError(
                "Cannot build an artifact bundle result with an empty or blank bundle ID."
            )

        if not isinstance(self.complete, bool):
            raise ExecutionArtifactBundleError(
                "Cannot build an artifact bundle result with a non-boolean complete."
            )
