import pytest

from backend.llm import LLMResponse
from backend.llm.budget import (
    BudgetExceededError,
    LLMBudgetService,
    UnknownBudgetError,
)
from backend.llm.cost import LLMCostService, LLMModelPricing
from backend.llm.usage import LLMUsageService


def test_configure_and_check():
    service = LLMBudgetService()
    budget = service.configure("workspace-1", max_tokens=1000, max_cost=5.0)

    assert budget.scope_id == "workspace-1"
    assert budget.used_tokens == 0
    assert budget.used_cost == 0.0
    assert budget.enabled is True

    assert service.check("workspace-1", estimated_tokens=500, estimated_cost=2.0) is True

    with pytest.raises(UnknownBudgetError):
        service.check("unknown-scope", 1, 1)

    # reuse Commit #6/#7 usage + cost services to derive real check() inputs
    usage_service = LLMUsageService()
    cost_service = LLMCostService(usage_service)
    cost_service.register_pricing(
        LLMModelPricing(provider="openai", model="gpt-4o", input_cost=0.001, output_cost=0.002)
    )
    response = LLMResponse(
        content="hi",
        model="gpt-4o",
        usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        finish_reason="stop",
    )
    usage_record = usage_service.record(response, request_id="req-x", provider="openai")
    estimate = cost_service.estimate("req-x")

    assert (
        service.check(
            "workspace-1",
            estimated_tokens=usage_record.total_tokens,
            estimated_cost=estimate.total_cost,
        )
        is True
    )


def test_token_limit():
    service = LLMBudgetService()
    service.configure("workspace-2", max_tokens=100, max_cost=None)

    service.consume("workspace-2", tokens=90, cost=0.0)

    with pytest.raises(BudgetExceededError):
        service.check("workspace-2", estimated_tokens=20, estimated_cost=0.0)

    assert service.check("workspace-2", estimated_tokens=10, estimated_cost=0.0) is True


def test_cost_limit():
    service = LLMBudgetService()
    service.configure("workspace-3", max_tokens=None, max_cost=1.0)

    service.consume("workspace-3", tokens=0, cost=0.9)

    with pytest.raises(BudgetExceededError):
        service.check("workspace-3", estimated_tokens=0, estimated_cost=0.2)

    assert service.check("workspace-3", estimated_tokens=0, estimated_cost=0.1) is True


def test_consumption():
    service = LLMBudgetService()
    service.configure("workspace-4", max_tokens=100, max_cost=1.0)

    service.consume("workspace-4", tokens=40, cost=0.4)
    budget = service.consume("workspace-4", tokens=30, cost=0.3)

    assert budget.used_tokens == 70
    assert budget.used_cost == pytest.approx(0.7)

    with pytest.raises(BudgetExceededError):
        service.consume("workspace-4", tokens=40, cost=0.0)

    with pytest.raises(BudgetExceededError):
        service.consume("workspace-4", tokens=0, cost=0.5)

    # rejected consumption must not partially apply
    assert budget.used_tokens == 70
    assert budget.used_cost == pytest.approx(0.7)


def test_remaining_budget():
    service = LLMBudgetService()
    service.configure("workspace-5", max_tokens=100, max_cost=2.0)
    service.consume("workspace-5", tokens=40, cost=0.5)

    remaining = service.remaining("workspace-5")
    assert remaining["tokens"] == 60
    assert remaining["cost"] == pytest.approx(1.5)

    service.configure("workspace-6")
    assert service.remaining("workspace-6") == {"tokens": None, "cost": None}


def test_reset_and_disable():
    service = LLMBudgetService()
    service.configure("workspace-7", max_tokens=50, max_cost=1.0)
    service.consume("workspace-7", tokens=50, cost=1.0)

    with pytest.raises(BudgetExceededError):
        service.check("workspace-7", estimated_tokens=1, estimated_cost=0.0)

    reset_budget = service.reset("workspace-7")
    assert reset_budget.used_tokens == 0
    assert reset_budget.used_cost == 0.0
    assert service.check("workspace-7", estimated_tokens=50, estimated_cost=1.0) is True

    service.consume("workspace-7", tokens=50, cost=1.0)
    service.configure("workspace-7", max_tokens=50, max_cost=1.0, enabled=False)

    assert service.check("workspace-7", estimated_tokens=1000, estimated_cost=100.0) is True
    consumed = service.consume("workspace-7", tokens=1000, cost=100.0)
    assert consumed.used_tokens == 1050
    assert consumed.used_cost == pytest.approx(101.0)
