from collections.abc import (
    Mapping,
)

from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from .execution_recovery_replay_error import (
    ExecutionRecoveryReplayError,
)

from .execution_recovery_replay import (
    ExecutionRecoveryReplay,
)


class ExecutionRecoveryReplayService:
    """
    Replays a session's recovery journal to diagnose whether the
    same recovery decision path reproduces the expected state.

    A session's journal is assumed to already exist elsewhere; this
    service depends on a plain resolver callable for it rather than
    a concrete store:
    - journal_history_resolver(session_id) -> the session's journal
      entries, in chronological order; matches the signature of an
      execution recovery journal service's history() method

    Behavior:
    - create() fixes the set of journal entries a replay covers, in
      their exact chronological order, as of that moment
    - execute() derives a result by folding those entries' details,
      strictly in the order fixed at creation, so replaying the same
      entries always reproduces the same result regardless of what
      is later appended to the live journal
    - compare() reports each field where the executed result
      diverges from an expected mapping
    - result() looks up the executed result, or None before
      execute() has run

    Replay is read-only throughout: it only ever reads journal
    entries through the resolver, and never calls anything that
    could mutate the journal or any other recovery state.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, journal_history_resolver):
        self._journal_history_resolver = journal_history_resolver
        self._replays_by_id = {}
        self._lock = RLock()

    def create(self, session_id: str) -> ExecutionRecoveryReplay:
        """
        Fix the set of journal entries a replay covers, in their
        exact chronological order, as of this moment.

        Raises:
            ExecutionRecoveryReplayError: If session_id is None or
                blank
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            entries = self._journal_history_resolver(session_id) or ()

            replay = ExecutionRecoveryReplay(
                session_id=session_id,
                journal_entry_ids=tuple(entry.entry_id for entry in entries),
            )

            self._replays_by_id[replay.replay_id] = replay

            return replay

    def execute(self, replay_id: str) -> ExecutionRecoveryReplay:
        """
        Derive a result by folding the covered entries' details,
        strictly in the order fixed at creation.

        Raises:
            ExecutionRecoveryReplayError: If replay_id is None or
                blank, or no replay is known under it
        """

        self._validate_id(replay_id, "replay ID")

        with self._lock:
            replay = self._resolve(replay_id)

            entries = self._journal_history_resolver(replay.session_id) or ()
            entries_by_id = {entry.entry_id: entry for entry in entries}

            accumulated = {}

            for journal_entry_id in replay.journal_entry_ids:
                entry = entries_by_id.get(journal_entry_id)

                if entry is not None:
                    accumulated.update(dict(entry.details))

            updated = replace(replay, result=accumulated)
            self._replays_by_id[replay_id] = updated

            return updated

    def compare(self, replay_id: str, expected: Mapping) -> tuple:
        """
        Report each field where the executed result diverges from
        an expected mapping.

        Raises:
            ExecutionRecoveryReplayError: If replay_id is None or
                blank, expected is not a mapping, no replay is known
                under replay_id, or it has not been executed
        """

        self._validate_id(replay_id, "replay ID")

        if not isinstance(expected, Mapping):
            raise ExecutionRecoveryReplayError("Cannot compare a replay against a non-mapping expected value.")

        with self._lock:
            replay = self._resolve(replay_id)

            if replay.result is None:
                raise ExecutionRecoveryReplayError(f"Replay ID {replay_id!r} has not been executed.")

            fields = sorted(set(replay.result) | set(expected))

            return tuple(
                {
                    "field": field_name,
                    "replayed_value": replay.result.get(field_name),
                    "expected_value": expected.get(field_name),
                }
                for field_name in fields
                if replay.result.get(field_name) != expected.get(field_name)
            )

    def result(self, replay_id: str):
        """
        Look up the executed result.

        Raises:
            ExecutionRecoveryReplayError: If replay_id is None or
                blank, or no replay is known under it
        """

        self._validate_id(replay_id, "replay ID")

        with self._lock:
            return self._resolve(replay_id).result

    def _resolve(self, replay_id: str) -> ExecutionRecoveryReplay:
        replay = self._replays_by_id.get(replay_id)

        if replay is None:
            raise ExecutionRecoveryReplayError(f"No replay is known under replay ID {replay_id!r}.")

        return replay

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionRecoveryReplayError(f"Cannot use an empty or blank {field_name}.")
