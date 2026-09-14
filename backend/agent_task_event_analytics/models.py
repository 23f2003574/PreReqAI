from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional


@dataclass(frozen=True)
class AgentTaskEventAnalytics:
    """LLMAgentTaskEventAnalyticsService.analyze()'s complete, structured
    outcome for one task_id's event stream (or a [start_time, end_time]
    window of it) -- a computed rollup of numbers/durations/timestamps,
    never itself persisted (no to_dict/from_dict round-trip, the same
    "purely computed result" convention backend.agent_task_events'
    own AgentTaskEventReplayResult/AgentTaskEventConsistencyResult already
    establish for a comparable non-persisted result type).

    Deliberately not a second backend.agent_task_events.AgentTaskEventTimeline
    (Rule: "Do not duplicate the timeline service's representation"): there
    is no raw `events` tuple embedded here at all -- every field is either
    a count, a duration, or a single informational timestamp, never the
    ordered event trail itself (a caller who wants that already has
    LLMAgentTaskEventTimelineService.build() for it).

    start_time/end_time echo exactly the bounds analyze() was called with
    (None when omitted), so a caller never has to remember what window a
    given result reflects.

    event_count/event_type_counts/first_event_at/last_event_at are read
    directly off backend.agent_task_events.AgentTaskEventTimeline.build()'s
    own already-computed fields (Rule: "Reuse the existing event query
    service" carried one level further -- reusing Timeline's own
    aggregation instead of re-querying and re-counting a second time).

    state_transition_counts/failure_count are derived from backend.
    agent_task_events.LLMAgentTaskEventReplayService.replay()'s own
    validated state_transitions -- how many times the task's event stream
    actually (legally) transitioned into each backend.agent_task_lifecycle
    STATES value, never a raw, unvalidated count of claimed to_state
    payload values (that distinction matters: an event claiming an
    unreachable or malformed to_state is exactly what Commit #6's own
    replay() already rejects as a replay error, and this service inherits
    that same discipline rather than re-deriving its own).

    time_to_first_event/time_to_terminal_state are both measured from the
    same reference point: the task's own earliest LIFECYCLE_TRANSITIONED
    event whose payload["to_state"] is backend.agent_task_lifecycle.CREATED
    (its "genesis" event) -- the same raw-claimed-to_state convention
    backend.agent_task_events.AgentTaskEventTimeline.current_observed_state
    already uses, not a new one. Both are None whenever that genesis event
    cannot be found in the analyzed window (Rule: "Never infer a duration
    when required boundary events are absent") -- never approximated from
    the first event in the window or from wall-clock time. time_to_terminal_state
    is additionally None whenever the task has not (yet, within this
    window) reached a terminal state at all.

    time_in_state only ever reports durations between two events this
    service actually observed (Rule, again: no inferred duration) -- there
    is deliberately no trailing "time spent in the current/final state
    since it was last observed" entry, since that would require inferring
    an end boundary (now, or the window's own end_time) that no event
    actually marks.

    retry_scheduled_count/retry_cancelled_count are exactly backend.
    agent_task_events.RETRY_SCHEDULED/RETRY_CANCELLED's own counts within
    event_type_counts, exposed directly for convenience (Rule: "Do not
    invent event types that aren't in the repository" -- both are Commit
    #1-of-the-agent-task-events-series' own existing vocabulary, never a
    new "retry" event type).

    terminal_outcome is replay()'s own final_state, but only when that
    value is actually one of backend.agent_task_lifecycle.TERMINAL_STATES
    -- None while the task's observed history has not reached one.
    """

    task_id: str
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    event_count: int
    event_type_counts: dict
    state_transition_counts: dict
    first_event_at: Optional[datetime]
    last_event_at: Optional[datetime]
    time_to_first_event: Optional[timedelta]
    time_to_terminal_state: Optional[timedelta]
    time_in_state: dict
    retry_scheduled_count: int
    retry_cancelled_count: int
    failure_count: int
    terminal_outcome: Optional[str]


