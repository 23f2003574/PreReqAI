from datetime import (
    datetime,
    timedelta,
    timezone,
)

from types import (
    SimpleNamespace,
)

import pytest

from backend.session import (
    ExecutionFairSchedulingError as Error,
    ExecutionFairSchedulingService,
    ExecutionSchedulingCredit,
)


class _FakeJobProvider:
    def __init__(self, jobs_by_scope=None):
        self._jobs_by_scope = jobs_by_scope or {}

    def queued(self, scope_id):
        return self._jobs_by_scope.get(scope_id, [])

    def set_queued(self, scope_id, jobs):
        self._jobs_by_scope[scope_id] = jobs


def _job(job_id, priority="NORMAL", waited_seconds=0):
    queued_at = datetime.now(timezone.utc) - timedelta(seconds=waited_seconds)
    return SimpleNamespace(job_id=job_id, priority=priority, queued_at=queued_at)


def _build():
    provider = _FakeJobProvider()
    return provider, ExecutionFairSchedulingService(provider)


class TestExecutionFairSchedulingService:
    def test_priority_selection(self):
        provider, service = _build()
        provider.set_queued("scope-1", [_job("job-low", "LOW"), _job("job-high", "HIGH")])

        assert service.eligible("scope-1") == ("job-high", "job-low")
        assert service.select("scope-1") == "job-high"

    def test_waiting_job_promotion(self):
        provider, service = _build()
        provider.set_queued(
            "scope-1",
            [
                _job("job-old-low", "LOW", waited_seconds=400),
                _job("job-fresh-high", "HIGH", waited_seconds=0),
            ],
        )

        assert service.eligible("scope-1") == ("job-old-low", "job-fresh-high")

    def test_starvation_prevention(self):
        provider, service = _build()
        provider.set_queued(
            "scope-1",
            [
                _job("job-fresh-critical", "CRITICAL", waited_seconds=0),
                _job("job-ancient-normal", "NORMAL", waited_seconds=100_000),
            ],
        )

        assert service.select("scope-1") == "job-ancient-normal"

    def test_credit_consumption_demotes_a_job(self):
        provider, service = _build()
        provider.set_queued("scope-1", [_job("job-1", "NORMAL"), _job("job-2", "NORMAL")])

        assert service.select("scope-1") == "job-1"

        service.consume("job-1", 10)

        assert service.select("scope-1") == "job-2"

    def test_rebalance_eases_consumed_credit(self):
        provider, service = _build()
        provider.set_queued("scope-1", [_job("job-1", "NORMAL")])
        service.consume("job-1", 10)

        rebalanced = service.rebalance("scope-1")

        assert len(rebalanced) == 1
        credit = rebalanced[0]
        assert isinstance(credit, ExecutionSchedulingCredit)
        assert credit.job_id == "job-1"
        assert credit.consumed == 5

    def test_rebalance_skips_jobs_with_no_consumed_credit(self):
        provider, service = _build()
        provider.set_queued("scope-1", [_job("job-1", "NORMAL")])

        assert service.rebalance("scope-1") == ()

    def test_deterministic_ordering(self):
        provider, service = _build()
        now = datetime.now(timezone.utc)
        provider.set_queued(
            "scope-1",
            [
                SimpleNamespace(job_id="job-b", priority="NORMAL", queued_at=now),
                SimpleNamespace(job_id="job-a", priority="NORMAL", queued_at=now),
            ],
        )

        first = service.eligible("scope-1")
        second = service.eligible("scope-1")

        assert first == ("job-a", "job-b")
        assert second == first

    def test_eligible_on_empty_scope_is_empty(self):
        _, service = _build()

        assert service.eligible("scope-1") == ()
        assert service.select("scope-1") is None

    def test_consume_returns_the_credit_record(self):
        _, service = _build()

        credit = service.consume("job-1", 3)

        assert isinstance(credit, ExecutionSchedulingCredit)
        assert credit.job_id == "job-1"
        assert credit.consumed == 3

    def test_consume_non_positive_amount_is_rejected(self):
        _, service = _build()

        with pytest.raises(Error):
            service.consume("job-1", 0)

    def test_blank_scope_id_is_rejected(self):
        _, service = _build()

        with pytest.raises(Error):
            service.eligible("")
