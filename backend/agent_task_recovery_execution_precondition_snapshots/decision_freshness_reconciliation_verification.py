from .decision_freshness_chain_validation import LLMAgentTaskRecoveryExecutionDecisionFreshnessChainValidationService
from .decision_freshness_reconciliation_result import (
    LLMAgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultService,
)
from .decision_store import LLMAgentTaskRecoveryExecutionPreconditionDecisionStore
from .models import (
    INTEGRITY_VALID,
    RECONCILIATION_COMPLETED,
    RECONCILIATION_RESULT_SCHEMA_VERSION,
    RECONCILIATION_STATUSES,
    RECONCILIATION_UNRESOLVED,
    RECONCILIATION_VERIFICATION_INVALID,
    RECONCILIATION_VERIFICATION_VALID,
    AgentTaskRecoveryExecutionDecisionFreshnessReconciliationVerificationResult,
)


class InvalidAgentTaskRecoveryExecutionDecisionFreshnessReconciliationVerificationError(ValueError):
    """Raised when verify() is given an invalid task_id/result_id."""


class LLMAgentTaskRecoveryExecutionDecisionFreshnessReconciliationVerificationService:
    """Verifies that a persisted reconciliation result (Commit #11) still
    matches the underlying decision chain -- a read-only comparison of
    persisted records, never another reconciliation: it reads the result
    record and the decision store, and compares against Commit #7's own
    chain validation of the currently persisted chain. It never calls
    reconcile(), never repairs, and never writes anything.

    Fails closed: a recorded authoritative decision that no longer exists,
    or a result claiming a valid chain that the persisted chain can no
    longer establish, is missing evidence and makes the verdict INVALID.
    `integrity_service` (Commit #1) is optional; when given, the recorded
    authoritative decision must also pass its check().
    """

    def __init__(
        self,
        result_service: LLMAgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultService = None,
        decision_store: LLMAgentTaskRecoveryExecutionPreconditionDecisionStore = None,
        chain_validation_service: LLMAgentTaskRecoveryExecutionDecisionFreshnessChainValidationService = None,
        integrity_service=None,
    ):
        self._result_service = (
            result_service if result_service is not None
            else LLMAgentTaskRecoveryExecutionDecisionFreshnessReconciliationResultService()
        )
        self._decision_store = (
            decision_store if decision_store is not None else LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
        )
        self._validation_service = (
            chain_validation_service if chain_validation_service is not None
            else LLMAgentTaskRecoveryExecutionDecisionFreshnessChainValidationService(
                decision_store=self._decision_store
            )
        )
        self._integrity_service = integrity_service

    def verify(
        self, task_id: str, result_id: str
    ) -> AgentTaskRecoveryExecutionDecisionFreshnessReconciliationVerificationResult:
        """Verify task_id's persisted reconciliation result_id.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionFreshnessReconciliationVerificationError:
                If task_id/result_id is not a non-empty string
        """
        for value, name in ((task_id, "task_id"), (result_id, "result_id")):
            if not value or not isinstance(value, str):
                raise InvalidAgentTaskRecoveryExecutionDecisionFreshnessReconciliationVerificationError(
                    f"{name} is required and must be a non-empty string"
                )

        mismatches, missing = [], []
        record = self._result_service.get(task_id, result_id)
        if record is None:
            missing.append(f"reconciliation result {result_id} does not exist for task {task_id}")
            return self._verdict(task_id, result_id, mismatches, missing)

        if record.schema_version != RECONCILIATION_RESULT_SCHEMA_VERSION:
            mismatches.append(
                f"unsupported schema version {record.schema_version!r} "
                f"(expected {RECONCILIATION_RESULT_SCHEMA_VERSION})"
            )
        if record.status not in RECONCILIATION_STATUSES:
            mismatches.append(f"unknown reconciliation status {record.status!r}")
        expected_status = (
            RECONCILIATION_COMPLETED if record.chain_valid and not record.conflicts and not record.unresolved
            else RECONCILIATION_UNRESOLVED
        )
        if record.status in RECONCILIATION_STATUSES and record.status != expected_status:
            mismatches.append(
                f"recorded status {record.status!r} contradicts its own chain validity, conflicts and "
                f"unresolved issues (expected {expected_status!r})"
            )

        dangling_previous_replaced = record.changed and any(
            "references a missing decision" in change for change in record.changes
        )
        for label, decision_id in (
            ("previous current", record.previous_current_decision_id),
            ("current", record.current_decision_id),
        ):
            if decision_id is None or self._decision_store.get(decision_id) is not None:
                continue
            if label == "previous current" and dangling_previous_replaced:
                continue
            missing.append(f"{label} decision {decision_id} no longer exists")

        if record.changed != bool(record.changes):
            mismatches.append("state-change flag disagrees with the recorded changes")
        if record.changed and record.current_decision_id == record.previous_current_decision_id:
            mismatches.append(
                f"recorded as changed, but the current decision {record.current_decision_id} equals the previous one"
            )
        if not record.changed and record.current_decision_id != record.previous_current_decision_id:
            mismatches.append(
                f"recorded as unchanged, but the current decision moved from "
                f"{record.previous_current_decision_id} to {record.current_decision_id}"
            )
        if record.changed and record.current_decision_id != record.authoritative_decision_id:
            mismatches.append(
                f"recorded change set the current decision to {record.current_decision_id}, "
                f"not the authoritative decision {record.authoritative_decision_id}"
            )

        for conflict in record.conflicts:
            if conflict not in record.unresolved:
                mismatches.append(f"recorded conflict is missing from the unresolved issues: {conflict}")
            if record.current_decision_id is None or record.current_decision_id not in conflict:
                mismatches.append(f"recorded conflict does not concern the current pointer: {conflict}")
        if not record.chain_valid and not record.unresolved:
            mismatches.append("an invalid chain was recorded without any unresolved issue")

        validation = self._validation_service.validate(task_id)
        if record.chain_valid != validation.valid:
            mismatches.append(
                f"recorded chain validity ({record.chain_valid}) no longer matches the persisted chain "
                f"({validation.valid})"
            )
        authoritative = record.authoritative_decision_id
        if record.chain_valid and authoritative is None:
            missing.append("a valid chain was recorded without an authoritative decision")
        if authoritative is not None:
            if self._decision_store.get(authoritative) is None:
                missing.append(f"authoritative decision {authoritative} no longer exists")
            elif not validation.valid:
                missing.append(
                    f"the persisted chain can no longer establish an authoritative decision to confirm {authoritative}"
                )
            elif validation.latest_decision_id != authoritative:
                mismatches.append(
                    f"recorded authoritative decision {authoritative} does not match the validated chain's "
                    f"authoritative decision {validation.latest_decision_id}"
                )
            elif self._integrity_service is not None:
                integrity = self._integrity_service.check(task_id, authoritative)
                if integrity.status != INTEGRITY_VALID:
                    mismatches.append(
                        f"authoritative decision {authoritative} failed its integrity check: "
                        f"{'; '.join(integrity.issues)}"
                    )

        return self._verdict(task_id, result_id, mismatches, missing)

    @staticmethod
    def _verdict(task_id, result_id, mismatches, missing):
        return AgentTaskRecoveryExecutionDecisionFreshnessReconciliationVerificationResult(
            task_id=task_id, result_id=result_id,
            status=(
                RECONCILIATION_VERIFICATION_VALID if not mismatches and not missing
                else RECONCILIATION_VERIFICATION_INVALID
            ),
            mismatches=tuple(mismatches), missing_evidence=tuple(missing),
        )
