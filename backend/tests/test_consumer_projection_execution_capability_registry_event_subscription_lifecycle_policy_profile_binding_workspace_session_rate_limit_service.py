import time

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRateLimit as RateLimit,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRateLimitError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRateLimitResult as Result,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRateLimitService as RateLimitService,
)


def _limit(operation="START", max_requests=2, window_seconds=3600):
    return RateLimit(limit_id="limit-1", operation=operation, max_requests=max_requests, window_seconds=window_seconds)


class TestWorkspaceSessionRateLimitService:
    def test_allowed_request(self):
        service = RateLimitService(limits=[_limit()])

        preview = service.check("session-1", "START")
        assert isinstance(preview, Result)
        assert preview.allowed is True
        assert preview.remaining == 2

        result = service.record("session-1", "START")
        assert result.allowed is True
        assert result.remaining == 1

    def test_limit_exceeded(self):
        service = RateLimitService(limits=[_limit(max_requests=1)])

        first = service.record("session-1", "START")
        assert first.allowed is True

        second = service.record("session-1", "START")
        assert second.allowed is False
        assert second.remaining == 0

        preview = service.check("session-1", "START")
        assert preview.allowed is False

        with pytest.raises(Error):
            service.record("session-1", "not-a-real-operation")

    def test_window_reset(self):
        service = RateLimitService(limits=[_limit(max_requests=1, window_seconds=0.05)])

        first = service.record("session-1", "START")
        assert first.allowed is True

        denied = service.record("session-1", "START")
        assert denied.allowed is False

        time.sleep(0.1)

        # the sliding window has elapsed: the earlier request has aged out
        after_window = service.record("session-1", "START")
        assert after_window.allowed is True

    def test_remaining_quota(self):
        service = RateLimitService(limits=[_limit(max_requests=3)])

        assert service.remaining("session-1", "START") == 3

        service.record("session-1", "START")
        assert service.remaining("session-1", "START") == 2

        service.record("session-1", "START")
        service.record("session-1", "START")
        assert service.remaining("session-1", "START") == 0

        with pytest.raises(Error):
            service.remaining("   ", "START")

    def test_independent_session_counters(self):
        service = RateLimitService(limits=[_limit(max_requests=1)])

        first_session = service.record("session-1", "START")
        second_session = service.record("session-2", "START")

        assert first_session.allowed is True
        assert second_session.allowed is True

        # session-1 is now exhausted, but session-2's quota is untouched
        assert service.record("session-1", "START").allowed is False
        assert service.remaining("session-2", "START") == 0

    def test_reset_counters(self):
        service = RateLimitService(limits=[_limit(operation="START", max_requests=1), _limit(operation="CANCEL", max_requests=1)])

        service.record("session-1", "START")
        service.record("session-1", "CANCEL")

        assert service.remaining("session-1", "START") == 0
        assert service.remaining("session-1", "CANCEL") == 0

        service.reset("session-1")

        assert service.remaining("session-1", "START") == 1
        assert service.remaining("session-1", "CANCEL") == 1

        with pytest.raises(Error):
            service.reset("   ")
