from backend.agent_task_recovery_execution_precondition_snapshots import models as m


def test_serialized_status_values_are_stable():
    assert (m.EXECUTION_DECISION_ALLOW, m.EXECUTION_DECISION_REVIEW, m.EXECUTION_DECISION_BLOCK) == (
        "allow",
        "review",
        "block",
    )
    assert (m.FRESHNESS_FRESH, m.FRESHNESS_STALE, m.FRESHNESS_UNKNOWN) == ("fresh", "stale", "unknown")
    assert (m.IMPACT_PLAN_VALIDATION_VALID, m.IMPACT_PLAN_VALIDATION_INVALID) == ("valid", "invalid")
    assert (m.IMPACT_INVALIDATION_VERIFICATION_VALID, m.IMPACT_INVALIDATION_VERIFICATION_INVALID) == (
        "valid",
        "invalid",
    )


def test_artifact_status_matches_freshness_status():
    assert m.ARTIFACT_FRESH == m.FRESHNESS_FRESH
    assert m.ARTIFACT_STALE == m.FRESHNESS_STALE
    assert m.ARTIFACT_UNKNOWN == m.FRESHNESS_UNKNOWN


def test_lifecycle_status_values_are_distinct_strings():
    values = [getattr(m, n) for n in dir(m) if n.startswith("IMPACT_LIFECYCLE_") and n.isupper()]
    values = [v for v in values if isinstance(v, str)]
    assert len(values) == len(set(values))
