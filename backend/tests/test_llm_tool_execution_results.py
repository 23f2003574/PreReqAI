import dataclasses
import json
from datetime import datetime, timezone

import pytest

from backend.llm.context import LLMContextService, estimate_text_tokens
from backend.llm.tool_execution import (
    DENIED,
    FAILED,
    LLMToolExecution,
    REJECTED,
    SUCCEEDED,
)
from backend.llm.tool_results import (
    DEFAULT_OUTPUT_TOKEN_BUDGET,
    MINIMUM_OUTPUT_TOKEN_BUDGET,
    InvalidToolResultError,
    LLMToolResult,
    LLMToolResultService,
    TOOL_ROLE,
)

NOW = datetime(2026, 8, 27, 12, 0, 0, tzinfo=timezone.utc)
LATER = datetime(2026, 8, 27, 12, 0, 1, tzinfo=timezone.utc)


def execution(status=SUCCEEDED, result=None, error=None, **overrides):
    fields = {
        "execution_id": "tool-execution-1",
        "plan_id": "tool-plan-summarize_notebook_analysis-1",
        "tool_name": "summarize_notebook_analysis",
        "status": status,
        "result": result,
        "error": error,
        "started_at": NOW,
        "completed_at": LATER,
    }
    fields.update(overrides)
    return LLMToolExecution(**fields)


# ---------------------------------------------------------------------------
# normalize()
# ---------------------------------------------------------------------------


def test_successful_normalization_preserves_output():
    """The real shape LLMNotebookAnalysisService.summary returns."""
    service = LLMToolResultService()
    summary = {"cell_count": 3, "code_cell_count": 2, "markdown_cell_count": 1}

    result = service.normalize(execution(result=summary))

    assert result.execution_id == "tool-execution-1"
    assert result.status == SUCCEEDED
    assert result.output == summary
    assert result.error is None
    assert result.completed_at == LATER
    assert result.metadata["tool_name"] == "summarize_notebook_analysis"
    assert result.metadata["plan_id"] == "tool-plan-summarize_notebook_analysis-1"
    assert result.metadata["truncated"] is False
    assert result.metadata["estimated_tokens"] > 0


def test_normalization_uses_the_projects_serialization_convention():
    """Dataclasses via asdict, datetimes via isoformat, tuples/sets as lists."""
    service = LLMToolResultService()

    @dataclasses.dataclass
    class Finding:
        name: str
        at: datetime

    result = service.normalize(
        execution(
            result={
                "findings": [Finding(name="add", at=NOW)],
                "names": ("a", "b"),
                "count": 2,
                "ok": True,
                "missing": None,
            }
        )
    )

    assert result.output == {
        "findings": [{"name": "add", "at": NOW.isoformat()}],
        "names": ["a", "b"],
        "count": 2,
        "ok": True,
        "missing": None,
    }
    # And the whole thing round-trips through the project's JSON convention.
    assert json.loads(json.dumps(result.output, sort_keys=True)) == result.output


def test_non_serializable_output_is_rendered_as_text():
    service = LLMToolResultService()

    class Opaque:
        def __str__(self):
            return "<opaque analysis handle>"

    result = service.normalize(execution(result={"handle": Opaque()}))

    assert result.output == {"handle": "<opaque analysis handle>"}
    assert service.validate(result) is True


@pytest.mark.parametrize("status", [FAILED, DENIED, REJECTED])
def test_failed_tool_result(status):
    service = LLMToolResultService()

    result = service.normalize(
        execution(status=status, result=None, error="UnknownAnalysisError: analysis-9")
    )

    assert result.status == status
    assert result.output is None
    assert result.error == "UnknownAnalysisError: analysis-9"
    assert result.metadata["truncated"] is False
    assert service.validate(result) is True


def test_failure_without_an_error_still_explains_itself():
    service = LLMToolResultService()

    result = service.normalize(execution(status=DENIED, error=None))

    assert result.error == DENIED
    assert service.validate(result) is True


# ---------------------------------------------------------------------------
# secret redaction
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "secret",
    [
        "sk-abcdefghijklmnopqrst",
        "AKIAIOSFODNN7EXAMPLE",
        "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
        "api_key=hunter2-supersecret",
    ],
)
def test_secret_redaction_in_nested_output(secret):
    service = LLMToolResultService()

    result = service.normalize(
        execution(result={"config": {"credential": secret}, "rows": [secret]})
    )

    assert result.output == {"config": {"credential": "[REDACTED]"}, "rows": ["[REDACTED]"]}
    assert secret not in json.dumps(result.output)
    assert service.validate(result) is True


