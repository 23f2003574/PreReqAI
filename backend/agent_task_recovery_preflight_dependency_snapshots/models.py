from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Optional
from uuid import uuid4

# One entry's effective dependency state, captured at snapshot time (or
# recomputed live for diff()'s own "current" side) -- deliberately a
# richer vocabulary than backend.agent_task_recovery_schedule_dependencies.
# models' own READY/BLOCKED/FAILED/UNKNOWN (that package's own state is a
# single, most-severe-wins verdict for a whole SCHEDULE; this one is a
# per-DEPENDENCY classification, so every one of
# backend.agent_task_dependency_resolution.AgentTaskDependencyResolution's
# own six buckets gets its own distinct value here, plus COMPLETED for a
# dependency present in the graph but in none of those six buckets --
# resolve()'s own "no bucket means satisfied" convention, made explicit
# rather than left as an absence, since a snapshot needs to be able to
# name a dependency as "already done" just as much as "still blocking").
READY = "ready"
PENDING = "pending"
FAILED = "failed"
BLOCKED = "blocked"
UNRESOLVED = "unresolved"
CYCLIC = "cyclic"
COMPLETED = "completed"
DEPENDENCY_SNAPSHOT_STATES = frozenset({READY, PENDING, FAILED, BLOCKED, UNRESOLVED, CYCLIC, COMPLETED})


@dataclass(frozen=True)
class AgentTaskDependencySnapshotEntry:
    """One dependency_task_id's effective state, as of one snapshot (or
    one live re-check) -- a plain value object, never itself mutated.
    """

    dependency_task_id: str
    state: str


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightDependencySnapshot:
    """LLMAgentTaskRecoveryPreflightDependencySnapshotService.create()'s
    durable, point-in-time capture of task_id's whole dependency graph,
    bound to the EXACT preflight it was taken for -- never a second
    dependency graph engine (Rule: "Reuse existing dependency resolver;
    don't duplicate dependency semantics"): every entry in `dependencies`
    is read straight from backend.agent_task_dependency_resolution.
    LLMAgentTaskDependencyResolver.resolve() (or, as a fallback, backend.
    agent_task_dependencies.LLMAgentTaskDependencyService.
    check_dependencies()) -- this class never traverses an edge or
    classifies a lifecycle state itself.

    Bound to the exact (task_id, preflight_id) this snapshot was taken
    for (Rule: "capture ... for the exact task/preflight") -- preflight_id
    is verified, at create() time, to actually be a preflight recorded for
    task_id via backend.agent_task_recovery_guardrails' own
    LLMAgentTaskRecoveryPreflightStore, never merely trusted from the
    caller.

    `dependencies` holds one AgentTaskDependencySnapshotEntry per
    dependency_task_id reachable from task_id at capture time, sorted by
    dependency_task_id for deterministic comparison -- task_id itself is
    never included (the same "never includes itself" convention every
    dependency-graph result in this repository already uses).

    Immutable once recorded (Rule: "Preserve immutable snapshots") -- a
    frozen dataclass, never replaced or edited in place; the store this
    class is persisted through has no update()/delete() at all, only
    save()/get()/list_for_task(), the same append-only discipline this
    project's own comparable history stores already establish.
    """

    task_id: str
    preflight_id: str
    dependencies: tuple
    captured_at: datetime
    snapshot_id: str = field(default_factory=lambda: str(uuid4()))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["captured_at"] = self.captured_at.isoformat()
        data["dependencies"] = [asdict(entry) for entry in self.dependencies]
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "AgentTaskRecoveryPreflightDependencySnapshot":
        payload = dict(data)
        value = payload.get("captured_at")
        if isinstance(value, str):
            payload["captured_at"] = datetime.fromisoformat(value)
        payload["dependencies"] = tuple(
            AgentTaskDependencySnapshotEntry(**entry) for entry in payload.get("dependencies") or ()
        )
        return cls(**payload)


