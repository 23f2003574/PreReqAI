from backend.llm.budget import LLMBudgetService
from backend.llm.budget_analytics import LLMBudgetAnalyticsService
from backend.llm.cost import LLMCostService, LLMModelPricing
from backend.llm.cost_analytics import LLMCostAnalyticsService
from backend.llm.models import LLMResponse
from backend.llm.usage import LLMUsageService
from backend.llm.usage_aggregation import LLMUsageAggregationService


def build_env():
    budget_service = LLMBudgetService()
    usage_service = LLMUsageService()
    cost_service = LLMCostService(usage_service)
    usage_analytics = LLMUsageAggregationService(usage_service)
    cost_analytics = LLMCostAnalyticsService(usage_service, cost_service)
    analytics = LLMBudgetAnalyticsService(budget_service, usage_analytics, cost_analytics)
    return budget_service, usage_service, cost_service, analytics


def test_token_utilization():
    budget_service, _, _, analytics = build_env()
    budget_service.configure("workspace-1", max_tokens=1000)
    budget_service.consume("workspace-1", tokens=250)

    assert analytics.utilization("workspace-1")["tokens"] == 0.25


def test_cost_utilization():
    budget_service, _, _, analytics = build_env()
    budget_service.configure("workspace-1", max_cost=10.0)
    budget_service.consume("workspace-1", cost=2.5)

    assert analytics.utilization("workspace-1")["cost"] == 0.25


def test_remaining_budget():
    budget_service, _, _, analytics = build_env()
    budget_service.configure("workspace-1", max_tokens=1000, max_cost=10.0)
    budget_service.consume("workspace-1", tokens=300, cost=4.0)

    remaining = analytics.remaining("workspace-1")

    assert remaining == {
        "tokens": 700,
        "cost": 6.0,
        "over_budget_tokens": False,
        "over_budget_cost": False,
    }


def test_over_budget_state():
    budget_service, _, _, analytics = build_env()
    # enabled=False lets consume() accumulate past the limit without raising,
    # simulating an over-budget scope for reporting purposes.
    budget_service.configure("workspace-1", max_tokens=100, max_cost=1.0, enabled=False)
    budget_service.consume("workspace-1", tokens=150, cost=1.5)

    remaining = analytics.remaining("workspace-1")
    assert remaining["tokens"] == -50
    assert remaining["cost"] == -0.5
    assert remaining["over_budget_tokens"] is True
    assert remaining["over_budget_cost"] is True

    utilization = analytics.utilization("workspace-1")
    assert utilization["tokens"] == 1.5
    assert utilization["cost"] == 1.5
    assert utilization["over_budget"] is True


def test_provider_model_breakdown():
    budget_service, usage_service, cost_service, analytics = build_env()
    cost_service.register_pricing(
        LLMModelPricing(provider="openai", model="gpt-4o", input_cost=0.01, output_cost=0.02)
    )
    budget_service.configure("workspace-1", max_tokens=1000, max_cost=10.0)

    usage_record = usage_service.record(
        LLMResponse(content="ok", model="gpt-4o", usage={"input_tokens": 100, "output_tokens": 50}),
        request_id="workspace-1",
        provider="openai",
    )
    estimate = cost_service.estimate("workspace-1")
    budget_service.consume("workspace-1", tokens=usage_record.total_tokens, cost=estimate.total_cost)

    by_provider = analytics.by_provider("workspace-1")
    assert by_provider["usage"]["openai"]["total_tokens"] == 150
    assert by_provider["cost"]["openai"]["by_currency"] == {"USD": 2.0}

    by_model = analytics.by_model("workspace-1")
    assert by_model["usage"]["gpt-4o"]["total_tokens"] == 150
    assert by_model["cost"]["gpt-4o"]["by_currency"] == {"USD": 2.0}


def test_empty_usage():
    budget_service, _, _, analytics = build_env()
    budget_service.configure("workspace-1", max_tokens=1000, max_cost=10.0)

    assert analytics.usage("workspace-1") == {"used_tokens": 0, "max_tokens": 1000}
    assert analytics.cost("workspace-1") == {"used_cost": 0.0, "max_cost": 10.0}
    assert analytics.remaining("workspace-1") == {
        "tokens": 1000,
        "cost": 10.0,
        "over_budget_tokens": False,
        "over_budget_cost": False,
    }
    assert analytics.utilization("workspace-1") == {"tokens": 0.0, "cost": 0.0, "over_budget": False}


def test_scope_isolation():
    budget_service, _, _, analytics = build_env()
    budget_service.configure("workspace-1", max_tokens=1000)
    budget_service.consume("workspace-1", tokens=500)
    budget_service.configure("workspace-2", max_tokens=200)
    budget_service.consume("workspace-2", tokens=50)

    assert analytics.usage("workspace-1") == {"used_tokens": 500, "max_tokens": 1000}
    assert analytics.usage("workspace-2") == {"used_tokens": 50, "max_tokens": 200}
    assert analytics.utilization("workspace-1")["tokens"] == 0.5
    assert analytics.utilization("workspace-2")["tokens"] == 0.25
