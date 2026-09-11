from dataclasses import dataclass, field


@dataclass(frozen=True)
class QueueExpirationResult(object):
    """LLMAgentTaskQueueExpirationService.expire()/expire_all()'s
    complete report of exactly what one call found and did (Rule:
    "Report every affected task explicitly") -- an entry that is still
    within its queue lifetime is never reported here at all (Rule:
    "Ignore entries that are still valid"; Behavior 2), so an empty
    result means exactly "nothing was found expired," not "nothing was
    checked."

    removed_entries/skipped_tasks are a two-way split of expired_tasks:
    every expired task_id appears in exactly one of them, never both.

    Attributes:
        expired_tasks: Every task_id found past its queue lifetime this
            call -- the same set removed_entries/skipped_tasks
            partition.
        removed_entries: The actual QueueEntry records (captured
            immediately before removal, not merely their task_ids --
            the last known priority/queued_at/claim state of each) that
            this call removed from the queue.
        skipped_tasks: Expired task_ids that were *not* removed because
            they are still actively, validly reserved (Commit #2's own
            reservation_service.is_reservation_valid()) -- Rule:
            "Preserve valid active reservations/entries." Still counted
            as expired (their queue lifetime genuinely lapsed), just
            not acted on destructively.
        errors: (task_id, error) pairs for anything this call could not
            act on -- concretely, a task_id passed to expire() that is
            not currently queued at all (Rule: "Missing entry is safe"
            -- reported here rather than raised).
    """

    expired_tasks: list = field(default_factory=list)
    removed_entries: list = field(default_factory=list)
    skipped_tasks: list = field(default_factory=list)
    errors: list = field(default_factory=list)