@dataclass(frozen=True)
class AgentTaskDependencySnapshotStateChange:
    """One dependency_task_id whose own state moved between a snapshot
    and a later diff() call, without landing in either of diff()'s own
    more specific `resolved`/`newly_blocked` buckets (see
    AgentTaskRecoveryPreflightDependencySnapshotDiff's own docstring)."""

    dependency_task_id: str
    previous_state: str
    current_state: str


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightDependencySnapshotDiff:
    """LLMAgentTaskRecoveryPreflightDependencySnapshotService.diff()'s
    complete, read-only comparison of one persisted snapshot against
    task_id's CURRENT dependency graph -- never a second reconciliation
    engine (Rule: "reuse existing dependency resolver; don't duplicate
    dependency semantics") and never itself a scheduling/recovery
    decision (Rule: "Read-only diff(); no scheduling/recovery side
    effects"): every fact here comes from comparing the snapshot's own
    already-persisted entries against one fresh resolve()/
    check_dependencies() call, nothing more.

    Every dependency_task_id present on either side is classified into
    exactly one bucket, never more than one (Rule: "Detect added,
    removed, resolved, newly-blocked, and state-changed dependencies"):

        added: reachable now, but not part of the snapshot at all --
            a new dependency edge/node since the snapshot was taken.
        removed: part of the snapshot, but not reachable at all now --
            the dependency edge/node itself is gone (distinct from
            `resolved`, which stays reachable, just COMPLETED).
        resolved: reachable on both sides, and now COMPLETED when it
            was not COMPLETED in the snapshot.
        newly_blocked: reachable on both sides, now BLOCKED when it was
            not BLOCKED in the snapshot -- called out as its own bucket
            (rather than folded into state_changed) since a newly-BLOCKED
            dependency is the one transition callers most need to react
            to.
        state_changed: reachable on both sides, with any OTHER state
            change (e.g. ready->pending, pending->failed, blocked->
            pending) -- every transition not already covered by
            `resolved`/`newly_blocked` above, as
            AgentTaskDependencySnapshotStateChange entries.

    A dependency whose state is identical on both sides appears in none
    of the above (Rule: "identical graph" produces every bucket empty).
    changed is exactly whether any bucket above is non-empty.
    """

    task_id: str
    snapshot_id: str
    preflight_id: str
    added: tuple
    removed: tuple
    resolved: tuple
    newly_blocked: tuple
    state_changed: tuple
    changed: bool
    diffed_at: datetime


# Commit #2's own overall verdict vocabulary -- a status ONE LEVEL UP from
# AgentTaskRecoveryPreflightDependencySnapshotDiff's own per-dependency
# buckets (which this commit reuses verbatim, never re-derives): UNCHANGED
# is exactly `not diff.changed`; CHANGED is exactly `diff.changed`;
# INDETERMINATE is a THIRD value neither of those two booleans can express
# on its own -- the live dependency graph could not be resolved at all
# this call (Rule: "Clearly distinguish unchanged, changed, and
# indeterminate states"), so nothing about "changed" can be honestly
# claimed either way.
UNCHANGED = "unchanged"
CHANGED = "changed"
INDETERMINATE = "indeterminate"
RECONCILIATION_STATUSES = frozenset({UNCHANGED, CHANGED, INDETERMINATE})


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightDependencySnapshotReconciliation:
    """LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService.
    reconcile()'s complete, read-only verdict on whether one Commit #1
    snapshot still matches task_id's CURRENT dependency graph -- never a
    second dependency comparison engine (Rule: "Reuse #1's snapshot
    service ... do not create another dependency resolver"): every
    per-dependency fact here (added/removed/resolved/blocked/changed) is
    Commit #1's own AgentTaskRecoveryPreflightDependencySnapshotDiff,
    carried through unchanged -- this class only adds the single overall
    `status` verdict and fail-closed handling on top.

    status/reliable are the two views of the same fact: reliable is
    exactly `status != INDETERMINATE`. blocked is Commit #1's own
    `newly_blocked` (Rule's own wording, "blocked", used here verbatim);
    changed is Commit #1's own `state_changed`. added/removed/resolved
    are Commit #1's own fields of the same name, untouched.

    reason is populated only when status is INDETERMINATE (Rule: "Never
    silently treat missing evidence as fresh/unchanged" -- the same
    fail-closed discipline backend.agent_task_recovery_schedule_dependencies'
    own reconciliation.py already establishes for a comparable case,
    reused here rather than re-derived): every other field is then empty/
    False, never a fabricated partial comparison.

    Deterministic and idempotent by construction (Rule): unlike backend.
    agent_task_recovery_schedule_dependencies' own reconciliation service
    (which persists an append-only observation history and diffs against
    the PREVIOUS stored observation -- a fire-once signal, non-idempotent
    across two reads taken moments apart), this class writes nothing at
    all. Every call is a pure function of (Commit #1's already-persisted,
    immutable snapshot, one fresh live dependency resolution) -- calling
    reconcile() twice in a row with nothing having changed in between
    always returns the exact same result, with no history to drift.
    """

    task_id: str
    snapshot_id: str
    preflight_id: str
    status: str
    reliable: bool
    added: tuple
    removed: tuple
    resolved: tuple
    blocked: tuple
    changed: tuple
    reason: Optional[str]
    reconciled_at: datetime
    version: Optional[int] = None
    integrity: Optional[object] = None
    signature: Optional[object] = None


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightDependencySnapshotVersion:
    """Commit #3's own thin, monotonically-numbered index entry binding
    one Commit #1 snapshot_id to an exact (task_id, preflight_id, version)
    -- never a copy of the snapshot's own content (Rule: "Do not invent a
    generic version-control system"): the real, immutable snapshot data
    stays entirely in Commit #1's own store; this is only a pointer to it,
    the same "version record references content, never duplicates it"
    shape backend.agent_policy_versioning.LLMAgentPolicyVersion already
    establishes for a comparable case (there the payload -- `rules` -- is
    embedded directly since Commit #1(-of-that-series)'s own store keeps
    no history of its own; here Commit #1(-of-this-series) already IS
    that immutable history, so only a reference is needed).

    version is 1-based and monotonically increasing per (task_id,
    preflight_id), assigned as `len(existing versions) + 1` -- the exact
    same numbering convention LLMAgentPolicyVersionService.list_versions()
    already uses (Rule: "reuse existing repository version/identity
    conventions").
    """

    task_id: str
    preflight_id: str
    version: int
    snapshot_id: str
    created_at: datetime

    def to_dict(self) -> dict:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "AgentTaskRecoveryPreflightDependencySnapshotVersion":
        payload = dict(data)
        value = payload.get("created_at")
        if isinstance(value, str):
            payload["created_at"] = datetime.fromisoformat(value)
        return cls(**payload)


