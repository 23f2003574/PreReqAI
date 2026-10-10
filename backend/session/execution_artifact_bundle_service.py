from threading import (
    RLock,
)

from .artifact_bundle import (
    ArtifactBundle,
)

from .artifact_bundle_result import (
    ArtifactBundleResult,
)

from .execution_artifact_bundle_error import (
    ExecutionArtifactBundleError,
)


class ExecutionArtifactBundleService:
    """
    Groups execution artifact versions into immutable bundles for
    atomic consumption, using an existing version resolver and
    execution artifact integrity service as the sources of truth for
    what versions exist and whether they are verified.

    The service's responsibility is bundle bookkeeping only. It does
    not verify checksums or resolve version identities itself; it
    relies on the dependencies given at construction time only to
    confirm a version ID is genuinely known, and to check whether it
    currently has a verified checksum.

    Behavior:
    - A bundle must group at least one version; an empty bundle is
      rejected
    - Every version in a bundle must be known at creation time
    - A bundle, once created, is immutable: its versions never change
    - verify() is read-only: it reports whether every version in a
      bundle is currently verified, without recording anything on
      the bundle itself

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, version_resolver, execution_artifact_integrity_service):
        """
        Args:
            version_resolver: The resolver used to confirm a version
                ID is known before it may be grouped into a bundle.
                Any object exposing `resolve(version_id)`, raising if
                the version is unknown, is accepted
            execution_artifact_integrity_service: The service used to
                check whether a version currently has a verified
                checksum. Any object exposing `status(version_id)`,
                raising if the version has no recorded checksum, is
                accepted
        """

        self._version_resolver = version_resolver
        self._execution_artifact_integrity_service = execution_artifact_integrity_service
        self._bundles_by_id = {}
        self._bundle_ids_by_session = {}
        self._lock = RLock()

    def create(self, session_id: str, version_ids) -> ArtifactBundle:
        """
        Create an immutable bundle grouping the given versions.

        Raises:
            ExecutionArtifactBundleError: If session_id is None or
                blank, version_ids is None or empty, or the version
                resolver does not recognize one of version_ids
        """

        self._validate_id(session_id, "session ID")

        if version_ids is None:
            raise ExecutionArtifactBundleError("Cannot create a bundle with None version_ids.")

        version_ids = tuple(version_ids)

        if not version_ids:
            raise ExecutionArtifactBundleError("Cannot create a bundle with no versions.")

        with self._lock:
            for version_id in version_ids:
                self._ensure_version_known(version_id)

            bundle = ArtifactBundle(session_id=session_id, version_ids=version_ids)

            self._bundles_by_id[bundle.bundle_id] = bundle
            self._bundle_ids_by_session.setdefault(session_id, []).append(bundle.bundle_id)

            return bundle

    def get(self, bundle_id: str) -> ArtifactBundle:
        """
        Look up a bundle.

        Raises:
            ExecutionArtifactBundleError: If bundle_id is None or
                blank, or no bundle is registered under it
        """

        self._validate_id(bundle_id, "bundle ID")

        with self._lock:
            return self._resolve(bundle_id)

    def verify(self, bundle_id: str) -> ArtifactBundleResult:
        """
        Check whether every version in a bundle currently has a
        verified checksum. Read-only: never mutates the bundle.

        Raises:
            ExecutionArtifactBundleError: If bundle_id is None or
                blank, or no bundle is registered under it
        """

        self._validate_id(bundle_id, "bundle ID")

        with self._lock:
            bundle = self._resolve(bundle_id)

            complete = all(self._is_verified(version_id) for version_id in bundle.version_ids)

            return ArtifactBundleResult(bundle_id=bundle_id, complete=complete)

    def list(self, session_id: str) -> list:
        """
        List every bundle created for a session, in the order they
        were created.

        Raises:
            ExecutionArtifactBundleError: If session_id is None or
                blank
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            return [
                self._bundles_by_id[bundle_id]
                for bundle_id in self._bundle_ids_by_session.get(session_id, [])
            ]

    def delete(self, bundle_id: str) -> ArtifactBundle:
        """
        Remove a bundle. The versions it grouped are left untouched.

        Raises:
            ExecutionArtifactBundleError: If bundle_id is None or
                blank, or no bundle is registered under it
        """

        self._validate_id(bundle_id, "bundle ID")

        with self._lock:
            bundle = self._resolve(bundle_id)

            del self._bundles_by_id[bundle_id]
            self._bundle_ids_by_session[bundle.session_id].remove(bundle_id)

            return bundle

    def _is_verified(self, version_id: str) -> bool:
        try:
            self._execution_artifact_integrity_service.status(version_id)
            return True
        except Exception:
            return False

    def _resolve(self, bundle_id: str) -> ArtifactBundle:
        bundle = self._bundles_by_id.get(bundle_id)

        if bundle is None:
            raise ExecutionArtifactBundleError(f"No bundle is known under bundle ID {bundle_id!r}.")

        return bundle

    def _ensure_version_known(self, version_id: str) -> None:
        try:
            self._version_resolver.resolve(version_id)
        except Exception as error:
            raise ExecutionArtifactBundleError(f"No version is known under version ID {version_id!r}.") from error

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactBundleError(f"Cannot use an empty or blank {field_name}.")
