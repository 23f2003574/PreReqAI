import types
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from backend.api_generation import (
    DraftNotValidatedError,
    FastAPIApplicationGenerator,
    InvalidDraftEndpointError,
    LLMAPIGenerationService,
)
from test_api_generation_boundary import _draft, _env


def _app(files):
    source = files["main.py"]
    compile(source, "main.py", "exec")
    module = types.ModuleType("generated_app")
    exec(source, module.__dict__)
    return module.app


def _generate():
    env = _env()
    _, validated = _draft(env)
    service = LLMAPIGenerationService(env["draft"], FastAPIApplicationGenerator())
    return env, validated, service


def test_validated_draft_becomes_a_fastapi_app_whose_routes_match_the_draft():
    _, validated, service = _generate()

    result = service.generate(validated)
    app = _app(result.files)

    [route] = [r for r in app.routes if r.path == "/add"]
    assert route.methods == {"POST"} and route.summary == validated.summary
    assert route.description == validated.description
    schema = app.openapi()
    operation = schema["paths"]["/add"]["post"]
    assert operation["summary"] == "Adds two numbers."
    request_props = schema["components"]["schemas"]["RequestModel"]["properties"]
    assert {k: v["type"] for k, v in request_props.items()} == {"a": "integer", "b": "integer"}
    assert schema["components"]["schemas"]["RequestModel"]["required"] == ["a", "b"]
    assert {k: v["type"] for k, v in schema["components"]["schemas"]["ResponseModel"]["properties"].items()} == {
        "sum": "integer"
    }


def test_generated_route_validates_requests_and_is_honestly_unimplemented():
    _, validated, service = _generate()
    client = TestClient(_app(service.generate(validated).files))

    assert client.post("/add", json={"a": 1}).status_code == 422
    assert client.post("/add", json={"a": 1, "b": 2}).status_code == 501


def test_generation_is_deterministic():
    _, validated, service = _generate()

    assert service.generate(validated).files == service.generate(validated).files


def test_unvalidated_draft_is_rejected_before_generation():
    env = _env()
    draft, _ = _draft(env)

    with pytest.raises(DraftNotValidatedError):
        LLMAPIGenerationService(env["draft"], FastAPIApplicationGenerator()).generate(draft)


@pytest.mark.parametrize("endpoint", ["FETCH /add", "POST add", "POST"])
def test_unsupported_endpoint_is_rejected(endpoint):
    _, validated, _ = _generate()
    with pytest.raises(InvalidDraftEndpointError):
        FastAPIApplicationGenerator().generate(replace(validated, endpoint=endpoint))


def test_non_identifier_field_name_is_rejected():
    _, validated, _ = _generate()
    with pytest.raises(InvalidDraftEndpointError):
        FastAPIApplicationGenerator().generate(replace(validated, parameters={"a-b": {"type": "int", "required": True}}))


def test_get_endpoint_uses_query_parameters_and_optional_fields():
    _, validated, _ = _generate()
    draft = replace(
        validated, endpoint="GET /find",
        parameters={"q": {"type": "str", "required": True}, "limit": {"type": "int", "required": False}},
        responses={"hits": {"type": "list", "nullable": True}},
    )
    app = _app(FastAPIApplicationGenerator().generate(draft))

    params = {p["name"]: p["required"] for p in app.openapi()["paths"]["/find"]["get"]["parameters"]}
    assert params == {"q": True, "limit": False}
    assert TestClient(app).get("/find").status_code == 422