# Commit #4's own integrity verdict vocabulary. VALID: the current
# canonical content/metadata hash matches the baseline recorded the
# first time this snapshot_id was ever verified (trust-on-first-use,
# the same "first observation establishes the trusted value" idea
# backend.llm.response_cache/backend.llm.tool_idempotency already use
# their own canonical-hash for, applied here to a durable snapshot
# instead of a cache key). CORRUPTED: content, metadata, or version
# binding no longer agrees with that baseline. MISSING: no such
# snapshot_id is recorded for task_id at all. UNVERIFIABLE: computing
# the current hash itself failed (fail-closed, mirrors Commit #2's own
# INDETERMINATE).
VALID = "valid"
CORRUPTED = "corrupted"
MISSING = "missing"
UNVERIFIABLE = "unverifiable"
INTEGRITY_STATUSES = frozenset({VALID, CORRUPTED, MISSING, UNVERIFIABLE})


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightDependencySnapshotIntegrityRecord:
    """The durable, write-once baseline integrity_value recorded the
    first time Commit #4's verify() ever ran for one exact (task_id,
    snapshot_id) -- never overwritten afterward (Rule: "Preserve
    immutable snapshot history"); every later verify() call compares a
    freshly recomputed value against this same baseline."""

    task_id: str
    snapshot_id: str
    integrity_value: str
    recorded_at: datetime

    def to_dict(self) -> dict:
        data = asdict(self)
        data["recorded_at"] = self.recorded_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "AgentTaskRecoveryPreflightDependencySnapshotIntegrityRecord":
        payload = dict(data)
        value = payload.get("recorded_at")
        if isinstance(value, str):
            payload["recorded_at"] = datetime.fromisoformat(value)
        return cls(**payload)


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightDependencySnapshotIntegrityResult:
    """LLMAgentTaskRecoveryPreflightDependencySnapshotIntegrityService.
    verify()'s complete, read-only verdict -- bound to the exact task_id,
    preflight_id, snapshot_id, and (when a version_service is configured)
    version (Rule: "Bind verification to exact task, preflight, snapshot,
    and version"). valid is exactly `status == VALID`; reasons collects
    every distinct issue found (content/metadata hash mismatch, and/or an
    ambiguous multi-version binding), never only the first."""

    task_id: str
    snapshot_id: str
    preflight_id: Optional[str]
    version: Optional[int]
    status: str
    valid: bool
    integrity_value: Optional[str]
    reasons: tuple
    verified_at: datetime


