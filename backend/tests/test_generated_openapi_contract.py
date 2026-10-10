import json
from dataclasses import replace

from backend.api_generation import (
    OPENAPI_FILENAME,
    FastAPIApplicationGenerator,
    LLMAPIGenerationResult,
    generated_openapi,
    write_openapi_contract,
)
from test_generated_application_entrypoint import _result


def _refs(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref":
                yield value
            else:
                yield from _refs(value)
    elif isinstance(node, list):
        for item in node:
            yield from _refs(item)


def _resolve(document, ref):
    node = document
    for part in ref.lstrip("#/").split("/"):
        node = node[part]
    return node


def test_contract_is_a_structurally_valid_openapi_document_for_the_generated_app():
    result, draft = _result()

    document = generated_openapi(result)

    assert document["openapi"].startswith("3.")
    assert document["info"]["title"] == draft.summary and document["info"]["description"] == draft.description
    assert list(document["paths"]) == ["/add"] and list(document["paths"]["/add"]) == ["post"]
    assert all(_resolve(document, ref) for ref in _refs(document))  # every $ref resolves


def test_operation_request_body_and_responses_match_the_draft():
    result, draft = _result()
    document = generated_openapi(result)
    operation = document["paths"]["/add"]["post"]

    assert operation["summary"] == draft.summary and operation["description"] == draft.description
    assert operation["operationId"] == "handler_add_post"
    request = _resolve(document, operation["requestBody"]["content"]["application/json"]["schema"]["$ref"])
    assert {k: v["type"] for k, v in request["properties"].items()} == {"a": "integer", "b": "integer"}
    assert request["required"] == ["a", "b"]
    ok = _resolve(document, operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"])
    assert {k: v["type"] for k, v in ok["properties"].items()} == {"sum": "integer"}
    assert "422" in operation["responses"]


def test_get_endpoint_documents_query_parameters_not_a_request_body():
    result, draft = _result()
    draft = replace(
        draft, endpoint="GET /find",
        parameters={"q": {"type": "str", "required": True}, "limit": {"type": "int", "required": False, "default": 5}},
        responses={"hits": {"type": "list", "nullable": False}}, examples=[],
    )
    files = FastAPIApplicationGenerator().generate(draft)

    operation = generated_openapi(LLMAPIGenerationResult("d", draft.endpoint, files))["paths"]["/find"]["get"]

    assert "requestBody" not in operation
    assert {p["name"]: (p["in"], p["required"]) for p in operation["parameters"]} == {
        "q": ("query", True), "limit": ("query", False),
    }


def test_written_contract_is_valid_json_and_byte_identical_across_runs(tmp_path):
    result, _ = _result()

    first = write_openapi_contract(result, tmp_path).read_bytes()
    second = write_openapi_contract(result, tmp_path).read_bytes()

    assert first == second and (tmp_path / OPENAPI_FILENAME).exists()
    assert json.loads(first) == generated_openapi(result)
    assert sorted(p.name for p in tmp_path.iterdir()) == [OPENAPI_FILENAME]
