import dataclasses

import pytest

from backend.llm.context import LLMContextItem, LLMContextService
from backend.llm.templates import (
    DisabledTemplateError,
    InvalidTemplateError,
    LLMPromptTemplateService,
    MissingVariableError,
    UnknownTemplateError,
)


def test_register_and_render():
    service = LLMPromptTemplateService()

    template = service.register(
        "greeting", "Hello {name}, welcome to {platform}.", ["name", "platform"]
    )

    assert template.template_id == "greeting:v1"
    assert template.version == 1
    assert template.enabled is True

    rendered = service.render(
        template.template_id, {"name": "Ada", "platform": "PreReqAI"}
    )
    assert rendered == "Hello Ada, welcome to PreReqAI."


def test_variable_validation():
    service = LLMPromptTemplateService()

    with pytest.raises(InvalidTemplateError):
        service.register("bad", "Hello {name}, {mystery}", ["name"])

    template = service.register("ok", "Hello {name}", ["name", "unused"])
    assert template.variables == ("name", "unused")


def test_missing_variable():
    service = LLMPromptTemplateService()
    template = service.register("greeting", "Hello {name}", ["name"])

    with pytest.raises(MissingVariableError):
        service.render(template.template_id, {})


def test_version_lookup():
    service = LLMPromptTemplateService()
    v1 = service.register("greeting", "Hi {name}", ["name"])
    v2 = service.register("greeting", "Hey {name}!", ["name"])

    versions = service.versions("greeting")

    assert [t.version for t in versions] == [1, 2]
    assert versions[0].template_id == v1.template_id
    assert versions[1].template_id == v2.template_id

    with pytest.raises(UnknownTemplateError):
        service.versions("does-not-exist")


def test_disabled_template():
    service = LLMPromptTemplateService()
    v1 = service.register("greeting", "Hi {name}", ["name"])
    v2 = service.register("greeting", "Hey {name}!", ["name"])

    assert v1.enabled is True
    assert v2.enabled is False

    with pytest.raises(DisabledTemplateError):
        service.render(v2.template_id, {"name": "Ada"})

    activated = service.activate(v2.template_id)
    assert activated.enabled is True

    with pytest.raises(DisabledTemplateError):
        service.render(v1.template_id, {"name": "Ada"})

    assert service.render(v2.template_id, {"name": "Ada"}) == "Hey Ada!"


def test_immutable_version():
    service = LLMPromptTemplateService()
    v1 = service.register("greeting", "Hi {name}", ["name"])

    with pytest.raises(dataclasses.FrozenInstanceError):
        v1.template = "Changed"

    v2 = service.register("greeting", "Hey {name}!", ["name"])
    assert service.versions("greeting")[0].template == "Hi {name}"

    activated = service.activate(v2.template_id)
    assert v2.enabled is False
    assert activated.enabled is True
    assert activated is not v2

    context_service = LLMContextService()
    context_service.create("req-tmpl-1")
    rendered = service.render(activated.template_id, {"name": "Ada"})
    context_service.add(
        "req-tmpl-1", LLMContextItem(type="user", content=rendered, priority=1)
    )
    built = context_service.build("req-tmpl-1")

    assert built["messages"][0]["content"] == rendered
