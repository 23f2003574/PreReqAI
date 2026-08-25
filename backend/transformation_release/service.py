from datetime import datetime, timezone

from backend.code_transformation import LLMCodeTransformationService
from backend.transformation_diff import LLMTransformationDiffService
from backend.transformation_execution import LLMTransformationExecutionService
from backend.transformation_gate import LLMTransformationGateService, UnknownGateEvaluationError

from .models import PREPARED, RELEASED, LLMTransformationRelease


class GatesNotEvaluatedError(ValueError):
    """Raised when prepare()/validate() is called for an execution whose release gates were never evaluated."""


class GatesNotPassedError(ValueError):
    """Raised when prepare()/validate() is called for an execution that hasn't passed every required gate."""


class ReleaseNotPreparedError(ValueError):
    """Raised when release() is called for a release_id that isn't currently PREPARED."""


class UnknownReleaseError(KeyError):
    """Raised when validate()/release()/status() is called for a release_id that was never prepared."""


class LLMTransformationReleaseService:
    """Prepares, then finalizes, an immutable release candidate for an
    execution that has passed every Commit #11 gate.

    Reuses LLMTransformationGateService.passed() as the sole readiness
    check: prepare() never creates a release for an execution whose gates
    were never evaluated or didn't all pass, and validate() re-runs the
    same check before release() may promote a candidate, so a regression
    discovered after prepare() (e.g. the gates are re-evaluated and now
    fail) blocks release() too. Every gate type Commit #11 always
    evaluates -- including VERIFICATION and REGRESSION -- must be PASSED,
    so "all gates pass" already entails both being clean; no separate
    check against those services is needed here. prepare()/validate()
    never mutate the gates, the execution, or notebook source, and
    release() never deploys anything -- it only flips this release's own
    status from PREPARED to RELEASED.
    """

    def __init__(
        self,
        gate_service: LLMTransformationGateService,
        execution_service: LLMTransformationExecutionService,
        diff_service: LLMTransformationDiffService,
        transformation_service: LLMCodeTransformationService,
    ):
        self._gate_service = gate_service
        self._execution_service = execution_service
        self._diff_service = diff_service
        self._transformation_service = transformation_service
        self._releases = {}
        self._version_counter_by_notebook = {}
        self._release_counter = 0

    def _notebook_id_for(self, execution) -> str:
        diff = self._diff_service.get(execution.diff_id)
        plan = self._transformation_service.get(diff.plan_id)
        return plan.notebook_id

    def _require_gates_passed(self, execution_id: str) -> None:
        try:
            passed = self._gate_service.passed(execution_id)
        except UnknownGateEvaluationError as exc:
            raise GatesNotEvaluatedError(
                f"execution {execution_id!r} has not had its release gates evaluated"
            ) from exc

        if not passed:
            raise GatesNotPassedError(f"execution {execution_id!r} has not passed every required gate")

    def prepare(self, execution_id: str) -> LLMTransformationRelease:
        self._require_gates_passed(execution_id)

        execution = self._execution_service.get(execution_id)
        notebook_id = self._notebook_id_for(execution)

        self._version_counter_by_notebook[notebook_id] = (
            self._version_counter_by_notebook.get(notebook_id, 0) + 1
        )
        version = f"{notebook_id}-v{self._version_counter_by_notebook[notebook_id]}"

        self._release_counter += 1
        release = LLMTransformationRelease(
            release_id=f"release-{execution_id}-{self._release_counter}",
            execution_id=execution_id,
            version=version,
            status=PREPARED,
            released_at=None,
        )
        self._releases[release.release_id] = release
        return release

    def _get(self, release_id: str) -> LLMTransformationRelease:
        try:
            return self._releases[release_id]
        except KeyError:
            raise UnknownReleaseError(release_id)

    def validate(self, release_id: str) -> bool:
        release = self._get(release_id)
        self._require_gates_passed(release.execution_id)
        return True

    def release(self, release_id: str) -> LLMTransformationRelease:
        current = self._get(release_id)
        if current.status != PREPARED:
            raise ReleaseNotPreparedError(
                f"release {release_id!r} is not currently PREPARED (status={current.status!r})"
            )

        self.validate(release_id)

        released = LLMTransformationRelease(
            release_id=current.release_id,
            execution_id=current.execution_id,
            version=current.version,
            status=RELEASED,
            released_at=datetime.now(timezone.utc),
        )
        self._releases[release_id] = released
        return released

    def status(self, release_id: str) -> str:
        return self._get(release_id).status
