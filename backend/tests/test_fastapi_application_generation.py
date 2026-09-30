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


def test_route_validates_requests_and_returns_the_documented_example_for_a_matching_input():
    _, validated, service = _generate()
    client = TestClient(_app(service.generate(validated).files))

    assert client.post("/add", json={"a": 1}).status_code == 422
    matched = client.post("/add", json={"a": 1, "b": 2})
    assert (matched.status_code, matched.json()) == (200, {"sum": 3})
    assert matched.headers["X-Execution"] == "documented-example"


def test_input_outside_the_documented_examples_is_an_explicit_501_not_a_fake_result():
    _, validated, service = _generate()
    client = TestClient(_app(service.generate(validated).files))

    response = client.post("/add", json={"a": 5, "b": 5})

    assert response.status_code == 501 and "no documented example" in response.json()["detail"]
    assert "X-Execution" not in response.headers


def test_endpoint_without_request_input_returns_its_documented_output():
    _, validated, _ = _generate()
    draft = replace(validated, parameters={}, examples=[{"input": {}, "output": {"sum": 3}}])
    client = TestClient(_app(FastAPIApplicationGenerator().generate(draft)))

    response = client.post("/add", json={})

    assert (response.status_code, response.json()) == (200, {"sum": 3})


def test_get_endpoint_matches_documented_query_input():
    _, validated, _ = _generate()
    draft = replace(
        validated, endpoint="GET /find", parameters={"q": {"type": "str", "required": True}},
        responses={"hits": {"type": "list", "nullable": False}},
        examples=[{"input": {"q": "x"}, "output": {"hits": ["x1"]}}],
    )
    client = TestClient(_app(FastAPIApplicationGenerator().generate(draft)))

    assert client.get("/find", params={"q": "x"}).json() == {"hits": ["x1"]}
    assert client.get("/find", params={"q": "y"}).status_code == 501


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