# LLMAgentTaskEventFailureClassifier's own category vocabulary -- deliberately
# distinct from backend.agent_failure_handling.CATEGORIES (NONE/RETRYABLE/
# PERMANENT/PERMISSION_DENIED/DEPENDENCY_FAILURE): that taxonomy is scoped to
# one plan-step execution (step_id) and answers "should this step retry right
# now," a different question from "why did this *task*, across its own event
# stream, end up here" -- reusing it directly would blur two unrelated
# identity spaces (step_id vs task_id) together. Where the two genuinely
# overlap in spirit (DEPENDENCY_FAILURE <-> FAILURE_CATEGORY_DEPENDENCY) the
# naming deliberately echoes it. Only categories with a clean, existing
# event-type-backed signal are included -- "validation/policy" maps to
# READINESS_CHANGED (backend.agent_task_readiness's own gate already folds a
# policy check into readiness), not to a new "policy" event type.
FAILURE_CATEGORY_EXECUTION = "execution"
FAILURE_CATEGORY_DEPENDENCY = "dependency"
FAILURE_CATEGORY_TIMEOUT_CANCELLATION = "timeout_cancellation"
FAILURE_CATEGORY_RETRY_EXHAUSTION = "retry_exhaustion"
FAILURE_CATEGORY_VALIDATION_POLICY = "validation_policy"
FAILURE_CATEGORY_CONTEXT = "context"
FAILURE_CATEGORY_UNKNOWN = "unknown"

FAILURE_CATEGORIES = frozenset(
    {
        FAILURE_CATEGORY_EXECUTION,
        FAILURE_CATEGORY_DEPENDENCY,
        FAILURE_CATEGORY_TIMEOUT_CANCELLATION,
        FAILURE_CATEGORY_RETRY_EXHAUSTION,
        FAILURE_CATEGORY_VALIDATION_POLICY,
        FAILURE_CATEGORY_CONTEXT,
        FAILURE_CATEGORY_UNKNOWN,
    }
)


@dataclass(frozen=True)
class AgentTaskEventFailure:
    """One raw event LLMAgentTaskEventFailureClassifier.classify() found
    claiming a terminal-failure-like backend.agent_task_lifecycle to_state
    (FAILED or CANCELLED) -- a reference to that exact event (event_id/
    occurred_at), never a rewritten or summarized copy of it (Rule: "Never
    rewrite the original event/error"). to_state is the raw claimed value,
    exactly as the event's own payload recorded it -- category/reason are
    this classifier's own added interpretation, kept in separate fields
    so the original claim is always distinguishable from this service's
    opinion about it.

    Deliberately scans *raw* claimed to_state values, not only backend.
    agent_task_events.LLMAgentTaskEventReplayService's own *validated*
    state_transitions: a task cannot legally leave FAILED/CANCELLED once
    reached (backend.agent_task_lifecycle.TRANSITIONS has no outgoing
    edges for either), so a second, later claim of the same or a
    different terminal state is exactly a "repeated failure" this
    classifier is asked to surface, even though replay() itself would
    silently skip a same-state reaffirmation or reject a conflicting one
    as a replay error -- see AgentTaskEventFailureAnalysis.terminal_failure
    for the one, authoritative answer instead.
    """

    event_id: str
    occurred_at: datetime
    to_state: str
    category: str
    reason: str


@dataclass(frozen=True)
class AgentTaskEventFailureAnalysis:
    """LLMAgentTaskEventFailureClassifier.classify()'s complete outcome
    for one task_id's event stream (or a [start_time, end_time] window of
    it).

    failures is every raw failure-claiming event found, oldest to newest
    (including any repeated/duplicate claims); category_counts tallies
    them by category. terminal_failure is the one, authoritative failure
    outcome -- present only when backend.agent_task_events.
    LLMAgentTaskEventReplayService's own validated final_state is itself
    terminal-and-failing (FAILED or CANCELLED), pointing at the specific
    AgentTaskEventFailure entry in `failures` that produced it. A task
    that failed once and was never touched again has exactly one entry in
    `failures`, equal to `terminal_failure`; a task with repeated/noisy
    failure claims can have many entries in `failures` while
    `terminal_failure` still names only the one replay() actually
    validated.
    """

    task_id: str
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    failure_count: int
    failures: tuple
    category_counts: dict
    terminal_failure: Optional[AgentTaskEventFailure]


