from .models import (
    IMPACT_LIFECYCLE_REMEDIATED,
    IMPACT_LIFECYCLE_RESULT_SCHEMA_VERSION,
    LIFECYCLE_VERIFICATION_INVALID,
    LIFECYCLE_VERIFICATION_VALID,
    RESOLUTION_RESOLVED,
    AgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleVerificationResult,
)


class InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleVerificationError(ValueError):
    """Raised when verify() is given invalid arguments."""


class LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleVerificationService:
    """Independently verifies a persisted impact-invalidation lifecycle
    result (#9) against current decision and artifact state -- read-only,
    never rerunning or repairing remediation. It compares the persisted
    record with:

      * the supersession resolution (is its authoritative decision still
        the authoritative one?);
      * the operation's audit record (#6) -- it must exist, match the
        record's audit reference, and agree on applied/skipped/failed
        artifacts and the affected set;
      * the post-remediation verification (#7) re-run now -- which checks
        refreshed artifacts reference the current decision, invalidated/
        cancelled ones are no longer executable, skipped/failed ones are
        still unresolved, and nothing unrelated changed.

    A record claiming success without a passing verification, or whose
    recorded verification status no longer matches current evidence, is a
    mismatch. Fails closed: evidence that cannot be established is
    missing_evidence and the verdict is INVALID.
    """

    def __init__(self, lifecycle_result_service, audit_service, verification_service, resolution_service):
        """The existing #9 result service, #6 audit service, #7
        verification service and the supersession resolution service,
        all wired to the same stores."""
        self._results = lifecycle_result_service
        self._audit = audit_service
        self._verification = verification_service
        self._resolution = resolution_service

    def verify(
        self, task_id: str, lifecycle_result_id: str
    ) -> AgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleVerificationResult:
        """Verify task_id's persisted lifecycle result lifecycle_result_id.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleVerificationError:
                If task_id/lifecycle_result_id is not a non-empty string
        """
        for value, name in ((task_id, "task_id"), (lifecycle_result_id, "lifecycle_result_id")):
            if not value or not isinstance(value, str):
                raise InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleVerificationError(
                    f"{name} is required and must be a non-empty string"
                )

        record = self._results.get(task_id, lifecycle_result_id)
        if record is None:
            return self._result(task_id, lifecycle_result_id, (), (
                f"lifecycle result {lifecycle_result_id} does not exist for task {task_id}",
            ), ())

        mismatches, missing, blockers = [], [], list(record.blocking_artifacts)
        if record.schema_version != IMPACT_LIFECYCLE_RESULT_SCHEMA_VERSION:
            mismatches.append(f"unsupported lifecycle result schema version {record.schema_version!r}")
        if record.status == IMPACT_LIFECYCLE_REMEDIATED and record.verification_status != LIFECYCLE_VERIFICATION_VALID:
            mismatches.append("the lifecycle was recorded as remediated without a passing verification")

        resolution = self._resolution.resolve(task_id)
        if resolution.resolution_state != RESOLUTION_RESOLVED:
            missing.append(f"the authoritative decision cannot be established ({resolution.resolution_state})")
        elif record.authoritative_decision_id is not None and (
            resolution.terminal_decision_id != record.authoritative_decision_id
        ):
            mismatches.append(
                f"recorded authoritative decision {record.authoritative_decision_id} is no longer authoritative "
                f"(now {resolution.terminal_decision_id}); the result is stale"
            )

        if record.operation_id is not None:
            audit = next((r for r in self._audit.list(task_id) if r.operation_id == record.operation_id), None)
            if audit is None:
                missing.append(f"no audit record exists for operation {record.operation_id}")
            else:
                if record.audit_id != audit.audit_id:
                    mismatches.append(
                        f"the lifecycle references audit {record.audit_id}, but operation {record.operation_id} "
                        f"was audited as {audit.audit_id}"
                    )
                for label, recorded, audited in (
                    ("applied", record.applied, audit.applied), ("skipped", record.skipped, audit.skipped),
                    ("failed", record.failed, audit.failed),
                ):
                    if sorted(o.artifact_id for o in recorded) != sorted(o.artifact_id for o in audited):
                        mismatches.append(f"the lifecycle's {label} artifacts disagree with the audit record")
                outside = sorted(set(record.affected_artifacts) - set(audit.artifact_ids))
                if outside:
                    mismatches.append(f"affected artifacts not part of the operation: {', '.join(outside)}")

                current = self._verification.verify(task_id, record.operation_id)
                mismatches.extend(f"artifact state: {m}" for m in current.mismatches)
                blockers.extend(i for i in current.blocking_issues if i not in blockers)
                if record.verification_status is not None and record.verification_status != current.status:
                    mismatches.append(
                        f"recorded verification status {record.verification_status!r} is inconsistent with current "
                        f"evidence ({current.status!r})"
                    )
        return self._result(task_id, lifecycle_result_id, mismatches, missing, blockers)

    @staticmethod
    def _result(task_id, result_id, mismatches, missing, blockers):
        return AgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleVerificationResult(
            task_id=task_id, lifecycle_result_id=result_id,
            status=LIFECYCLE_VERIFICATION_VALID if not mismatches and not missing else LIFECYCLE_VERIFICATION_INVALID,
            mismatches=tuple(mismatches), missing_evidence=tuple(missing), remaining_blockers=tuple(blockers),
        )
