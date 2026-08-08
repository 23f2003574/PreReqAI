import hashlib

from threading import (
    RLock,
)

from .artifact_bundle_manifest import (
    ArtifactBundleManifest,
)

from .artifact_bundle_manifest_entry import (
    ArtifactBundleManifestEntry,
)

from .execution_artifact_bundle_manifest_error import (
    ExecutionArtifactBundleManifestError,
)


class ExecutionArtifactBundleManifestService:
    """
    Generates deterministic manifests describing exactly which
    artifact versions belong to a bundle, using an existing execution
    artifact bundle service, execution artifact integrity service,
    and version resolver as the sources of truth for a bundle's
    versions, their checksums, and their owning artifacts.

    The service's responsibility is manifest bookkeeping only. It
    does not compute checksums or store bundle contents itself.

    Behavior:
    - A manifest's entries follow the bundle's own version order
    - generate() rejects a bundle with a version that has no recorded
      integrity checksum
    - Two manifests built from the same entries in the same order
      always have the same fingerprint
    - verify() is read-only: it recomputes the bundle's current
      manifest and compares its fingerprint to the last generated
      one, without recording anything

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_artifact_bundle_service, execution_artifact_integrity_service, version_resolver):
        """
        Args:
            execution_artifact_bundle_service: The service used to
                look up a bundle's ordered version IDs. Any object
                exposing `get(bundle_id)`, raising if the bundle is
                unknown, is accepted
            execution_artifact_integrity_service: The service used to
                look up a version's recorded checksum. Any object
                exposing `status(version_id)` (returning an object
                with a `.checksum`), raising if the version has no
                recorded checksum, is accepted
            version_resolver: The resolver used to identify the
                artifact a version belongs to. Any object exposing
                `resolve(version_id)` (returning an object with an
                `.artifact_id`), raising if the version is unknown,
                is accepted
        """

        self._execution_artifact_bundle_service = execution_artifact_bundle_service
        self._execution_artifact_integrity_service = execution_artifact_integrity_service
        self._version_resolver = version_resolver
        self._manifests_by_bundle = {}
        self._lock = RLock()

    def generate(self, bundle_id: str) -> ArtifactBundleManifest:
        """
        Generate and store a fresh manifest for a bundle, from its
        current version set and their current checksums.

        Raises:
            ExecutionArtifactBundleManifestError: If bundle_id is
                None or blank, the execution artifact bundle service
                does not recognize bundle_id, or a version in the
                bundle has no recorded integrity checksum
        """

        self._validate_id(bundle_id, "bundle ID")

        with self._lock:
            manifest = self._build_manifest(bundle_id)
            self._manifests_by_bundle[bundle_id] = manifest

            return manifest

    def get(self, bundle_id: str) -> ArtifactBundleManifest:
        """
        Look up a bundle's most recently generated manifest.

        Raises:
            ExecutionArtifactBundleManifestError: If bundle_id is
                None or blank, or no manifest has been generated for
                it yet
        """

        self._validate_id(bundle_id, "bundle ID")

        with self._lock:
            return self._resolve(bundle_id)

    def verify(self, bundle_id: str) -> bool:
        """
        Check whether a bundle's current version set and checksums
        still match its last generated manifest. Read-only: never
        mutates the stored manifest.

        Raises:
            ExecutionArtifactBundleManifestError: If bundle_id is
                None or blank, no manifest has been generated for it
                yet, or a currently-grouped version has no recorded
                integrity checksum
        """

        self._validate_id(bundle_id, "bundle ID")

        with self._lock:
            stored = self._resolve(bundle_id)
            current = self._build_manifest(bundle_id)

            return current.fingerprint == stored.fingerprint

    def diff(self, bundle_id: str, expected: ArtifactBundleManifest) -> dict:
        """
        Compare a bundle's last generated manifest against an
        expected manifest.

        Returns:
            A dict with "added", "removed", and "changed" lists of
            ArtifactBundleManifestEntry: entries present now but not
            in expected, entries in expected but not present now, and
            entries present in both under the same version ID but
            with a different checksum

        Raises:
            ExecutionArtifactBundleManifestError: If bundle_id is
                None or blank, expected is not an
                ArtifactBundleManifest, or no manifest has been
                generated for bundle_id yet
        """

        self._validate_id(bundle_id, "bundle ID")

        if not isinstance(expected, ArtifactBundleManifest):
            raise ExecutionArtifactBundleManifestError(
                "Cannot diff against an invalid expected manifest: expected must be an ArtifactBundleManifest."
            )

        with self._lock:
            current = self._resolve(bundle_id)

            current_by_version = {entry.version_id: entry for entry in current.entries}
            expected_by_version = {entry.version_id: entry for entry in expected.entries}

            added = [
                entry for version_id, entry in current_by_version.items() if version_id not in expected_by_version
            ]
            removed = [
                entry for version_id, entry in expected_by_version.items() if version_id not in current_by_version
            ]
            changed = [
                current_by_version[version_id]
                for version_id in current_by_version
                if version_id in expected_by_version
                and current_by_version[version_id].checksum != expected_by_version[version_id].checksum
            ]

            return {"added": added, "removed": removed, "changed": changed}

    def _build_manifest(self, bundle_id: str) -> ArtifactBundleManifest:
        bundle = self._get_bundle(bundle_id)

        entries = tuple(self._build_entry(version_id) for version_id in bundle.version_ids)

        return ArtifactBundleManifest(
            bundle_id=bundle_id,
            entries=entries,
            fingerprint=self._compute_fingerprint(entries),
        )

    def _build_entry(self, version_id: str) -> ArtifactBundleManifestEntry:
        try:
            version = self._version_resolver.resolve(version_id)
        except Exception as error:
            raise ExecutionArtifactBundleManifestError(
                f"No version is known under version ID {version_id!r}."
            ) from error

        try:
            checksum = self._execution_artifact_integrity_service.status(version_id).checksum
        except Exception as error:
            raise ExecutionArtifactBundleManifestError(
                f"Version ID {version_id!r} has no recorded integrity checksum."
            ) from error

        return ArtifactBundleManifestEntry(
            artifact_id=version.artifact_id,
            version_id=version_id,
            checksum=checksum,
        )

    @staticmethod
    def _compute_fingerprint(entries) -> str:
        canonical = "|".join(f"{entry.artifact_id}:{entry.version_id}:{entry.checksum}" for entry in entries)

        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _get_bundle(self, bundle_id: str):
        try:
            return self._execution_artifact_bundle_service.get(bundle_id)
        except Exception as error:
            raise ExecutionArtifactBundleManifestError(
                f"No bundle is known under bundle ID {bundle_id!r}."
            ) from error

    def _resolve(self, bundle_id: str) -> ArtifactBundleManifest:
        manifest = self._manifests_by_bundle.get(bundle_id)

        if manifest is None:
            raise ExecutionArtifactBundleManifestError(f"No manifest has been generated for bundle ID {bundle_id!r}.")

        return manifest

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactBundleManifestError(f"Cannot use an empty or blank {field_name}.")
