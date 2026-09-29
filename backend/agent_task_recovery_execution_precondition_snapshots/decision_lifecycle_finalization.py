from types import SimpleNamespace

from .models import (
    FINALIZATION_CHECK_FAILED,
    FINALIZATION_CHECK_PASSED,
    FINALIZATION_CHECK_WARNING,
    IMPACT_LIFECYCLE_EXECUTION_FAILED,
    LIFECYCLE_VERIFICATION_VALID,
    RESOLUTION_RESOLVED,
    AgentTaskRecoveryExecutionDecisionLifecycleFinalizationCheck,
    AgentTaskRecoveryExecutionDecisionLifecycleFinalizationResult,
)

# facade attribute -> (constructor keyword, the one method the facade calls on it)
_FACADE_DEPENDENCIES = {
    "_resolution": ("resolution_service", "resolve"),
    "_impact": ("impact_service", "analyze"),
    "_staleness": ("staleness_service", "check"),
    "_planner": ("plan_service", "plan"),
    "_validation": ("plan_validation_service", "validate"),
    "_execution": ("execution_service", "execute"),
    "_audit": ("audit_service", "record"),
    "_verification": ("verification_service", "verify"),
}
_BLOCKING_LIFECYCLE_STATUSES = frozenset({"blocked", "unsafe", "unresolved", "validation_failed", "execution_failed"})


class InvalidAgentTaskRecoveryExecutionDecisionLifecycleFinalizationError(ValueError):
    """Raised when finalize() is given a non-string, non-None or blank task_id."""