# LLMAgentTaskEventFailureRecoveryPlanner's own recovery-action vocabulary --
# each backed by a genuinely existing repository mechanism, never invented to
# fill a result (Rule: "Never invent an action merely to fill a result"):
#   RETRY -> backend.agent_task_queue_retry_eligibility's own eligibility
#     check (or backend.agent_task_queue_retry_repair's own CREATE/UPDATE
#     proposal) says the task may currently retry.
#   WAIT_FOR_DEPENDENCY -> backend.agent_task_readiness's own "dependencies"
#     check still fails.
#   REFRESH_CONTEXT -> backend.agent_task_context holds a context record for
#     this task that backend.agent_task_context_refresh could act on.
#   REPAIR_TASK -> backend.agent_task_queue_retry_repair's own plan_repair()
#     proposes a concrete UPDATE/CREATE operation for this task.
#   MARK_UNRECOVERABLE -> the failure is terminal-by-nature (cancellation),
#     retry attempts are exhausted (dead_letter_required), or the category
#     has no automated repair path in this repository (validation/policy).
#   UNRESOLVED -> a supported category, but the collaborator needed to
#     verify feasibility was not supplied, or none of that category's own
#     read-only checks pointed to a specific action.
#   NONE -> there is no failure to plan around at all.
RECOVERY_ACTION_RETRY = "retry"
RECOVERY_ACTION_WAIT_FOR_DEPENDENCY = "wait_for_dependency"
RECOVERY_ACTION_REFRESH_CONTEXT = "refresh_context"
RECOVERY_ACTION_REPAIR_TASK = "repair_task"
RECOVERY_ACTION_MARK_UNRECOVERABLE = "mark_unrecoverable"
RECOVERY_ACTION_UNRESOLVED = "unresolved"
RECOVERY_ACTION_NONE = "no_action_needed"

RECOVERY_ACTIONS = frozenset(
    {
        RECOVERY_ACTION_RETRY,
        RECOVERY_ACTION_WAIT_FOR_DEPENDENCY,
        RECOVERY_ACTION_REFRESH_CONTEXT,
        RECOVERY_ACTION_REPAIR_TASK,
        RECOVERY_ACTION_MARK_UNRECOVERABLE,
        RECOVERY_ACTION_UNRESOLVED,
        RECOVERY_ACTION_NONE,
    }
)

# A plain int scale, higher meaning more urgent -- the same "higher first"
# convention backend.llm.context.LLMContextItem.priority/backend.
# agent_task_queue.QueueEntry.priority already establish, reused rather than
# a new priority representation.
RECOVERY_PRIORITY_NONE = 0
RECOVERY_PRIORITY_LOW = 1
RECOVERY_PRIORITY_MEDIUM = 2
RECOVERY_PRIORITY_HIGH = 3


@dataclass(frozen=True)
class AgentTaskFailureRecoveryPlan:
    """LLMAgentTaskEventFailureRecoveryPlanner.plan()'s single, read-only
    recommendation for task_id -- planning only, never itself performed
    (Rule: "Never execute recovery").

    Deliberately one flat recommendation, not a list (Rule: "avoid
    recommending mutually incompatible actions" -- a task can only
    meaningfully pursue one recovery action at a time, so this plan is
    resolved down to exactly one before it is ever returned):
    failure_event_id/failure_category are read straight off Commit #2's
    own AgentTaskEventFailureAnalysis (Rule: "Reuse Commit #2
    classification rather than reclassifying failures") -- terminal_failure
    when one exists (the one failure replay() actually validated),
    otherwise the most recent raw failure claim, otherwise None (no
    failures at all -- recommended_action is then RECOVERY_ACTION_NONE).

    reason always cites the concrete, existing check/service result this
    plan's own recommended_action is based on -- never a generic or
    invented explanation. blocking_conditions is only ever populated for
    RECOVERY_ACTION_WAIT_FOR_DEPENDENCY, naming the exact
    backend.agent_task_readiness "dependencies" check detail(s) still
    failing.
    """

    task_id: str
    failure_event_id: Optional[str]
    failure_category: Optional[str]
    recommended_action: str
    reason: str
    priority: int
    blocking_conditions: tuple