def test_secret_redaction_in_error_text():
    service = LLMToolResultService()

    result = service.normalize(
        execution(status=FAILED, error="RuntimeError: auth failed with sk-abcdefghijklmnop")
    )

    assert result.error == "[REDACTED]"


def test_secret_redaction_in_dict_keys():
    service = LLMToolResultService()

    result = service.normalize(execution(result={"sk-abcdefghijklmnopqrst": "value"}))

    assert result.output == {"[REDACTED]": "value"}


def test_a_result_carrying_a_secret_cannot_enter_context():
    """validate() is the last line of defence, independent of normalize()."""
    service = LLMToolResultService()
    smuggled = LLMToolResult(
        execution_id="tool-execution-1",
        status=SUCCEEDED,
        output={"credential": "sk-abcdefghijklmnopqrst"},
        error=None,
        metadata={"tool_name": "summarize_notebook_analysis"},
        completed_at=LATER,
    )

    with pytest.raises(InvalidToolResultError, match="credential"):
        service.validate(smuggled)

    with pytest.raises(InvalidToolResultError):
        service.context(smuggled)


# ---------------------------------------------------------------------------
# output limits
# ---------------------------------------------------------------------------


def test_output_limit_handling():
    service = LLMToolResultService(token_budget=50)
    big = {"rows": ["a notebook function summary line" for _ in range(200)]}
    assert estimate_text_tokens(json.dumps(big)) > 50

    result = service.normalize(execution(result=big))

    assert result.status == SUCCEEDED
    assert result.metadata["truncated"] is True
    assert result.metadata["original_estimated_tokens"] > 50
    assert result.metadata["token_budget"] == 50
    assert result.output["truncated"] is True
    # The envelope stays fixed and compact; the numbers live in metadata.
    assert result.output["reason"] == "output exceeds token budget"
    assert result.output["preview"]
    # The trimmed result is itself within budget, so it can enter context.
    assert service.validate(result) is True


def test_output_within_budget_is_not_truncated():
    service = LLMToolResultService(token_budget=DEFAULT_OUTPUT_TOKEN_BUDGET)
    summary = {"cell_count": 3, "code_cell_count": 2}

    result = service.normalize(execution(result=summary))

    assert result.metadata["truncated"] is False
    assert result.output == summary


def test_limit_uses_the_projects_own_token_estimate():
    """Not a second sizing rule -- the same estimator LLMContextService uses."""
    service = LLMToolResultService(token_budget=1000)
    payload = {"text": "x" * 400}

    result = service.normalize(execution(result=payload))

    rendered = json.dumps(result.output, sort_keys=True, indent=2, default=str)
    assert result.metadata["estimated_tokens"] == estimate_text_tokens(rendered)


def test_an_oversized_result_is_refused_by_validate():
    service = LLMToolResultService(token_budget=MINIMUM_OUTPUT_TOKEN_BUDGET)
    oversized = LLMToolResult(
        execution_id="tool-execution-1",
        status=SUCCEEDED,
        output={"rows": ["long line of notebook output" for _ in range(50)]},
        error=None,
        metadata={"tool_name": "summarize_notebook_analysis"},
        completed_at=LATER,
    )

    with pytest.raises(InvalidToolResultError, match="budget"):
        service.validate(oversized)


def test_token_budget_must_be_positive():
    for bad in (0, -1, "100", 1.5, True):
        with pytest.raises(InvalidToolResultError):
            LLMToolResultService(token_budget=bad)


def test_token_budget_below_the_derived_floor_is_refused():
    """Below the floor even a bare truncation notice would not fit, so
    normalize() could emit a result validate() must refuse."""
    with pytest.raises(InvalidToolResultError, match="at least"):
        LLMToolResultService(token_budget=MINIMUM_OUTPUT_TOKEN_BUDGET - 1)


@pytest.mark.parametrize(
    "budget", [MINIMUM_OUTPUT_TOKEN_BUDGET, MINIMUM_OUTPUT_TOKEN_BUDGET + 1, 30, 50]
)
def test_truncation_always_produces_a_result_that_validates(budget):
    """Whatever the budget, normalize() and validate() agree."""
    service = LLMToolResultService(token_budget=budget)
    huge = {"rows": ["a long line of notebook output" * 3 for _ in range(200)]}

    result = service.normalize(execution(result=huge))

    assert result.metadata["truncated"] is True
    assert result.metadata["estimated_tokens"] <= budget
    assert service.validate(result) is True
    service.context(result).validate()


