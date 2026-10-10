from dataclasses import dataclass, field


@dataclass(frozen=True)
class QueueRebalanceResult(object):
    """LLMAgentTaskQueueRebalancer.rebalance()'s complete report of
    exactly what one call examined and did (Rule: "Report exactly what
    changed") -- never a queue snapshot or a second ordering of its own:
    every task_id named here is exactly the task_id Commit #1's own
    QueueEntry already carries.

    affected_tasks is every task_id this call actually considered --
    every currently-queued task_id when rebalance() was called with
    task_ids=None, or the subset of the given task_ids that were
    actually queued at the time (a given task_id that was never queued,
    or is no longer queued, is simply not part of affected_tasks at
    all -- see LLMAgentTaskQueueRebalancer.rebalance()'s own docstring
    for why that is not an error). removed_tasks/reordered_tasks/
    unchanged_tasks are a strict three-way partition of affected_tasks:
    every affected task_id appears in exactly one of them.

    Attributes:
        affected_tasks: Every task_id this call considered, in a
            deterministic order (Commit #3's own ordering, computed
            once at the start of the call, before any removal).
        reordered_tasks: Affected task_ids that are still queued after
            this call, and whose position changed since the last time
            this same LLMAgentTaskQueueRebalancer instance observed
            them (see that class's own docstring for what "changed
            since last observed" means -- there is no prior state to
            compare a never-before-seen task_id against, so a task_id
            can only ever land here on its second or later
            appearance).
        removed_tasks: Affected task_ids that were no longer eligible
            (Commit #1's own readiness_service.is_ready() reported
            False) and were not actively reserved (Commit #2's own
            reservation_service.is_reservation_valid() reported False)
            -- removed from the queue by this call (Rule: "Remove
            entries that are no longer valid/eligible").
        unchanged_tasks: Affected task_ids that are still queued after
            this call and whose position did not change (including
            every task_id observed for the first time -- see
            reordered_tasks above).
    """

    affected_tasks: list = field(default_factory=list)
    reordered_tasks: list = field(default_factory=list)
    removed_tasks: list = field(default_factory=list)
    unchanged_tasks: list = field(default_factory=list)
