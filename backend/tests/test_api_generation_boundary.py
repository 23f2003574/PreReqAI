from dataclasses import replace

import pytest

from backend.api_documentation_draft import DRAFT, UnknownDraftError
from backend.api_generation import (
    APIGenerator,
    DraftNotValidatedError,
    InvalidGeneratorOutputError,
    LLMAPIGenerationService,
)
from test_llm_api_documentation_draft import (
    ANALYSIS_RESPONSE,
    CANDIDATE_RESPONSE,
    DOC_RESPONSE,
    EMPTY_REVIEW_RESPONSE,
    EXPOSURE_RESPONSE,
    INPUT_SCHEMA_RESPONSE,
    OUTPUT_SCHEMA_RESPONSE,
    _approved_recommendation,
    build_env,
    make_response,
)


class RecordingGenerator(APIGenerator):
    def __init__(self, output=None):
        self.seen = []
        self.output = {"app/main.py": "# generated"} if output is None else output

    def generate(self, draft):
        self.seen.append(draft)
        return self.output


def _draft(env):
    draft = env["draft"].generate(_approved_recommendation(env))
    return draft, env["draft"].validate(draft)


def _env():
    return build_env(
        [make_response(r) for r in (
            ANALYSIS_RESPONSE, CANDIDATE_RESPONSE, INPUT_SCHEMA_RESPONSE, OUTPUT_SCHEMA_RESPONSE,
            EXPOSURE_RESPONSE, EMPTY_REVIEW_RESPONSE, DOC_RESPONSE,
        )]
    )


def test_validated_draft_reaches_the_generator_unchanged():
    env = _env()
    _, validated = _draft(env)
    generator = RecordingGenerator()

    result = LLMAPIGenerationService(env["draft"], generator).generate(validated)

    assert generator.seen == [validated]
    assert (result.draft_id, result.endpoint) == (validated.draft_id, "POST /add")
    assert result.files == {"app/main.py": "# generated"}


def test_unvalidated_draft_never_reaches_the_generator():
    env = _env()
    draft, _ = _draft(env)
    generator = RecordingGenerator()

    with pytest.raises(DraftNotValidatedError):
        LLMAPIGenerationService(env["draft"], generator).generate(draft)
    assert draft.status == DRAFT and generator.seen == []


def test_forged_or_stale_validated_copy_is_rejected():
    env = _env()
    _, validated = _draft(env)
    generator = RecordingGenerator()
    service = LLMAPIGenerationService(env["draft"], generator)

    with pytest.raises(DraftNotValidatedError):
        service.generate(replace(validated, summary="tampered"))
    assert generator.seen == []


def test_unknown_draft_raises_the_draft_services_own_error():
    env = _env()
    _, validated = _draft(env)
    generator = RecordingGenerator()

    with pytest.raises(UnknownDraftError):
        LLMAPIGenerationService(env["draft"], generator).generate(replace(validated, draft_id="never-generated"))
    assert generator.seen == []


@pytest.mark.parametrize("bad", [None, ["x"], {"a.py": 1}, {1: "x"}])
def test_malformed_generator_output_is_rejected(bad):
    env = _env()
    _, validated = _draft(env)
    generator = RecordingGenerator(output=bad if bad is not None else "not a dict")

    with pytest.raises(InvalidGeneratorOutputError):
        LLMAPIGenerationService(env["draft"], generator).generate(validated)