@dataclass(frozen=True)
class AgentTaskFailureRecoveryResult:
    """LLMAgentTaskFailureRecoveryService.execute()/execute_plan()'s
    complete outcome for one AgentTaskFailureRecoveryPlan.

    planned_action is exactly the plan's own recommended_action (Rule:
    "Reuse Commit #3; don't reimplement recovery decisions" -- this
    service never overrides what Commit #3 decided, only carries it out).
    executed_action is what this call actually attempted -- None only
    when nothing could even be attempted (an unsupported action, or a
    required collaborator was never supplied); otherwise it always
    equals planned_action, whether or not the attempt succeeded.

    success is whether the underlying, already-existing mechanism
    reported the action as having gone through (Rule: "Unsupported
    actions must fail explicitly, not silently succeed" -- an
    unsupported/missing-collaborator case is always success=False,
    never a silent no-op reported as success). failure_reason is the
    concrete reason execution did not succeed, carrying the underlying
    mechanism's own error/explanation verbatim wherever one exists,
    never a generic message.

    affected_reference is a short, human-readable description of what
    this call actually changed (a schedule's own attempt number, a
    dead-letter entry's reason, a repair's own final_status, a context
    refresh's own added/removed counts, a queue entry's own priority) --
    never a duplicated copy of the affected record itself, only enough
    to identify what happened. None when nothing was actually changed
    (a no-op, a failure, or no action needed at all).

    source_failure_event_id/partial (Commit #5) are additive fields: the
    former is exactly the plan's own failure_event_id, carried through so
    a later outcome-recording step can link back to the originating
    failure without re-deriving anything; the latter is only ever True
    for a REPAIR_TASK execution whose own
    backend.agent_task_queue_retry_repair_execution.RetryRepairResult.
    final_status was PARTIAL -- both default to their "nothing special"
    value so every result Commit #4's own tests already construct remains
    valid unchanged (Rule -- Commit #5's own: "Existing recovery execution
    must remain compatible").
    """

    task_id: str
    planned_action: str
    executed_action: Optional[str]
    success: bool
    failure_reason: Optional[str]
    affected_reference: Optional[str]
    source_failure_event_id: Optional[str] = None
    partial: bool = False


# LLMAgentTaskRecoveryOutcomeService's own event_type -- reuses backend.
# agent_task_events' own append-only store/query machinery directly (Rule:
# "Reuse the existing Agent Task Event system where appropriate"; "Do not
# invent another audit/history store") rather than a new persisted entity.
# Not added to that module's own KNOWN_EVENT_TYPES vocabulary -- that
# constant lives in a different, already-completed series' own package, and
# its own docstring already documents emit() as deliberately open (not
# restricted to that enum), so a plain string here needs no changes there.
RECOVERY_OUTCOME_EVENT_TYPE = "recovery_outcome_recorded"

# A closed set (unlike KNOWN_EVENT_TYPES): exactly the three outcomes Commit
# #4's own execution layer can actually distinguish (Rule: "Do not invent
# recovery statuses unsupported by the repository") -- PARTIAL only ever
# applies to a REPAIR_TASK execution whose RetryRepairResult.final_status
# was itself PARTIAL (see AgentTaskFailureRecoveryResult.partial's own
# docstring); every other action can only ever report SUCCESS or FAILED.
RECOVERY_OUTCOME_SUCCESS = "success"
RECOVERY_OUTCOME_FAILED = "failed"
RECOVERY_OUTCOME_PARTIAL = "partial"

RECOVERY_OUTCOME_STATUSES = frozenset(
    {
        RECOVERY_OUTCOME_SUCCESS,
        RECOVERY_OUTCOME_FAILED,
        RECOVERY_OUTCOME_PARTIAL,
    }
)


