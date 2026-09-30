"""End-to-end smoke for the notebook -> API documentation workflow using the
real services, wired exactly as the per-stage suites wire them. Only the LLM
provider is scripted (the one genuinely external dependency).

Stages covered: notebook analysis -> API candidate -> input/output schema ->
exposure recommendation -> schema review (approval gate) -> documentation
draft -> validated draft.

Not covered because the repository has no implementation of them: FastAPI
code generation, generated-artifact validation (backend.compilation_execution
only defines the abstract Compiler contract) and OpenAPI generation for a
generated API (api_documentation_draft states it never regenerates OpenAPI)."""
from test_llm_api_documentation_draft import (
    ANALYSIS_RESPONSE,
    CANDIDATE_RESPONSE,
    DOC_RESPONSE,
    EMPTY_REVIEW_RESPONSE,
    EXPOSURE_RESPONSE,
    INPUT_SCHEMA_RESPONSE,
    NOTEBOOK,
    OUTPUT_SCHEMA_RESPONSE,
    VALIDATED,
    _confident_intent,
    build_env,
    make_response,
)


def test_notebook_flows_through_every_existing_stage_to_a_validated_api_draft():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(EXPOSURE_RESPONSE),
            make_response(EMPTY_REVIEW_RESPONSE),
            make_response(DOC_RESPONSE),
        ]
    )

    analysis = env["notebook_analysis"].analyze(NOTEBOOK)
    assert [f["name"] for f in env["notebook_analysis"].functions(analysis.analysis_id)] == ["add"]

    [candidate] = env["api_candidate"].analyze(analysis.analysis_id)
    assert (candidate.function_name, candidate.inputs, candidate.outputs) == ("add", ["a", "b"], ["sum"])

    env["input_schema"].infer(candidate.candidate_id)
    env["output_schema"].infer(candidate.candidate_id)
    [recommendation] = env["exposure"].recommend(_confident_intent())
    assert (recommendation.method, recommendation.endpoint_name) == ("POST", "/add")

    review = env["review"].review(recommendation)
    assert env["review"].approved(review.review_id)

    draft = env["draft"].validate(env["draft"].generate(recommendation))

    assert draft.status == VALIDATED and draft.endpoint == "POST /add"
    assert draft.parameters == {"a": {"type": "int", "required": True}, "b": {"type": "int", "required": True}}
    assert draft.responses == {"sum": {"type": "int", "nullable": False}}
    assert draft.examples == [{"input": {"a": 1, "b": 2}, "output": {"sum": 3}}]
    assert env["draft"].get(draft.draft_id) == draft
