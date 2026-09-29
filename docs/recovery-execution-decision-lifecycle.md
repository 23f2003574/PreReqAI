# Recovery Execution Decision Lifecycle

## Purpose

Decides whether a recovery execution may proceed, and keeps downstream artifacts consistent when that decision is superseded. Code lives in `backend/agent_task_recovery_execution_precondition_snapshots/`.

## Entry Points

There is no CLI, HTTP endpoint or `evaluate` command for this lifecycle. It is a Python service layer; callers construct and call the services directly.

| Service | Call | Returns |
| --- | --- | --- |
| `LLMAgentTaskRecoveryExecutionPreconditionDecisionService` | `decide(task_id, snapshot_id, authorization_id=None)` | decision record |
| same | `is_allowed(task_id, snapshot_id, authorization_id=None)` | `bool` |
| `LLMAgentTaskRecoveryExecutionDecisionStalenessService` | `check(task_id, decision_id)` | staleness result |
| `LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionLifecycleService` | `resolve(task_id)` | resolution lifecycle result |
| `LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleService` | `run(task_id)` | lifecycle result |

## Decision States

`decide()` composes validation, drift, revalidation and approval reconciliation, and returns one of:

- `allow` — execution may proceed.
- `review` — material drift or a changed approval state needs human review before proceeding.
- `block` — must not proceed. An unresolvable `snapshot_id` is reported as `block`, not raised (fail closed).

`is_allowed()` is `True` only for `allow`. A failure to persist the decision propagates as an error instead of returning `allow`. A blank `task_id`/`snapshot_id` raises `InvalidAgentTaskRecoveryExecutionPreconditionDecisionError`.

## Stale Decisions

`check(task_id, decision_id)` reports whether a stored decision is still `fresh`, `stale` or `unknown` (`FRESHNESS_*` in `models.py`). A decision that fails its integrity check or is missing is not treated as fresh. Blank ids raise `InvalidAgentTaskRecoveryExecutionDecisionStalenessError`.

## Artifact Invalidation and Reconciliation

`ImpactInvalidationLifecycleService.run(task_id)` takes the authoritative decision and its lineage predecessor, then sequences: resolve decision, change impact, staleness, plan, plan validation, safe remediation, audit, verification. It never runs recovery itself. It is idempotent: an already-remediated change returns `up_to_date`.

Result `status` (`IMPACT_LIFECYCLE_*`):

| Status | Meaning |
| --- | --- |
| `clean` | nothing to remediate (including no predecessor decision) |
| `up_to_date` | already remediated by an earlier verified operation |
| `remediated` | remediation applied and verified |
| `blocked` | verification reports blocking issues (e.g. `manual_review` items) |
| `unsafe` | verification failed or found mismatches |
| `unresolved` | the authoritative decision could not be resolved |
| `validation_failed` | the plan was rejected before execution |
| `execution_failed` | execution or audit recording failed |

Expected outcomes (`blocked`, `unsafe`, `validation_failed`) are returned as statuses. Failures of a collaborator are captured in the result's `errors`. Persisting results (`...LifecycleResultService.record`) wraps store errors in the module error with the original exception as `__cause__`.

## Minimal Example

```python
from backend.agent_task_recovery_execution_precondition_snapshots import (
    LLMAgentTaskRecoveryExecutionPreconditionDecisionService,
)

decision = LLMAgentTaskRecoveryExecutionPreconditionDecisionService(...).decide("task-1", "snapshot-1")
print(decision.decision, decision.reason)
```

Constructor collaborators are the snapshot/validation/drift/revalidation/reconciliation services; see the class docstrings.
