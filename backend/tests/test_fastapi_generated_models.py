from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from backend.api_generation import FastAPIApplicationGenerator, InvalidDraftEndpointError
from test_api_generation_boundary import _draft, _env
from test_fastapi_application_generation import _app


def _base():
    _, validated = _draft(_env())
    return validated


def _app_for(**overrides):
    return _app(FastAPIApplicationGenerator().generate(replace(_base(), **overrides)))


def _schemas(app):
    return app.openapi()["components"]["schemas"]


def test_primitive_fields_map_to_their_json_schema_types():
    params = {n: {"type": t, "required": True} for n, t in (("i", "int"), ("f", "float"), ("s", "str"), ("b", "bool"))}
    schema = _schemas(_app_for(parameters=params, examples=[]))["PostAddRequest"]

    assert {k: v["type"] for k, v in schema["properties"].items()} == {
        "i": "integer", "f": "number", "s": "string", "b": "boolean",
    }


def test_required_and_optional_fields_and_their_validation():
    params = {"a": {"type": "int", "required": True}, "note": {"type": "str", "required": False}}
    app = _app_for(parameters=params, examples=[])
    client = TestClient(app)

    assert _schemas(app)["PostAddRequest"]["required"] == ["a"]
    assert client.post("/add", json={"note": "x"}).status_code == 422
    assert client.post("/add", json={"a": 1}).status_code == 501  # valid request, no matching example


def test_documented_defaults_are_carried_over_and_make_the_field_optional():
    params = {"a": {"type": "int", "required": True}, "scale": {"type": "int", "required": True, "default": 10}}
    app = _app_for(parameters=params, examples=[{"input": {"a": 1}, "output": {"sum": 3}}])
    schema = _schemas(app)["PostAddRequest"]

    assert schema["properties"]["scale"]["default"] == 10 and schema["required"] == ["a"]
    assert TestClient(app).post("/add", json={"a": 1}).status_code == 200


def test_min_max_constraints_are_enforced():
    params = {"a": {"type": "int", "required": True, "constraints": {"min": 0, "max": 5}}}
    client = TestClient(_app_for(parameters=params, examples=[]))

    assert client.post("/add", json={"a": 9}).status_code == 422
    assert client.post("/add", json={"a": -1}).status_code == 422
    assert client.post("/add", json={"a": 3}).status_code == 501


def test_nested_object_and_typed_list_structures_become_models():
    responses = {
        "point": {"type": "dict", "nullable": False, "structure": {"type": "object", "properties": {"x": "int", "y": "int"}}},
        "tags": {"type": "list", "nullable": True, "structure": {"type": "list", "items": "str"}},
    }
    app = _app_for(responses=responses, examples=[{"input": {"a": 1, "b": 2}, "output": {"point": {"x": 1, "y": 2}}}])
    schemas = _schemas(app)

    assert set(schemas["PostAddResponsePoint"]["properties"]) == {"x", "y"}
    assert schemas["PostAddResponse"]["required"] == ["point"]
    body = TestClient(app).post("/add", json={"a": 1, "b": 2})
    assert body.status_code == 200 and body.json()["point"] == {"x": 1, "y": 2}


def test_response_model_is_registered_on_the_route():
    app = _app_for()

    [route] = [r for r in app.routes if r.path == "/add"]
    assert route.response_model.__name__ == "PostAddResponse"
    assert app.openapi()["paths"]["/add"]["post"]["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/PostAddResponse"
    }


@pytest.mark.parametrize(
    "overrides",
    [
        {"parameters": {"a": {"type": "decimal", "required": True}}},
        {"parameters": {"a": {"type": "str", "required": True, "constraints": {"min": 1}}}},
        {"parameters": {"a": {"type": "int", "required": True, "constraints": {"pattern": "x"}}}},
        {"responses": {"r": {"type": "dict", "nullable": False, "structure": {"type": "object", "properties": {"x": "blob"}}}}},
        {"responses": {"r": {"type": "list", "nullable": False, "structure": {"type": "tuple-of", "items": "int"}}}},
    ],
)
def test_schemas_that_cannot_be_represented_safely_are_rejected_not_guessed(overrides):
    with pytest.raises(InvalidDraftEndpointError):
        FastAPIApplicationGenerator().generate(replace(_base(), **overrides))


def test_model_names_are_deterministic_and_derived_from_the_endpoint():
    files = FastAPIApplicationGenerator().generate(replace(_base(), endpoint="PUT /v1/user-items"))["app/main.py"]

    assert "class PutV1UserItemsRequest(BaseModel)" in files and "class PutV1UserItemsResponse(BaseModel)" in files
