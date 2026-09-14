from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from backend.agent_task_event_analytics import (
    RECOVERY_OUTCOME_FAILED,
    RECOVERY_OUTCOME_PARTIAL,
    RECOVERY_OUTCOME_SUCCESS,
    LLMAgentTaskFailureRecoveryService,
)
from backend.storage import AtomicJsonFile

from .models import AgentTaskRecoveryPreflightConsumption
from .preflight_authorization_validation import LLMAgentTaskRecoveryPreflightAuthorizationValidationService
from .preflight_store import LLMAgentTaskRecoveryPreflightStore


class InvalidAgentTaskRecoveryPreflightConsumptionError(ValueError):
    """Raised when consume()/get() is given invalid arguments, or an
    authorization is not currently valid enough to consume."""


class AgentTaskRecoveryPreflightConsumptionStore(ABC):
    """Raw persistence for the one AgentTaskRecoveryPreflightConsumption
    record per authorization_id, ever -- the same single-record-per-key
    shape Commit #8/#9's own approval/authorization stores already use.
    There is no update() or delete(): a consumption is recorded exactly
    once and never rewritten."""

    @abstractmethod
    def save(self, record: AgentTaskRecoveryPreflightConsumption) -> AgentTaskRecoveryPreflightConsumption:
        ...

    @abstractmethod
    def get(self, authorization_id: str) -> Optional[AgentTaskRecoveryPreflightConsumption]:
        ...


class InMemoryAgentTaskRecoveryPreflightConsumptionStore(AgentTaskRecoveryPreflightConsumptionStore):
    """Stores AgentTaskRecoveryPreflightConsumption records in memory,
    for development and testing."""

    def __init__(self):
        self._records: dict = {}

    def save(self, record: AgentTaskRecoveryPreflightConsumption) -> AgentTaskRecoveryPreflightConsumption:
        stored = deepcopy(record)
        self._records[record.authorization_id] = stored
        return deepcopy(stored)

    def get(self, authorization_id: str) -> Optional[AgentTaskRecoveryPreflightConsumption]:
        record = self._records.get(authorization_id)
        return deepcopy(record) if record is not None else None