# ---------------------------------------------------------------------------
# malformed results
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides,match",
    [
        ({"execution_id": ""}, "execution_id"),
        ({"status": "MAYBE"}, "status"),
        ({"metadata": "not-a-dict"}, "metadata"),
        ({"status": SUCCEEDED, "error": "boom"}, "no error"),
        ({"status": FAILED, "output": {"a": 1}, "error": "boom"}, "no output"),
        ({"status": FAILED, "output": None, "error": None}, "explain itself"),
        ({"status": FAILED, "output": None, "error": ""}, "explain itself"),
    ],
)
def test_malformed_result_is_refused(overrides, match):
    service = LLMToolResultService()
    fields = {
        "execution_id": "tool-execution-1",
        "status": SUCCEEDED,
        "output": {"cell_count": 3},
        "error": None,
        "metadata": {"tool_name": "summarize_notebook_analysis"},
        "completed_at": LATER,
    }
    fields.update(overrides)
    result = LLMToolResult(**fields)

    with pytest.raises(InvalidToolResultError, match=match):
        service.validate(result)

    with pytest.raises(InvalidToolResultError):
        service.context(result)


def test_validate_rejects_a_non_result():
    service = LLMToolResultService()

    for bad in (None, {"status": SUCCEEDED}, "result", 42):
        with pytest.raises(InvalidToolResultError):
            service.validate(bad)


def test_normalize_rejects_a_non_execution():
    service = LLMToolResultService()

    for bad in (None, {"status": SUCCEEDED}, "execution"):
        with pytest.raises(TypeError):
            service.normalize(bad)


# ---------------------------------------------------------------------------
# context conversion
# ---------------------------------------------------------------------------


def test_context_conversion_returns_the_existing_context_protocol():
    service = LLMToolResultService()
    summary = {"cell_count": 3, "code_cell_count": 2}
    result = service.normalize(execution(result=summary))

    item = service.context(result)

    assert item.type == TOOL_ROLE
    item.validate()  # the existing LLMContextItem contract

    payload = json.loads(item.content)
    assert payload == {
        "execution_id": "tool-execution-1",
        "status": SUCCEEDED,
        "tool": "summarize_notebook_analysis",
        "output": summary,
    }


def test_context_item_flows_through_the_real_context_service():
    service = LLMToolResultService()
    context_service = LLMContextService()
    context_service.create("request-1", system="You may call tools.")
    result = service.normalize(execution(result={"cell_count": 3}))

    added = context_service.add("request-1", service.context(result))
    built = context_service.build("request-1")

    assert added.id == "request-1-item-1"
    assert built["messages"][-1]["role"] == TOOL_ROLE
    assert json.loads(built["messages"][-1]["content"])["output"] == {"cell_count": 3}


def test_context_of_a_failure_carries_the_reason_not_an_output():
    service = LLMToolResultService()
    result = service.normalize(
        execution(status=FAILED, error="UnknownAnalysisError: analysis-9")
    )

    payload = json.loads(service.context(result).content)

    assert payload["status"] == FAILED
    assert payload["error"] == "UnknownAnalysisError: analysis-9"
    assert "output" not in payload


def test_context_flags_truncation_to_the_model():
    service = LLMToolResultService(token_budget=50)
    result = service.normalize(
        execution(result={"rows": ["a long notebook summary line"] * 200})
    )

    payload = json.loads(service.context(result).content)

    assert payload["truncated"] is True
    assert payload["output"]["truncated"] is True


def test_context_priority_is_settable():
    service = LLMToolResultService()
    result = service.normalize(execution(result={"cell_count": 3}))

    assert service.context(result).priority == 0
    assert service.context(result, priority=5).priority == 5


# ---------------------------------------------------------------------------
# no re-execution
# ---------------------------------------------------------------------------


def test_result_processing_never_re_executes_tools():
    """The service holds no registry, permissions, or handlers -- it cannot
    invoke anything, and reads the record only."""
    service = LLMToolResultService()

    for attr in ("invoke", "call", "execute", "run", "dispatch", "bind"):
        assert not hasattr(service, attr)

    record = execution(result={"cell_count": 3})
    before = dataclasses.asdict(record)

    result = service.normalize(record)
    service.validate(result)
    service.context(result)

    assert dataclasses.asdict(record) == before


def test_results_are_immutable():
    service = LLMToolResultService()
    result = service.normalize(execution(result={"cell_count": 3}))

    with pytest.raises(dataclasses.FrozenInstanceError):
        result.status = FAILED