@dataclass(frozen=True)
class AgentTaskRecoveryOutcome:
    """LLMAgentTaskRecoveryOutcomeService.record()'s durable record of one
    completed AgentTaskFailureRecoveryResult -- never itself authoritative
    task state (Rule: "Do not turn outcomes into authoritative task
    state"), purely a durable fact: "this recovery attempt happened, and
    here is how it went."

    recovery_id is exactly the underlying backend.agent_task_events.
    AgentTaskEvent.event_id this outcome was recorded as (Rule: "Use
    repository conventions for IDs" -- no second id-generation scheme).
    source_failure_event_id links back to the originating failure this
    recovery was attempted for (Commit #4's own
    AgentTaskFailureRecoveryResult.source_failure_event_id, itself Commit
    #3's own plan.failure_event_id, carried through unbroken) -- a
    reference, never a copy of that event.

    started_at/completed_at are both the single moment record() itself
    ran: Commit #4's own AgentTaskFailureRecoveryResult carries no timing
    metadata of its own (every execution path is synchronous), so this
    service does not fabricate a duration it cannot actually observe --
    both fields are set to the same timestamp rather than inventing a
    fictitious start time.
    """

    recovery_id: str
    task_id: str
    source_failure_event_id: Optional[str]
    planned_action: str
    executed_action: Optional[str]
    status: str
    reason: Optional[str]
    started_at: datetime
    completed_at: datetime


@dataclass(frozen=True)
class AgentTaskRecoveryHistorySummary:
    """LLMAgentTaskRecoveryHistoryService.summarize()'s compact rollup of
    one task's own recorded recovery outcomes -- every field is a plain
    count or a value copied verbatim from the latest
    AgentTaskRecoveryOutcome, never a re-derivation of anything Commit
    #5's own record() already decided (Rule: "Reuse Commit #5 outcomes;
    do not reconstruct them from raw events").

    successful_attempts/failed_attempts/partial_attempts are a strict
    partition of total_attempts (every outcome has exactly one of Commit
    #5's own three RECOVERY_OUTCOME_STATUSES) -- partial_attempts is
    counted separately rather than folded into either bucket, since a
    PARTIAL repair is genuinely neither a full success nor a failure
    (Rule: "Do not invent recovery statuses unsupported by the
    repository" cuts both ways: never inventing a new status, and never
    silently discarding a real one by miscounting it).

    latest_status/latest_action are None only when there are no recorded
    outcomes at all; otherwise latest_action is the latest outcome's own
    executed_action, falling back to its planned_action only when nothing
    was actually executed (an unsupported/unresolved action) -- always
    reporting the most informative real value Commit #5 already recorded,
    never a placeholder.
    """

    task_id: str
    total_attempts: int
    successful_attempts: int
    failed_attempts: int
    partial_attempts: int
    latest_status: Optional[str]
    latest_action: Optional[str]