# Commit #5's own signature-verdict vocabulary. Reuses VALID/MISSING/
# UNVERIFIABLE verbatim from Commit #4 (same meaning, same word --
# never a second, colliding constant with the same string value); adds
# INVALID for "a signature is recorded, the snapshot itself exists, but
# authenticity/binding does not check out" -- distinct from Commit #4's
# own CORRUPTED, which describes the snapshot's CONTENT, not a
# signature's own authenticity.
INVALID = "invalid"
SIGNATURE_STATUSES = frozenset({VALID, INVALID, MISSING, UNVERIFIABLE})


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightDependencySnapshotSignature:
    """One immutable, append-only signing event for a Commit #1 snapshot
    -- Rule: "Preserve signature metadata/history; don't overwrite prior
    signatures": sign() always appends a NEW record (never checked for
    duplicates/idempotency the way #1-#4's own content-addressed writes
    are), so re-signing (e.g. after a key rotation) is always possible
    and every past signature stays inspectable.

    signature is this record's own canonical payload -- {task_id,
    preflight_id, snapshot_id, version, integrity_value} -- HMAC-SHA256'd
    under the signing key, prefixed "hmac-sha256:". integrity_value is
    Commit #4's own compute() output at signing time, embedded verbatim
    (Rule: "Sign the canonical snapshot representation used by the
    integrity service").
    """

    task_id: str
    preflight_id: str
    snapshot_id: str
    version: Optional[int]
    integrity_value: str
    signature: str
    signed_at: datetime
    signature_id: str = field(default_factory=lambda: str(uuid4()))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["signed_at"] = self.signed_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "AgentTaskRecoveryPreflightDependencySnapshotSignature":
        payload = dict(data)
        value = payload.get("signed_at")
        if isinstance(value, str):
            payload["signed_at"] = datetime.fromisoformat(value)
        return cls(**payload)


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightDependencySnapshotSignatureVerification:
    """LLMAgentTaskRecoveryPreflightDependencySnapshotSigningService.
    verify_signature()'s complete, read-only verdict -- bound to the
    exact task_id/preflight_id/snapshot_id/version (Rule: "Bind the
    signature to exact task, preflight, snapshot, and version identity").
    valid is exactly `status == VALID`; integrity_status carries Commit
    #4's own status alongside (Rule: "Verify both authenticity and
    snapshot integrity before accepting a signed snapshot")."""

    task_id: str
    snapshot_id: str
    preflight_id: Optional[str]
    version: Optional[int]
    status: str
    valid: bool
    signature_id: Optional[str]
    integrity_status: Optional[str]
    reasons: tuple
    verified_at: datetime


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightDependencySnapshotTrustResult:
    """Commit #6's own single trust-decision verdict -- composes Commit
    #1(existence/binding)/#3(supersession)/#4(integrity)/#5(signature),
    never re-deriving any of their logic itself. trusted is exactly `not
    blocking_reasons` (fail-closed: every blocking condition collected,
    never only the first)."""

    task_id: str
    snapshot_id: str
    preflight_id: Optional[str]
    version: Optional[int]
    trusted: bool
    integrity_status: Optional[str]
    signature_status: Optional[str]
    blocking_reasons: tuple
    validated_at: datetime


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightDependencySnapshotTrustHistoryRecord:
    """Commit #7's own durable, append-only capture of one Commit #6
    AgentTaskRecoveryPreflightDependencySnapshotTrustResult -- every field
    is that result's own evidence, preserved verbatim (Rule: "Preserve
    the exact evidence returned by the trust validator"), never
    re-derived a second way. history_id/recorded_at are this record's own
    bookkeeping (the underlying backend.agent_task_events event's own
    event_id/occurred_at); verified_at is the ORIGINAL trust_result's own
    validated_at, kept distinct from recorded_at since recording can
    happen a moment after validation ran."""

    task_id: str
    preflight_id: Optional[str]
    snapshot_id: str
    version: Optional[int]
    trusted: bool
    integrity_status: Optional[str]
    signature_status: Optional[str]
    blocking_reasons: tuple
    verified_at: datetime
    recorded_at: datetime
    history_id: str


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightDependencySnapshotTrustChangeResult:
    """Commit #8's own comparison of task_id/snapshot_id's PREVIOUSLY
    recorded (Commit #7) trust state against a FRESH (Commit #6) trust
    validation -- never a second verification implementation (Rule: "Do
    not duplicate verification logic"): current_trust is exactly what
    LLMAgentTaskRecoveryPreflightDependencySnapshotTrustService.
    validate() itself returned this call; previous_trust is exactly
    Commit #7's own latest() for this (task_id, snapshot_id), None only
    when nothing was ever recorded before.

    changed is purely field-value comparison (Rule: "Do not infer trust
    changes from timestamps alone") -- checked_at/verified_at never
    participate. changed_dimensions names every field that differs
    (trusted/integrity_status/signature_status/version/preflight_id/
    blocking_reasons); evidence is one human-readable "field changed from
    X to Y" string per dimension. revalidation_required is True when
    there was nothing to compare against yet (previous_trust is None) or
    the fresh validation is not trusted -- False when the snapshot
    remains trusted, whether or not some non-blocking dimension moved.
    """

    task_id: str
    snapshot_id: str
    previous_trust: Optional[object]
    current_trust: object
    changed: bool
    changed_dimensions: tuple
    evidence: tuple
    revalidation_required: bool
    checked_at: datetime


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightDependencySnapshotTrustInvalidationResult:
    """Commit #9's own report of whether task_id's exact snapshot_id
    warranted invalidating its referencing preflight -- never a second
    invalidation framework (Rule: "Do not create another invalidation
    framework"): invalidated, when True via invalidate(), is always the
    direct result of backend.agent_task_recovery_guardrails' own
    LLMAgentTaskRecoveryPreflightInvalidationService.invalidate(), never
    a parallel state machine this class maintains itself.

    warranted is exactly `not current trust` (Commit #8's own
    current_trust.trusted, fresh every call) -- Rule: "Invalidate only
    when a real trust failure/change is detected". invalidated is False
    whenever warranted is False (check()/invalidate() both refuse to
    invalidate a still-trusted snapshot); True whenever the referenced
    preflight is already invalid for any reason (freshly invalidated
    this call, already invalidated on a prior call, or already obsolete/
    superseded -- Rule: "Already-invalidated/obsolete snapshots must
    remain historical and non-actionable").

    affected_preflight_ids/affected_schedule_ids name every downstream
    record this snapshot's loss of trust touches (Rule: "Identify
    affected preflights/schedules referencing that snapshot") --
    affected_schedule_ids is only ever populated when a scheduling_service
    was configured, () otherwise, never fabricated. evidence is Commit
    #8's own change.evidence (or, lacking any dimension diff, the fresh
    trust result's own blocking_reasons) -- never re-derived.
    """

    task_id: str
    snapshot_id: str
    preflight_id: Optional[str]
    warranted: bool
    invalidated: bool
    reason: Optional[str]
    affected_preflight_ids: tuple
    affected_schedule_ids: tuple
    evidence: tuple
    checked_at: datetime


