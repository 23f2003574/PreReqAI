from threading import (
    RLock,
)

from .artifact_dependency import (
    ArtifactDependency,
)

from .artifact_dependency_result import (
    ArtifactDependencyResult,
)

from .execution_artifact_dependency_error import (
    ExecutionArtifactDependencyError,
)


class ExecutionArtifactDependencyService:
    """
    Tracks which execution artifacts require other execution
    artifacts as inputs, optionally pinned to an exact version, using
    an existing execution artifact registry and version service as
    the sources of truth for what exists.

    The service's responsibility is dependency bookkeeping only. It
    does not build or produce artifacts itself; validate() only
    reports whether a required artifact currently has an available
    version, leaving a caller to act on that.

    Behavior:
    - An artifact cannot depend on itself
    - add() rejects an edge that would close a cycle in the
      dependency graph
    - validate() reports unsatisfied if a required artifact has no
      version yet, or, when required_version is pinned, no version
      exactly matching it

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_artifact_service, execution_artifact_version_service):
        """
        Args:
            execution_artifact_service: The registry used to confirm
                an artifact ID is known before a dependency is added
                for, or against, it. Any object exposing
                `get(artifact_id)`, raising if the artifact is
                unknown, is accepted
            execution_artifact_version_service: The service used to
                confirm a required artifact currently has an
                available (optionally exact) version. Any object
                exposing `latest(artifact_id)` and
                `get(artifact_id, version)`, each raising if unknown,
                is accepted
        """

        self._execution_artifact_service = execution_artifact_service
        self._execution_artifact_version_service = execution_artifact_version_service
        self._dependencies_by_id = {}
        self._dependency_ids_by_artifact = {}
        self._dependent_ids_by_required_artifact = {}
        self._lock = RLock()

    def add(self, artifact_id: str, required_artifact_id: str, version: int | None = None) -> ArtifactDependency:
        """
        Declare that artifact_id requires required_artifact_id,
        optionally pinned to an exact version.

        Raises:
            ExecutionArtifactDependencyError: If artifact_id or
                required_artifact_id is None or blank, they are
                equal, either is unknown to the execution artifact
                registry, or the new edge would close a dependency
                cycle
        """

        self._validate_id(artifact_id, "artifact ID")
        self._validate_id(required_artifact_id, "required artifact ID")

        if artifact_id == required_artifact_id:
            raise ExecutionArtifactDependencyError(
                f"Artifact ID {artifact_id!r} cannot depend on itself."
            )

        with self._lock:
            self._ensure_artifact_known(artifact_id)
            self._ensure_artifact_known(required_artifact_id)

            if self._reaches(required_artifact_id, artifact_id):
                raise ExecutionArtifactDependencyError(
                    f"Cannot add dependency: artifact ID {required_artifact_id!r} already depends "
                    f"(directly or transitively) on artifact ID {artifact_id!r}."
                )

            dependency = ArtifactDependency(
                artifact_id=artifact_id,
                required_artifact_id=required_artifact_id,
                required_version=version,
            )

            self._dependencies_by_id[dependency.dependency_id] = dependency
            self._dependency_ids_by_artifact.setdefault(artifact_id, []).append(dependency.dependency_id)
            self._dependent_ids_by_required_artifact.setdefault(required_artifact_id, []).append(artifact_id)

            return dependency

    def remove(self, dependency_id: str) -> ArtifactDependency:
        """
        Remove a declared dependency.

        Raises:
            ExecutionArtifactDependencyError: If dependency_id is None
                or blank, or no dependency is registered under it
        """

        self._validate_id(dependency_id, "dependency ID")

        with self._lock:
            dependency = self._dependencies_by_id.get(dependency_id)

            if dependency is None:
                raise ExecutionArtifactDependencyError(
                    f"No dependency is known under dependency ID {dependency_id!r}."
                )

            del self._dependencies_by_id[dependency_id]
            self._dependency_ids_by_artifact[dependency.artifact_id].remove(dependency_id)
            self._dependent_ids_by_required_artifact[dependency.required_artifact_id].remove(
                dependency.artifact_id
            )

            return dependency

    def validate(self, artifact_id: str) -> ArtifactDependencyResult:
        """
        Check whether every dependency declared for an artifact is
        currently satisfied.

        Raises:
            ExecutionArtifactDependencyError: If artifact_id is None
                or blank, or the execution artifact registry does not
                recognize artifact_id
        """

        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            self._ensure_artifact_known(artifact_id)

            dependency_ids = self._dependency_ids_by_artifact.get(artifact_id, [])

            if not dependency_ids:
                return ArtifactDependencyResult(
                    satisfied=True,
                    reason=f"Artifact ID {artifact_id!r} has no declared dependencies.",
                )

            for dependency_id in dependency_ids:
                dependency = self._dependencies_by_id[dependency_id]

                if dependency.required_version is not None:
                    try:
                        self._execution_artifact_version_service.get(
                            dependency.required_artifact_id, dependency.required_version
                        )
                    except Exception:
                        return ArtifactDependencyResult(
                            satisfied=False,
                            reason=(
                                f"Required artifact ID {dependency.required_artifact_id!r} has no "
                                f"version {dependency.required_version} available."
                            ),
                        )
                else:
                    try:
                        self._execution_artifact_version_service.latest(dependency.required_artifact_id)
                    except Exception:
                        return ArtifactDependencyResult(
                            satisfied=False,
                            reason=(
                                f"Required artifact ID {dependency.required_artifact_id!r} has no "
                                "version available yet."
                            ),
                        )

            return ArtifactDependencyResult(
                satisfied=True,
                reason=f"All {len(dependency_ids)} dependencies of artifact ID {artifact_id!r} are satisfied.",
            )

    def dependents(self, artifact_id: str) -> list:
        """
        List every artifact that currently declares a dependency on
        artifact_id, in the order those dependencies were added.

        Raises:
            ExecutionArtifactDependencyError: If artifact_id is None
                or blank, or the execution artifact registry does not
                recognize artifact_id
        """

        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            self._ensure_artifact_known(artifact_id)

            return list(self._dependent_ids_by_required_artifact.get(artifact_id, []))

    def _reaches(self, start: str, target: str) -> bool:
        visited = set()
        stack = [start]

        while stack:
            current = stack.pop()

            if current == target:
                return True

            if current in visited:
                continue

            visited.add(current)

            for dependency_id in self._dependency_ids_by_artifact.get(current, []):
                stack.append(self._dependencies_by_id[dependency_id].required_artifact_id)

        return False

    def _ensure_artifact_known(self, artifact_id: str) -> None:
        try:
            self._execution_artifact_service.get(artifact_id)
        except Exception as error:
            raise ExecutionArtifactDependencyError(
                f"No artifact is known under artifact ID {artifact_id!r}."
            ) from error

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactDependencyError(f"Cannot use an empty or blank {field_name}.")