@dataclass(frozen=True)
class AgentTaskRecoveryEffectiveness:
    """LLMAgentTaskRecoveryEffectivenessService.analyze()'s complete
    outcome for one task_id -- analytics over Commit #6's own recovery
    history, never a second recovery executor or a second metrics
    framework (Rule: "This is analytics over recovery history, not
    another recovery executor").

    attempts is Commit #6's own AgentTaskRecoveryOutcome list, embedded
    verbatim, oldest to newest (Rule: "For each attempt, retain enough
    linkage to identify the source failure and resulting outcome" --
    every entry already carries its own source_failure_event_id/
    recovery_id, so nothing further needs inventing).

    success_rate/success_rate_by_action are None (whole) or simply absent
    (per-action) exactly when there is no attempt to compute a rate over
    -- never 0.0, which would misreport "attempted and always failed" for
    "never attempted at all" (Rule: "Missing outcome boundaries must
    remain unknown, not fabricated"). attempts_by_action/
    success_rate_by_action both key on the same value Commit #6's own
    latest_action already uses (executed_action, falling back to
    planned_action when nothing was actually executed) -- the same
    convention, not a new one.

    failures_followed_by_success counts *distinct* source_failure_event_id
    values that have at least one SUCCESS outcome recorded among their own
    attempts -- never a raw attempt count, since several attempts can
    target the same originating failure.

    terminal_failure_after_recovery is None whenever no failure_classifier
    was supplied to determine it (Rule: "Do not claim causality beyond
    what the stored task/recovery data supports" -- without Commit #2's
    own authoritative, replay-validated answer, this service has no
    reliable way to say whether the task's own real outcome was ultimately
    a terminal failure, so it does not guess); when supplied, it is
    exactly whether Commit #2's own
    LLMAgentTaskEventFailureClassifier.classify().terminal_failure is not
    None -- reused, never re-derived.

    average_recovery_duration is the mean of each attempt's own
    completed_at - started_at (Commit #5's own fields) -- None only when
    there are no attempts at all. Under Commit #5's own current design
    (every attempt is recorded synchronously, so started_at always equals
    completed_at) this is always timedelta(0) -- an honest reflection of
    what is actually observable, not a defect in this commit: "recovery
    duration where timestamps exist" is computed for real from the
    timestamps that do exist, never approximated from anything else.
    """

    task_id: str
    total_attempts: int
    successful_attempts: int
    failed_attempts: int
    partial_attempts: int
    success_rate: Optional[float]
    attempts_by_action: dict
    success_rate_by_action: dict
    failures_followed_by_success: int
    terminal_failure_after_recovery: Optional[bool]
    average_recovery_duration: Optional[timedelta]
    latest_outcome: Optional[AgentTaskRecoveryOutcome]
    attempts: tuple


# The sample size at which LLMAgentTaskRecoveryRecommendationService.
# recommend() treats a historical success rate as fully trustworthy --
# below it, confidence is scaled down proportionally (Rule: "Do not treat
# historical success as a guarantee" -- a 100% success rate from a single
# past attempt should never carry the same weight as 100% from several).
# Deliberately small and documented, not a tuned/learned parameter: this is
# a plain, explainable dampening rule, not a second statistics framework.
MINIMUM_CONFIDENT_SAMPLE_SIZE = 3


@dataclass(frozen=True)
class AgentTaskRecoveryRecommendation:
    """LLMAgentTaskRecoveryRecommendationService.recommend()'s complete
    outcome for one task_id -- a decision layer over Commits #2/#3/#6/#7,
    never a second strategy/recommendation framework and never itself an
    executor (Rule: "Never execute the recommendation").

    recommended_action is always exactly Commit #3's own plan.
    recommended_action (Rule: "Reuse existing failure classification/
    planning semantics"; "Do not invent actions") -- this service never
    substitutes a different action based on history; historical evidence
    only ever adjusts *confidence* and *reason*, never *which* action is
    named, since Commit #3's own planner is the sole authority on which
    actions are currently feasible at all (retry/execution limits,
    dependency/readiness state) via its own already-existing collaborators.

    confidence is a plain 0.0-1.0 float, not a new qualitative scale
    (Rule: "Do not invent a second ... framework") -- it is 0.0 whenever
    there is no supporting evidence at all (no prior attempts of this
    exact action for this exact failure category), and otherwise the
    historical success rate for that action *within that same failure
    category*, scaled down for a small sample via
    MINIMUM_CONFIDENT_SAMPLE_SIZE. Category-scoping is deliberate: an
    action's track record against a *different* kind of failure is not
    treated as evidence for the current one (Rule, implicitly: historical
    success must actually apply to the situation at hand to count as
    evidence) -- when no failure classifier was supplied to determine
    each past attempt's own category, this falls back to the action's
    unscoped history rather than refusing to answer at all.

    supporting_recovery_ids names only the successful past attempts that
    actually back this confidence figure -- Commit #5/#6's own
    recovery_id values, never a copy of those records. blocking_conditions
    is exactly Commit #3's own plan.blocking_conditions, carried through
    unchanged.
    """

    task_id: str
    recommended_action: str
    confidence: float
    reason: str
    supporting_recovery_ids: tuple
    blocking_conditions: tuple
