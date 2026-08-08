from threading import (
    RLock,
)

from .artifact_lineage import (
    ArtifactLineage,
)

from .execution_artifact_lineage_error import (
    ExecutionArtifactLineageError,
)


class ExecutionArtifactLineageService:
    """
    Records how execution artifact versions were produced from other
    versions and execution sessions, using an existing version
    resolver as the source of truth for what versions exist.

    The service's responsibility is lineage bookkeeping only. It does
    not produce artifacts or resolve version identities itself; it
    relies on the version resolver, given at construction time, only
    to confirm a version ID is genuinely known before it is recorded
    as an output or input.

    Behavior:
    - A version cannot be recorded as its own input
    - record() rejects an output or input version ID the resolver
      does not recognize
    - Every lineage record, once created, is immutable and permanent

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, version_resolver):
        """
        Args:
            version_resolver: The resolver used to confirm a version
                ID is known before it is recorded as an output or
                input. Any object exposing `resolve(version_id)`,
                raising if the version is unknown, is accepted
        """

        self._version_resolver = version_resolver
        self._lineage_by_output = {}
        self._output_ids_by_input = {}
        self._lock = RLock()

    def record(self, output_version_id: str, input_version_ids, session_id: str) -> ArtifactLineage:
        """
        Record how output_version_id was produced.

        Raises:
            ExecutionArtifactLineageError: If output_version_id or
                session_id is None or blank, input_version_ids is
                None, output_version_id appears in input_version_ids,
                or the version resolver does not recognize
                output_version_id or any of input_version_ids
        """

        self._validate_id(output_version_id, "output version ID")
        self._validate_id(session_id, "session ID")

        if input_version_ids is None:
            raise ExecutionArtifactLineageError("Cannot record lineage with None input_version_ids.")

        input_version_ids = tuple(input_version_ids)

        if output_version_id in input_version_ids:
            raise ExecutionArtifactLineageError(
                f"Version ID {output_version_id!r} cannot be listed as its own input."
            )

        with self._lock:
            self._ensure_version_known(output_version_id)

            for input_version_id in input_version_ids:
                self._ensure_version_known(input_version_id)

            lineage = ArtifactLineage(
                output_version_id=output_version_id,
                input_version_ids=input_version_ids,
                session_id=session_id,
            )

            self._lineage_by_output[output_version_id] = lineage

            for input_version_id in input_version_ids:
                self._output_ids_by_input.setdefault(input_version_id, []).append(output_version_id)

            return lineage

    def lineage(self, version_id: str) -> ArtifactLineage:
        """
        Look up the lineage record describing how a version was
        produced.

        Raises:
            ExecutionArtifactLineageError: If version_id is None or
                blank, or no lineage has been recorded for it
        """

        self._validate_id(version_id, "version ID")

        with self._lock:
            return self._resolve_lineage(version_id)

    def inputs(self, version_id: str) -> tuple:
        """
        List the versions a version was produced from.

        Raises:
            ExecutionArtifactLineageError: If version_id is None or
                blank, or no lineage has been recorded for it
        """

        self._validate_id(version_id, "version ID")

        with self._lock:
            return self._resolve_lineage(version_id).input_version_ids

    def outputs(self, version_id: str) -> list:
        """
        List every version recorded as having been produced using
        version_id as an input, in the order those records were
        made.

        Raises:
            ExecutionArtifactLineageError: If version_id is None or
                blank, or the version resolver does not recognize it
        """

        self._validate_id(version_id, "version ID")

        with self._lock:
            self._ensure_version_known(version_id)

            return list(self._output_ids_by_input.get(version_id, []))

    def _resolve_lineage(self, version_id: str) -> ArtifactLineage:
        lineage = self._lineage_by_output.get(version_id)

        if lineage is None:
            raise ExecutionArtifactLineageError(f"No lineage is recorded for version ID {version_id!r}.")

        return lineage

    def _ensure_version_known(self, version_id: str) -> None:
        try:
            self._version_resolver.resolve(version_id)
        except Exception as error:
            raise ExecutionArtifactLineageError(f"No version is known under version ID {version_id!r}.") from error

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactLineageError(f"Cannot use an empty or blank {field_name}.")
