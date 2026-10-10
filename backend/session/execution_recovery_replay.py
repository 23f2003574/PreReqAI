from collections.abc import (
    Mapping,
)

from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from types import (
    MappingProxyType,
)

from uuid import uuid4

from .execution_recovery_replay_error import (
    ExecutionRecoveryReplayError,
)


@dataclass(frozen=True)
class ExecutionRecoveryReplay:
    """
    Immutable record of replaying a session's recovery journal to
    diagnose whether the same decision path reproduces the expected
    state.

    The replay is a value object only. It performs no replaying of
    its own; creating a replay against a session's current journal,
    executing it, comparing its result against an expectation, and
    looking up that result is the responsibility of an execution
    recovery replay service.

    Attributes:
        replay_id: The replay's unique identifier
        session_id: The identifier of the execution session whose
            journal this replay reproduces
        journal_entry_ids: The journal entry IDs this replay covers,
            in the exact chronological order they were recorded,
            fixed at creation time
        result: The state derived by replaying those entries in
            order, as an immutable mapping, or None before execute()
            has run
        created_at: When this replay was created
    """

    session_id: str

    journal_entry_ids: tuple = field(
        default_factory=tuple,
    )

    result: Mapping | None = None

    replay_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.replay_id, "replay ID")
        self._require_text(self.session_id, "session ID")

        if not isinstance(self.created_at, datetime):
            raise ExecutionRecoveryReplayError(
                "Cannot build an execution recovery replay with a non-datetime created_at."
            )

        if self.journal_entry_ids is None:
            raise ExecutionRecoveryReplayError(
                "Cannot build an execution recovery replay with a None journal_entry_ids."
            )

        journal_entry_id_list = list(self.journal_entry_ids)

        for journal_entry_id in journal_entry_id_list:
            self._require_text(journal_entry_id, "journal entry ID")

        if len(set(journal_entry_id_list)) != len(journal_entry_id_list):
            raise ExecutionRecoveryReplayError(
                "Cannot build an execution recovery replay with duplicate journal entry IDs."
            )

        object.__setattr__(self, "journal_entry_ids", tuple(journal_entry_id_list))

        if self.result is not None:
            if not isinstance(self.result, Mapping):
                raise ExecutionRecoveryReplayError(
                    "Cannot build an execution recovery replay with a non-mapping result."
                )

            object.__setattr__(self, "result", MappingProxyType(dict(self.result)))

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionRecoveryReplayError(
                f"Cannot build an execution recovery replay with an empty or blank {field_name}."
            )