# Commit #10's own outcome vocabulary for revalidate(). REUSED: an
# already-trusted snapshot (the exact one asked about, or a later one a
# PRIOR revalidate() call already produced) was returned unchanged, no
# new snapshot minted. REPLACED: the old snapshot was untrusted, and a
# freshly created snapshot passed its own trust validation. FAILED: a
# fresh snapshot was created, but it ALSO failed trust -- reported
# honestly, never retried in a loop or fabricated as trusted. MISSING:
# old_snapshot_id does not exist for task_id at all.
REUSED = "reused"
REPLACED = "replaced"
REVALIDATION_FAILED = "failed"
REVALIDATION_MISSING = "missing"
REVALIDATION_ACTIONS = frozenset({REUSED, REPLACED, REVALIDATION_FAILED, REVALIDATION_MISSING})


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightDependencySnapshotTrustRevalidationResult:
    """LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRevalidationService.
    revalidate()'s complete report -- never a second snapshot/trust
    pipeline (Rule: "Do not duplicate any of those mechanisms"):
    old_trust/new_trust are exactly Commit #6's own
    AgentTaskRecoveryPreflightDependencySnapshotTrustResult objects,
    carried through unchanged. new_snapshot_id equals old_snapshot_id
    exactly when action is REUSED (Rule: "return the existing trusted
    snapshot" -- never a copy); it is a genuinely new Commit #1
    snapshot_id for REPLACED/REVALIDATION_FAILED, and None only for
    REVALIDATION_MISSING."""

    task_id: str
    preflight_id: Optional[str]
    old_snapshot_id: str
    new_snapshot_id: Optional[str]
    action: str
    old_trust: Optional[object]
    new_trust: Optional[object]
    revalidated_at: datetime


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryAuditRecord:
    """Commit #11's own durable, append-only capture of one Commit #10
    AgentTaskRecoveryPreflightDependencySnapshotTrustRevalidationResult --
    every field is that result's own evidence (old_trust/new_trust
    flattened into their own trusted/integrity_status/signature_status),
    preserved verbatim, never re-derived. audit_id/recorded_at are this
    record's own bookkeeping (the underlying backend.agent_task_events
    event's own event_id/occurred_at); revalidated_at is the ORIGINAL
    revalidation_result's own timestamp, kept distinct from recorded_at."""

    task_id: str
    preflight_id: Optional[str]
    old_snapshot_id: str
    new_snapshot_id: Optional[str]
    version: Optional[int]
    action: str
    old_trusted: Optional[bool]
    old_integrity_status: Optional[str]
    old_signature_status: Optional[str]
    new_trusted: Optional[bool]
    new_integrity_status: Optional[str]
    new_signature_status: Optional[str]
    reason: Optional[str]
    revalidated_at: Optional[datetime]
    recorded_at: datetime
    audit_id: str


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryReconciliationResult:
    """Commit #12's own report of propagating a #10-produced replacement
    snapshot into its consumers -- never a second snapshot/trust system
    (Rule: "Do not create another snapshot/trust system"): every write
    here is delegated to an existing optional collaborator (guardrails'
    own preflight revalidation, schedule_dependencies' own schedule
    reconciliation); this class only decides WHICH consumers are safe to
    touch.

    reconciled is exactly `not reasons` blocking anything (True even when
    there was simply nothing to do). updated_references names every
    preflight_id/schedule_id this call actually caused a downstream
    revalidation/reconciliation call for; skipped_conflicts names every
    one deliberately left untouched (a newer replacement already exists,
    or the given new_snapshot_id itself was not trusted) -- Rule: "Detect
    conflicting/current replacements rather than blindly overwriting
    references".
    """

    task_id: str
    preflight_id: Optional[str]
    old_snapshot_id: str
    new_snapshot_id: str
    reconciled: bool
    affected_preflight_ids: tuple
    affected_schedule_ids: tuple
    updated_references: tuple
    skipped_conflicts: tuple
    reasons: tuple
    reconciled_at: datetime


