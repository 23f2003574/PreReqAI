from .models import (
    ARTIFACT_STALE,
    IMPACT_RECONCILIATION_ALREADY_REPLACED,
    IMPACT_RECONCILIATION_FAILED_CLOSED,
    IMPACT_RECONCILIATION_NO_OP,
    IMPACT_RECONCILIATION_REPLACED,
    IMPACT_RECONCILIATION_RESULT_SCHEMA_VERSION,
    LIFECYCLE_VERIFICATION_INVALID,
    LIFECYCLE_VERIFICATION_VALID,
    RESOLUTION_RESOLVED,
    AgentTaskRecoveryExecutionDecisionImpactInvalidationReconciliationVerificationResult,
)


class InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationReconciliationVerificationError(ValueError):
    """Raised when verify() is given invalid arguments."""


class LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationReconciliationVerificationService:
    """Independently verifies a persisted lifecycle reconciliation (#12)
    against current decision and artifact state -- read-only, never
    rerunning remediation or repairing anything. It compares the
    reconciliation record with the lifecycle results it links (#9), the
    supersession resolution, current staleness (#1 impact + #2), and the
    lifecycle verification (#10) of whichever lifecycle result the
    reconciliation made authoritative.

    Checks: the previous lifecycle result still exists unchanged; the
    replacement reference is valid for the recorded state; the recorded
    newly-stale artifacts and unresolved blockers match current evidence;
    the recorded verification status agrees with #10 now; and the newest
    reconciliation is not presenting a superseded decision as current.
    Fails closed: evidence that cannot be established is missing_evidence
    and leaves authoritative_lifecycle_result_id None.
    """

    def __init__(
        self, reconciliation_result_service, lifecycle_result_service, lifecycle_verification_service,
        resolution_service, impact_service, staleness_service,
    ):
        """The existing #12, #9 and #10 services, the supersession
        resolution service, and #1/#2 -- all wired to the same stores."""
        self._reconciliations = reconciliation_result_service
        self._results = lifecycle_result_service
        self._lifecycle_verification = lifecycle_verification_service
        self._resolution = resolution_service
        self._impact = impact_service
        self._staleness = staleness_service

    def verify(
        self, task_id: str, reconciliation_result_id: str
    ) -> AgentTaskRecoveryExecutionDecisionImpactInvalidationReconciliationVerificationResult:
        """Verify task_id's persisted reconciliation reconciliation_result_id.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationReconciliationVerificationError:
                If task_id/reconciliation_result_id is not a non-empty string
        """
        for value, name in ((task_id, "task_id"), (reconciliation_result_id, "reconciliation_result_id")):
            if not value or not isinstance(value, str):
                raise InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationReconciliationVerificationError(
                    f"{name} is required and must be a non-empty string"
                )

        record = self._reconciliations.get(task_id, reconciliation_result_id)
        if record is None:
            return self._result(task_id, reconciliation_result_id, (), (
                f"reconciliation result {reconciliation_result_id} does not exist for task {task_id}",
            ), (), None)

        mismatches, missing = [], []
        if record.schema_version != IMPACT_RECONCILIATION_RESULT_SCHEMA_VERSION:
            mismatches.append(f"unsupported reconciliation schema version {record.schema_version!r}")

        previous = self._results.get(task_id, record.previous_result_id)
        if previous is None:
            missing.append(f"previous lifecycle result {record.previous_result_id} no longer exists")
        elif record.previous_status is not None and previous.status != record.previous_status:
            mismatches.append(
                f"previous lifecycle result {previous.result_id} changed status from {record.previous_status!r} "
                f"to {previous.status!r}; lifecycle history must be immutable"
            )

        resolution = self._resolution.resolve(task_id)
        current = resolution.terminal_decision_id if resolution.resolution_state == RESOLUTION_RESOLVED else None
        if current is None:
            missing.append(f"the authoritative decision cannot be established ({resolution.resolution_state})")
        latest = self._reconciliations.latest(task_id)
        if (
            current is not None and latest is not None and latest.result_id == record.result_id
            and record.current_decision_id != current
        ):
            mismatches.append(
                f"the newest reconciliation presents decision {record.current_decision_id} as current, but the "
                f"authoritative decision is now {current}"
            )

        authoritative = self._check_replacement(task_id, record, previous, mismatches, missing)

        if current is not None and current == record.current_decision_id and len(resolution.chain) >= 2:
            staleness = self._staleness.check(task_id, self._impact.analyze(task_id, resolution.chain[-2], current))
            stale_now = {f"{a.kind}:{a.reference}" for a in staleness.artifacts if a.status == ARTIFACT_STALE}
            replacement = (
                self._results.get(task_id, record.replacement_result_id) if record.replacement_result_id else None
            )
            remediated = {o.artifact_id for o in replacement.applied} if replacement is not None else set()
            for artifact_id in record.newly_stale_artifacts:
                if artifact_id not in stale_now and artifact_id not in remediated:
                    mismatches.append(
                        f"recorded newly stale artifact {artifact_id} is neither stale now nor remediated by the "
                        "replacement"
                    )

        blockers = ()
        if authoritative is not None:
            verification = self._lifecycle_verification.verify(task_id, authoritative)
            blockers = tuple(verification.remaining_blockers)
            missing.extend(f"authoritative lifecycle: {m}" for m in verification.missing_evidence)
            expected_blockers = set(blockers) | (
                set(verification.mismatches) if record.state == IMPACT_RECONCILIATION_REPLACED else set()
            )
            if set(record.unresolved_blockers) != expected_blockers:
                mismatches.append(
                    "recorded unresolved blockers do not match current evidence: recorded "
                    f"{sorted(record.unresolved_blockers)}, now {sorted(expected_blockers)}"
                )
            if record.verification_status is not None and record.verification_status != verification.status:
                mismatches.append(
                    f"recorded verification status {record.verification_status!r} disagrees with current evidence "
                    f"({verification.status!r})"
                )
        elif record.state != IMPACT_RECONCILIATION_FAILED_CLOSED:
            missing.append("the authoritative lifecycle result cannot be established")

        return self._result(task_id, reconciliation_result_id, mismatches, missing, blockers, authoritative)

    def _check_replacement(self, task_id, record, previous, mismatches, missing):
        if record.state == IMPACT_RECONCILIATION_NO_OP:
            if record.replacement_result_id is not None:
                mismatches.append("a no-op reconciliation references a replacement lifecycle result")
            if record.newly_stale_artifacts:
                mismatches.append("a no-op reconciliation records newly stale artifacts")
            return previous.result_id if previous is not None else None
        if record.state in (IMPACT_RECONCILIATION_REPLACED, IMPACT_RECONCILIATION_ALREADY_REPLACED):
            if record.replacement_result_id is None:
                mismatches.append(f"a {record.state} reconciliation names no replacement lifecycle result")
                return None
            replacement = self._results.get(task_id, record.replacement_result_id)
            if replacement is None:
                missing.append(f"replacement lifecycle result {record.replacement_result_id} does not exist")
                return None
            if replacement.result_id == record.previous_result_id:
                mismatches.append("the replacement lifecycle result is the previous result itself")
                return None
            if replacement.authoritative_decision_id != record.current_decision_id:
                mismatches.append(
                    f"replacement lifecycle result {replacement.result_id} is for decision "
                    f"{replacement.authoritative_decision_id}, not {record.current_decision_id}"
                )
            if record.replacement_operation_id != replacement.operation_id:
                mismatches.append("the recorded replacement operation id disagrees with the replacement result")
            history = [r.result_id for r in self._results.history(task_id)]
            if previous is not None and history.index(replacement.result_id) < history.index(previous.result_id):
                mismatches.append("the replacement lifecycle result predates the result it replaces")
            return replacement.result_id
        return None

    @staticmethod
    def _result(task_id, result_id, mismatches, missing, blockers, authoritative):
        status = LIFECYCLE_VERIFICATION_VALID if not mismatches and not missing else LIFECYCLE_VERIFICATION_INVALID
        return AgentTaskRecoveryExecutionDecisionImpactInvalidationReconciliationVerificationResult(
            task_id=task_id, reconciliation_result_id=result_id, status=status, mismatches=tuple(mismatches),
            missing_evidence=tuple(missing), remaining_blockers=tuple(blockers),
            authoritative_lifecycle_result_id=authoritative if status == LIFECYCLE_VERIFICATION_VALID else None,
        )
