import pytest

from backend.llm import LLMRequest
from backend.llm.context import LLMContext, LLMContextItem, LLMContextService, UnknownContextError


def test_create_and_add():
    service = LLMContextService()

    context = service.create("req-1", system="You are a tutor.", metadata={"user": "abc"})

    assert isinstance(context, LLMContext)
    assert context.request_id == "req-1"
    assert context.system == "You are a tutor."
    assert context.messages == []
    assert context.metadata == {"user": "abc"}

    item = service.add(
        "req-1", LLMContextItem(type="user", content="What is gradient descent?", priority=5)
    )

    assert item.id is not None
    assert context.messages == [item]

    with pytest.raises(ValueError):
        service.create("req-1")

    with pytest.raises(UnknownContextError):
        service.add("missing", LLMContextItem(type="user", content="x", priority=1))


def test_priority_trimming():
    service = LLMContextService()
    service.create("req-2", token_budget=6)

    low = service.add("req-2", LLMContextItem(type="user", content="l" * 10, priority=1))
    med = service.add("req-2", LLMContextItem(type="user", content="m" * 10, priority=5))
    high = service.add("req-2", LLMContextItem(type="user", content="h" * 10, priority=9))

    result = service.build("req-2")
    contents = [message["content"] for message in result["messages"]]

    assert low.content not in contents
    assert med.content in contents
    assert high.content in contents
    assert contents == [med.content, high.content]


def test_token_budget_enforcement():
    service = LLMContextService()
    service.create("req-3", token_budget=8)

    for i in range(5):
        service.add("req-3", LLMContextItem(type="user", content="x" * 20, priority=i))

    raw_estimate = service.estimate_tokens("req-3")
    result = service.build("req-3")

    assert raw_estimate > 8
    assert result["estimated_tokens"] <= 8

    with pytest.raises(ValueError):
        service.create("req-3b", system="s" * 100, token_budget=1)
        service.build("req-3b")


def test_ordering():
    service = LLMContextService()
    service.create("req-4")

    service.add("req-4", LLMContextItem(type="user", content="first", priority=1))
    service.add("req-4", LLMContextItem(type="assistant", content="second", priority=9))
    service.add("req-4", LLMContextItem(type="user", content="third", priority=5))

    result = service.build("req-4")
    contents = [message["content"] for message in result["messages"]]

    assert contents == ["first", "second", "third"]


def test_removal():
    service = LLMContextService()
    service.create("req-5")

    keep = service.add("req-5", LLMContextItem(type="user", content="keep me", priority=1))
    drop = service.add("req-5", LLMContextItem(type="user", content="drop me", priority=1))

    removed = service.remove("req-5", drop.id)
    assert removed is drop

    result = service.build("req-5")
    contents = [message["content"] for message in result["messages"]]
    assert contents == ["keep me"]

    with pytest.raises(KeyError):
        service.remove("req-5", "not-a-real-id")


def test_deterministic_build():
    service = LLMContextService()
    service.create("req-6", system="Be concise.", token_budget=50)

    service.add("req-6", LLMContextItem(type="user", content="Explain backprop.", priority=3))
    service.add("req-6", LLMContextItem(type="assistant", content="Sure, here goes.", priority=2))

    first = service.build("req-6")
    second = service.build("req-6")

    assert first == second

    request = LLMRequest(model="gpt-4o", messages=first["messages"])
    request.validate()