NO_OP = "no_op"


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryOrchestrationResult:
    """Commit #13's own single, composed report closing the trust
    lifecycle: detect (#8) -> invalidate (#9) -> revalidate (#10) ->
    audit (#11) -> reconcile (#12) -- never a second workflow engine
    (Rule: "Do not introduce generic orchestration infrastructure"):
    every field below is exactly what the ONE existing service owning
    that step already produced, never re-derived.

    action is NO_OP when the snapshot was already trusted (nothing else
    ran); otherwise Commit #10's own action (REPLACED/REVALIDATION_FAILED/
    REVALIDATION_MISSING) -- reconciliation is only ever attempted when
    action is REPLACED (Rule: "Fail closed if replacement trust
    validation fails"), so `reconciliation` stays None for every other
    action. partial_failure is populated only when a collaborator raised
    unexpectedly during the reconcile step (Rule: "Handle partial
    failures explicitly") -- never for an ordinary, structured refusal
    (which is instead expressed the normal way, in that step's own
    result)."""

    task_id: str
    old_snapshot_id: str
    new_snapshot_id: Optional[str]
    trusted: bool
    action: str
    change: object
    invalidation: Optional[object]
    revalidation: Optional[object]
    audit_record: Optional[object]
    reconciliation: Optional[object]
    partial_failure: Optional[str]
    recovered_at: datetime


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightDependencyImpactCacheEntry:
    """One cached dependency-impact result, bound to the exact
    (task_id, preflight_id, snapshot_id, version) it was computed for --
    `result` is an AgentTaskRecoveryPreflightDependencySnapshotReconciliation
    carried through unchanged, never a re-derived copy. `version` is the
    result's own version (None only when no version service was
    configured when it was computed)."""

    task_id: str
    preflight_id: str
    snapshot_id: str
    version: Optional[int]
    result: object
    cached_at: datetime


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightDependencyImpactCacheInvalidation:
    """invalidate()'s own report. `invalidated` is True only when an entry
    was actually removed by THIS call -- a repeated invalidate() (or one
    for a never-cached preflight) reports False, never an error."""

    task_id: str
    preflight_id: str
    invalidated: bool
    reason: Optional[str]
    invalidated_at: datetime


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightDependencyImpactCacheInvalidationOutcome:
    """One cached entry an invalidation pass judged affected, with the
    exact identity it was bound to and every reason it was judged stale.
    `invalidated` is True only when THIS pass actually removed the entry
    (False if it was already gone by then)."""

    preflight_id: str
    snapshot_id: str
    version: Optional[int]
    invalidated: bool
    reasons: tuple


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightDependencyImpactCacheInvalidationResult:
    """The complete report of one invalidation pass over task_id's cached
    impact entries. `trigger` is which operation ran (dependency/
    preflight/snapshot/reconcile) and `subject_id` the changed entity it
    was given (None for reconcile). `affected` holds only entries judged
    stale; `retained_preflight_ids` names every entry left intact, so an
    unrelated change is visibly a no-op. A repeated pass over unchanged
    state reports no affected entries and changes nothing."""

    task_id: str
    trigger: str
    subject_id: Optional[str]
    affected: tuple
    retained_preflight_ids: tuple
    invalidated_count: int
    checked_at: datetime


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightDependencyImpactCacheWarmResult:
    """warm()'s report for one preflight. `status` is one of WARMED (a
    fresh impact result was stored), ALREADY_CURRENT (a valid entry was
    kept, or a newer one won), SKIPPED (the preflight is not eligible --
    `reasons` says why, and nothing was analysed or written) or NOT_CACHED
    (analysis ran but its result could not be cached). `replaced` is True
    only when a WARMED result took the place of an existing, stale entry.
    `impact_status` is the stored reconciliation's own status
    (unchanged/changed/indeterminate) when analysis ran."""

    task_id: str
    preflight_id: str
    status: str
    snapshot_id: Optional[str]
    version: Optional[int]
    replaced: bool
    impact_status: Optional[str]
    reasons: tuple
    warmed_at: datetime


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightDependencyImpactCacheWarmSummary:
    """warm_active()'s report: one warm result per processed preflight,
    newest first, plus the preflights excluded outright (explicitly
    invalidated, so never processed at all)."""

    task_id: str
    results: tuple
    warmed_count: int
    already_current_count: int
    skipped_count: int
    not_cached_count: int
    excluded_preflight_ids: tuple
    warmed_at: datetime


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightDependencyImpactCacheMetrics:
    """summary()'s aggregate of one task's recorded cache activity, every
    figure a plain count over recorded events -- never an estimate.

    lookups is hits + misses. hit_rate/miss_rate/warm_success_rate are
    count / total as a float, 0.0 when the total is zero -- the same
    convention backend.agent_policy_metrics' own denial_rate uses.
    stale_misses is the subset of misses whose reason was "stale" (an
    entry existed but its snapshot/version was no longer current);
    miss_reasons breaks every miss down by its recorded reason.
    warm_attempts counts warmings that actually did work (a result stored
    or a failure); warm_failures = warm_attempts - warm_successes.
    computations_avoided counts cached results a caller actually
    consumed INSTEAD of running a fresh impact analysis -- not merely
    hits, since a hit can still be discarded (e.g. it belongs to a newer
    snapshot than the one asked about)."""

    task_id: str
    hits: int
    misses: int
    lookups: int
    hit_rate: float
    miss_rate: float
    stale_misses: int
    miss_reasons: dict
    invalidations: int
    warm_attempts: int
    warm_successes: int
    warm_failures: int
    warm_success_rate: float
    computations_avoided: int
    generated_at: datetime


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightDependencyImpactCacheEvictionCandidate:
    """One cache entry the eviction plan proposes to remove, identified
    by the exact (task_id, preflight_id, snapshot_id, version) it holds,
    with every reason it qualified."""

    task_id: str
    preflight_id: str
    snapshot_id: str
    version: Optional[int]
    cached_at: datetime
    reasons: tuple


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightDependencyImpactCacheEvictionProtection:
    """One cache entry that was kept, and the concrete reason why -- the
    evidence, not a bare tally, that an entry was deliberately spared."""

    task_id: str
    preflight_id: str
    snapshot_id: str
    version: Optional[int]
    reason: str


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightDependencyImpactCacheEvictionPlan:
    """plan()'s read-only proposal for one task. `before` is the
    retention cutoff actually used (always concrete, never "the default"):
    an entry cached at or before it is older than the retention window.
    Every entry currently cached for task_id appears in exactly one of
    `eligible` and `protected`."""

    task_id: str
    before: datetime
    eligible: tuple
    protected: tuple
    planned_at: datetime


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightDependencyImpactCacheEvictionResult:
    """evict()'s outcome for one plan, embedded verbatim. `evicted` is what
    THIS call removed; `already_evicted` is what the plan named that was
    already gone (re-running a plan is never an error); `newly_protected`
    is what evict() re-checked at apply time and spared because it had
    become valid, or been replaced by a fresher entry, since planning."""

    plan: AgentTaskRecoveryPreflightDependencyImpactCacheEvictionPlan
    evicted: tuple
    already_evicted: tuple
    newly_protected: tuple
    evicted_at: datetime


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightDependencyImpactCacheConsistencyViolation:
    """One concrete disagreement between a cached entry (or its absence)
    and the source it should reflect, anchored to one preflight_id.
    `category` is one of the CONSISTENCY_CATEGORIES; snapshot_id/version
    are the entry's own when one exists, else the current source's."""

    preflight_id: str
    snapshot_id: Optional[str]
    version: Optional[int]
    category: str
    reason: str


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightDependencyImpactCacheConsistencyResult:
    """check()'s complete, read-only outcome. is_consistent is exactly
    `not violations` (the convention every consistency result in this
    repository uses); `checked_preflight_ids` names everything examined,
    so an empty result is distinguishable from an unexamined one."""

    task_id: str
    preflight_id: Optional[str]
    is_consistent: bool
    violations: tuple
    checked_preflight_ids: tuple
    deep: bool
    checked_at: datetime


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightDependencyImpactCacheRepairAction:
    """What repair() did (or declined to do) for one preflight: `action`
    is one of RECOMPUTED, REMOVED, KEPT_NEWER, UNREPAIRABLE."""

    preflight_id: str
    categories: tuple
    action: str
    reason: str


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightDependencyImpactCacheRepairResult:
    """repair()'s outcome: the check it acted on, every action taken, and
    a fresh re-check. is_consistent is that re-check's verdict, so a
    repair that could not fix something (e.g. untrusted) says so."""

    task_id: str
    preflight_id: Optional[str]
    before: AgentTaskRecoveryPreflightDependencyImpactCacheConsistencyResult
    actions: tuple
    after: AgentTaskRecoveryPreflightDependencyImpactCacheConsistencyResult
    repaired_count: int
    is_consistent: bool
    repaired_at: datetime


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightDependencyImpactCacheRefreshResult:
    """refresh()'s report for one preflight. `status` is one of REFRESHED
    (a fresh result was stored), CURRENT (already consistent; nothing
    done), NOT_TRUSTED (trust in the latest snapshot cannot be
    established; nothing changed), NEWER_ENTRY (a newer entry was kept)
    or NOT_REFRESHED (nothing to refresh from, or no result could be
    stored). `categories` are the consistency violations that prompted a
    refresh; `result` is the reconciliation now cached, only when
    REFRESHED."""

    task_id: str
    preflight_id: str
    status: str
    snapshot_id: Optional[str]
    version: Optional[int]
    categories: tuple
    reasons: tuple
    result: Optional[object]
    refreshed_at: datetime


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightDependencyImpactCacheRefreshSummary:
    """refresh_stale()'s report: one refresh result per INCONSISTENT
    preflight (consistent ones are left alone and only counted)."""

    task_id: str
    results: tuple
    checked_count: int
    consistent_count: int
    refreshed_count: int
    not_trusted_count: int
    newer_entry_count: int
    not_refreshed_count: int
    refreshed_at: datetime


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightDependencyImpactCachePrecomputeOutcome:
    """One preflight's precompute outcome: `status` is SKIPPED (not
    eligible, or already current/consistent, or a newer entry kept),
    REFRESHED (its entry was rebuilt) or FAILED (the rebuild could not
    complete). `refresh_status` is the refresh service's own verdict when
    it ran, so nothing it said is lost; `reasons` explains the status."""

    preflight_id: str
    status: str
    snapshot_id: Optional[str]
    version: Optional[int]
    refresh_status: Optional[str]
    reasons: tuple


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightDependencyImpactCachePrecomputeResult:
    """precompute()'s report: one outcome per requested preflight, in the
    order processed, plus the counts. `excluded_preflight_ids` lists the
    explicitly invalidated preflights an active run never considered."""

    task_id: str
    outcomes: tuple
    refreshed_count: int
    skipped_count: int
    failed_count: int
    excluded_preflight_ids: tuple
    precomputed_at: datetime


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightDependencyImpactCacheBatchOutcome:
    """One preflight's batch-reconciliation outcome. `status` is CONSISTENT
    (its cached impact already matches the trusted snapshot, or a newer
    entry was kept), REFRESHED (rebuilt), INVALIDATED (an obsolete entry
    was removed) or UNAVAILABLE (nothing could be established or built:
    untrusted or missing evidence, or a failure -- `reasons` says which,
    and the cache was left as it was). `refresh_status` is the refresh
    service's own verdict when it ran."""

    preflight_id: str
    status: str
    snapshot_id: Optional[str]
    version: Optional[int]
    refresh_status: Optional[str]
    categories: tuple
    reasons: tuple


@dataclass(frozen=True)
class AgentTaskRecoveryPreflightDependencyImpactCacheBatchResult:
    """reconcile()'s report: one outcome per preflight processed plus
    aggregate counts (consistent + refreshed + invalidated + unavailable
    == total). `excluded_preflight_ids` lists the explicitly invalidated
    preflights an active run never considered."""

    task_id: str
    outcomes: tuple
    total: int
    consistent_count: int
    refreshed_count: int
    invalidated_count: int
    unavailable_count: int
    excluded_preflight_ids: tuple
    reconciled_at: datetime