class LLMAgentTaskRecoveryExecutionDecisionLifecycleFinalizationService:
    """A read-only release gate over the impact-invalidation lifecycle. It
    composes what already exists -- the lifecycle facade's own wiring, the
    supersession resolution service, the persisted-result service and the
    lifecycle verification service -- and never runs recovery, remediation or
    the real lifecycle. The timeout-safety check drives a throwaway facade
    built only from failing doubles, so nothing real is touched.

    Every check always runs, in a fixed order, so the result is deterministic
    for CI. ready is True only when no check failed; warnings (a check that
    cannot be evaluated, e.g. no task_id given) never block."""

    def __init__(
        self, lifecycle_service, resolution_service, lifecycle_result_service=None,
        lifecycle_verification_service=None, expected_surfaces=None,
    ):
        """expected_surfaces: {name: callable-or-None} for the CLI/API entry
        points a release expects; a missing one is a blocker. None/empty
        means no surface is registered (reported as a warning: this package
        has no CLI or HTTP surface of its own)."""
        self._facade = lifecycle_service
        self._resolution = resolution_service
        self._results = lifecycle_result_service
        self._verification = lifecycle_verification_service
        self._surfaces = dict(expected_surfaces or {})

    def finalize(self, task_id=None) -> AgentTaskRecoveryExecutionDecisionLifecycleFinalizationResult:
        """Raises:
            InvalidAgentTaskRecoveryExecutionDecisionLifecycleFinalizationError:
                If task_id is given but is not a non-empty string
        """
        if task_id is not None and (not isinstance(task_id, str) or not task_id):
            raise InvalidAgentTaskRecoveryExecutionDecisionLifecycleFinalizationError(
                "task_id must be a non-empty string when given"
            )
        checks = (
            self._configuration(), self._dependencies(), self._wiring(), self._lineage(task_id),
            self._critical_blockers(task_id), self._persisted_results(task_id), self._timeout_safety(),
            self._surface_availability(),
        )
        blocking = tuple(f"{c.name}: {c.detail}" for c in checks if c.status == FINALIZATION_CHECK_FAILED)
        warnings = tuple(f"{c.name}: {c.detail}" for c in checks if c.status == FINALIZATION_CHECK_WARNING)
        return AgentTaskRecoveryExecutionDecisionLifecycleFinalizationResult(
            task_id=task_id, ready=not blocking, checks=checks, blocking_issues=blocking, warnings=warnings,
        )

    @staticmethod
    def _check(name, ok, detail_if_failed="", status_if_not_ok=FINALIZATION_CHECK_FAILED):
        return AgentTaskRecoveryExecutionDecisionLifecycleFinalizationCheck(
            name=name, status=FINALIZATION_CHECK_PASSED if ok else status_if_not_ok,
            detail="" if ok else detail_if_failed,
        )

    def _configuration(self):
        missing = [kw for attr, (kw, _) in _FACADE_DEPENDENCIES.items() if getattr(self._facade, attr, None) is None]
        if self._resolution is None:
            missing.append("resolution_service (finalization)")
        return self._check("configuration", not missing, "missing required dependencies: " + ", ".join(missing))

    def _dependencies(self):
        broken = [
            f"{kw}.{method}" for attr, (kw, method) in _FACADE_DEPENDENCIES.items()
            if not callable(getattr(getattr(self._facade, attr, None), method, None))
        ]
        return self._check("dependencies", not broken, "dependencies do not resolve: " + ", ".join(broken))

    def _wiring(self):
        same = getattr(self._facade, "_resolution", None) is self._resolution
        return self._check(
            "wiring", same, "the facade and the finalization service use different resolution services"
        )

    def _lineage(self, task_id):
        if task_id is None:
            return self._check("decision_lineage", False, "no task_id given; lineage not evaluated",
                               FINALIZATION_CHECK_WARNING)
        try:
            state = self._resolution.resolve(task_id).resolution_state
        except Exception as error:
            return self._check("decision_lineage", False, f"resolution failed: {type(error).__name__}: {error}")
        return self._check("decision_lineage", state == RESOLUTION_RESOLVED, f"lineage is {state}")

    def _critical_blockers(self, task_id):
        latest = self._latest(task_id)
        if latest is None:
            return self._check("critical_blockers", False, "no persisted lifecycle result to inspect",
                               FINALIZATION_CHECK_WARNING)
        bad = latest.status in _BLOCKING_LIFECYCLE_STATUSES
        return self._check(
            "critical_blockers", not bad,
            f"latest lifecycle result {latest.result_id} is {latest.status} with blocking "
            f"artifacts {sorted(latest.blocking_artifacts)}",
        )

    def _persisted_results(self, task_id):
        if task_id is None or self._results is None or self._verification is None:
            return self._check("persisted_results", False, "results or verification service not available",
                               FINALIZATION_CHECK_WARNING)
        invalid = []
        for record in self._results.history(task_id):
            try:
                verdict = self._verification.verify(task_id, record.result_id)
            except Exception as error:
                invalid.append(f"{record.result_id} ({type(error).__name__}: {error})")
                continue
            if verdict.status != LIFECYCLE_VERIFICATION_VALID:
                invalid.append(f"{record.result_id} ({verdict.status})")
        return self._check("persisted_results", not invalid, "unverifiable results: " + ", ".join(invalid))

    def _timeout_safety(self):
        """A throwaway facade whose resolution times out and whose every other
        collaborator records a call: the timeout must yield a non-success
        result and no downstream stage may run."""
        called = []

        def timeout(*args):
            raise TimeoutError("probe")

        def recorder(name):
            return lambda *args: called.append(name)

        doubles = {kw: SimpleNamespace(**{method: recorder(kw)}) for kw, method in
                   (v for v in _FACADE_DEPENDENCIES.values())}
        doubles["resolution_service"] = SimpleNamespace(resolve=timeout)
        try:
            result = type(self._facade)(**doubles).run("finalization-probe")
        except BaseException as error:  # the boundary must not leak even this
            return self._check("timeout_safety", False, f"timeout leaked out of the facade: {type(error).__name__}")
        ok = result.status == IMPACT_LIFECYCLE_EXECUTION_FAILED and not called
        return self._check("timeout_safety", ok, f"timeout produced {result.status!r} and downstream calls {called}")

    def _surface_availability(self):
        if not self._surfaces:
            return self._check("surfaces", False, "no CLI/API surface registered for this lifecycle",
                               FINALIZATION_CHECK_WARNING)
        missing = sorted(name for name, target in self._surfaces.items() if not callable(target))
        return self._check("surfaces", not missing, "missing surfaces: " + ", ".join(missing))

    def _latest(self, task_id):
        if task_id is None or self._results is None:
            return None
        return self._results.latest(task_id)
