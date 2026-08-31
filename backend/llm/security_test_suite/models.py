from dataclasses import dataclass, field


@dataclass(frozen=True)
class LLMSecurityTestCase:
    """One representative input/output payload for LLMSecurityTestSuite.

    name identifies the case in a result/summary without needing to
    reveal what content it carries. content is fixture text only -- a
    synthetic example of a safe, sensitive, or malicious payload, never
    a real user prompt or response -- wrapped into an LLMRequest (by
    run_input_cases()) or an LLMResponse (by run_output_cases()) exactly
    as Commit #1/#2 already expect. expected_decision is one of Commit
    #5's own ALLOW/REDACT/BLOCK vocabulary: what the real pipeline,
    exercised through Commit #7's simulation, should decide for this
    content.
    """

    name: str
    content: str
    expected_decision: str


@dataclass(frozen=True)
class LLMSecurityTestResult:
    """The outcome of running one LLMSecurityTestCase through the real
    Commit #5 decision, via Commit #7's read-only simulation.

    passed is expected_decision == actual_decision. policy_ids and
    finding_types identify what actually applied/was raised -- Commit
    #6's own "identify without exposing" fields, reused here rather than
    a second convention. redactions is Commit #7's own detect()-derived
    {"location", "pattern"} preview: it is what identifies a secret case
    even when no Commit #4 policy is registered for the data_type found
    (an unpolicied secret still fails closed to BLOCK with no
    finding_types of its own -- Commit #1/#2 have no SECRETS-style
    category on the input side -- so redactions is what names the
    sensitive data_type actually responsible). None of these three
    fields ever carries a matched value or finding evidence -- only
    labels.
    """

    name: str
    direction: str
    expected_decision: str
    actual_decision: str
    passed: bool
    policy_ids: tuple = field(default_factory=tuple)
    finding_types: tuple = field(default_factory=tuple)
    redactions: tuple = field(default_factory=tuple)