class JsonAgentTaskRecoveryPreflightConsumptionStore(AgentTaskRecoveryPreflightConsumptionStore):
    """Persists AgentTaskRecoveryPreflightConsumption records to a JSON
    file, keyed by authorization_id."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, record: AgentTaskRecoveryPreflightConsumption) -> AgentTaskRecoveryPreflightConsumption:
        records = self.file.read()
        records[record.authorization_id] = record.to_dict()
        self.file.write(records)
        return deepcopy(record)

    def get(self, authorization_id: str) -> Optional[AgentTaskRecoveryPreflightConsumption]:
        records = self.file.read()
        data = records.get(authorization_id)
        return AgentTaskRecoveryPreflightConsumption.from_dict(data) if data is not None else None


def _outcome_for(execution_result) -> str:
    if not execution_result.success:
        return RECOVERY_OUTCOME_FAILED
    return RECOVERY_OUTCOME_PARTIAL if execution_result.partial else RECOVERY_OUTCOME_SUCCESS


class LLMAgentTaskRecoveryPreflightAuthorizationConsumptionService:
    """The execution boundary: safely hands one Commit #9 authorization's
    already-approved recovery plan to backend.agent_task_event_analytics'
    own existing Commit #4 LLMAgentTaskFailureRecoveryService -- never a
    second execution engine, authorization system, or task-state
    mechanism (Rule): consume() calls that real service's own
    execute_plan() exactly once, and every gate before it is exactly one
    existing collaborator's own read, never re-derived.

    Never executes unless validation succeeds (Rule: "Never execute a
    plan unless authorization validation succeeds"): consume() calls
    Commit #10's own validate() first and raises immediately, before
    touching the execution service at all, for anything it reports
    invalid (missing/revoked/superseded/invalidated/stale/lapsed-approval/
    policy-blocked) -- this never re-implements any of those checks
    itself.

    Idempotent by authorization_id, unconditionally (Rule: "Prevent
    accidental double execution from repeated consume() calls";
    "already-consumed authorization cannot execute twice"): the FIRST
    thing consume() does is check the consumption store for an existing
    record -- if found, it is returned exactly as recorded, and
    execute_plan() is never called again, regardless of what the
    authorization's current validation state is by then. A failed
    execution is recorded exactly like a successful one (Rule: "If
    execution fails, record the failed consumption outcome without
    silently retrying it") -- there is no retry loop anywhere in this
    class, only ever one attempt, ever, per authorization_id.

    Bound to the exact task_id + preflight_id (Rule): the plan executed
    is always the one embedded on the EXACT preflight named by the
    authorization being consumed (resolved via Commit #4's own
    preflight_store.history()), never a freshly re-planned or
    differently-scoped one.

    Does not bypass existing safeguards (Rule: "Do not bypass existing
    retry, budget, dependency, policy, or recovery safeguards"): the
    plan is hard-executed through the real, unmodified
    LLMAgentTaskFailureRecoveryService.execute_plan() -- every retry/
    readiness/context/repair/dead-letter collaborator that service was
    itself configured with runs exactly as it always would; this class
    adds no bypass, shortcut, or parallel path around any of it.

    execution_result is embedded verbatim on the persisted record (Rule:
    "execution/result reference is preserved") -- never summarized;
    `outcome` reuses backend.agent_task_event_analytics' own existing
    RECOVERY_OUTCOME_SUCCESS/FAILED/PARTIAL vocabulary rather than
    inventing a new one.
    """

    def __init__(
        self,
        validation_service: LLMAgentTaskRecoveryPreflightAuthorizationValidationService = None,
        preflight_store: LLMAgentTaskRecoveryPreflightStore = None,
        execution_service: LLMAgentTaskFailureRecoveryService = None,
        store: AgentTaskRecoveryPreflightConsumptionStore = None,
    ):
        self._preflight_store = (
            preflight_store if preflight_store is not None else LLMAgentTaskRecoveryPreflightStore()
        )
        self._validation_service = (
            validation_service
            if validation_service is not None
            else LLMAgentTaskRecoveryPreflightAuthorizationValidationService(preflight_store=self._preflight_store)
        )
        self._execution_service = (
            execution_service if execution_service is not None else LLMAgentTaskFailureRecoveryService()
        )
        self._store = store if store is not None else InMemoryAgentTaskRecoveryPreflightConsumptionStore()

    def consume(self, task_id: str, authorization_id: str) -> AgentTaskRecoveryPreflightConsumption:
        """Validate, then execute, task_id's exact authorization_id's own
        recovery plan exactly once. Idempotent: an already-consumed
        authorization_id returns its original recorded outcome unchanged,
        never re-executing.

        Raises:
            InvalidAgentTaskRecoveryPreflightConsumptionError: If
                task_id/authorization_id is not a non-empty string,
                Commit #10's own validate() reports the authorization
                invalid, or its own referenced preflight has no recovery
                plan to execute
        """
        self._require_text(task_id, "task_id")
        self._require_text(authorization_id, "authorization_id")

        existing = self._store.get(authorization_id)
        if existing is not None and existing.task_id == task_id:
            return existing

        validation = self._validation_service.validate(task_id, authorization_id)
        if not validation.valid:
            raise InvalidAgentTaskRecoveryPreflightConsumptionError(
                f"authorization {authorization_id!r} is not valid and cannot be consumed: "
                + "; ".join(validation.blocking_reasons)
            )

        preflight = next(
            (
                record
                for record in self._preflight_store.history(task_id)
                if record.preflight_id == validation.preflight_id
            ),
            None,
        )
        if preflight is None or preflight.plan is None:
            raise InvalidAgentTaskRecoveryPreflightConsumptionError(
                f"preflight {validation.preflight_id!r} has no recovery plan to execute"
            )

        execution_result = self._execution_service.execute_plan(preflight.plan)

        consumption = AgentTaskRecoveryPreflightConsumption(
            task_id=task_id,
            authorization_id=authorization_id,
            preflight_id=preflight.preflight_id,
            consumed_at=datetime.now(timezone.utc),
            execution_result=execution_result,
            outcome=_outcome_for(execution_result),
        )
        return self._store.save(consumption)

    def get(self, task_id: str, authorization_id: str) -> Optional[AgentTaskRecoveryPreflightConsumption]:
        """task_id's consumption record for its exact authorization_id,
        or None if it was never consumed -- never raises for a missing
        record.

        Raises:
            InvalidAgentTaskRecoveryPreflightConsumptionError: If
                task_id or authorization_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        self._require_text(authorization_id, "authorization_id")

        record = self._store.get(authorization_id)
        if record is None or record.task_id != task_id:
            return None
        return record

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryPreflightConsumptionError(
                f"{field_name} is required and must be a non-empty string"
            )
