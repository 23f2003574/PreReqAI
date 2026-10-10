from backend.llm.secret_redaction import LLMSecretRedactionService
from backend.llm.security_policy import ALLOW, BLOCK, REDACT, LLMSecurityPolicyService
from backend.llm.security_policy_simulation import LLMSecurityPolicySimulationService
from backend.llm.security_test_suite import (
    DEFAULT_INPUT_CASES,
    DEFAULT_OUTPUT_CASES,
    LLMSecurityTestCase,
    LLMSecurityTestSuite,
)
from backend.llm.sensitive_data_policy import LLMSensitiveDataPolicy, LLMSensitiveDataPolicyService

AWS_KEY_TYPE = "AWS access key"
AWS_SECRET = "AKIAABCDEFGHIJKLMNOP"


def build_default_suite():
    return LLMSecurityTestSuite()


def build_redact_suite():
    secret_redaction = LLMSecretRedactionService()
    sensitive_policy = LLMSensitiveDataPolicyService(secret_redaction)
    sensitive_policy.register(LLMSensitiveDataPolicy(policy_id="p1", data_type=AWS_KEY_TYPE, action=REDACT))
    policy_service = LLMSecurityPolicyService(
        sensitive_data_policy_service=sensitive_policy, secret_redaction_service=secret_redaction
    )
    simulation_service = LLMSecurityPolicySimulationService(policy_service, secret_redaction)
    return LLMSecurityTestSuite(simulation_service)


def find(results, name):
    return next(result for result in results if result.name == name)


def test_safe_cases_pass():
    suite = build_default_suite()

    input_results = suite.run_input_cases(DEFAULT_INPUT_CASES)
    output_results = suite.run_output_cases(DEFAULT_OUTPUT_CASES)

    assert find(input_results, "safe_question").passed is True
    assert find(input_results, "safe_question").actual_decision == ALLOW
    assert find(output_results, "safe_summary").passed is True
    assert find(output_results, "safe_summary").actual_decision == ALLOW


def test_secret_cases_are_identified_without_a_registered_policy():
    suite = build_default_suite()

    input_results = suite.run_input_cases(DEFAULT_INPUT_CASES)
    output_results = suite.run_output_cases(DEFAULT_OUTPUT_CASES)

    input_secret_case = find(input_results, "unpolicied_secret_input")
    output_secret_case = find(output_results, "unpolicied_secret_output")

    assert input_secret_case.passed is True
    assert input_secret_case.actual_decision == BLOCK
    assert any(r["pattern"] == AWS_KEY_TYPE for r in input_secret_case.redactions)
    assert AWS_SECRET not in str(input_secret_case.redactions)

    assert output_secret_case.passed is True
    assert output_secret_case.actual_decision == BLOCK
    assert "SECRETS" in output_secret_case.finding_types
    assert any(r["pattern"] == AWS_KEY_TYPE for r in output_secret_case.redactions)
    assert AWS_SECRET not in str(output_secret_case.redactions)


def test_injection_cases_are_blocked():
    suite = build_default_suite()

    result = find(suite.run_input_cases(DEFAULT_INPUT_CASES), "prompt_injection")

    assert result.passed is True
    assert result.actual_decision == BLOCK
    assert "PROMPT_INJECTION" in result.finding_types


def test_blocked_cases_across_input_and_output():
    suite = build_default_suite()

    input_results = suite.run_input_cases(DEFAULT_INPUT_CASES)
    output_results = suite.run_output_cases(DEFAULT_OUTPUT_CASES)

    blocked_input_names = {r.name for r in input_results if r.actual_decision == BLOCK}
    blocked_output_names = {r.name for r in output_results if r.actual_decision == BLOCK}

    assert {"prompt_injection", "tool_boundary_bypass_input", "unpolicied_secret_input"} <= blocked_input_names
    assert {"unsafe_generated_code", "tool_call_boundary_bypass", "unpolicied_secret_output"} <= blocked_output_names
    assert all(r.passed for r in input_results + output_results)


def test_redaction_cases_with_a_configured_policy():
    suite = build_redact_suite()
    cases = (
        LLMSecurityTestCase("redact_secret_input", f"reference: {AWS_SECRET}", REDACT),
        LLMSecurityTestCase("redact_secret_output", f"here is your key {AWS_SECRET}", REDACT),
    )

    input_result = find(suite.run_input_cases([cases[0]]), "redact_secret_input")
    output_result = find(suite.run_output_cases([cases[1]]), "redact_secret_output")

    assert input_result.passed is True
    assert input_result.actual_decision == REDACT
    assert input_result.policy_ids == ("p1",)

    assert output_result.passed is True
    assert output_result.actual_decision == REDACT
    assert output_result.policy_ids == ("p1",)


def test_tool_boundary_cases():
    suite = build_default_suite()

    input_result = find(suite.run_input_cases(DEFAULT_INPUT_CASES), "tool_boundary_bypass_input")
    output_result = find(suite.run_output_cases(DEFAULT_OUTPUT_CASES), "tool_call_boundary_bypass")

    assert input_result.passed is True
    assert "TOOL_BOUNDARY_BYPASS" in input_result.finding_types
    assert output_result.passed is True
    assert "TOOL_BOUNDARY_BYPASS" in output_result.finding_types


def test_generated_code_boundary_cases():
    suite = build_default_suite()

    result = find(suite.run_output_cases(DEFAULT_OUTPUT_CASES), "unsafe_generated_code")

    assert result.passed is True
    assert result.actual_decision == BLOCK
    assert "UNSAFE_INSTRUCTION" in result.finding_types


def test_summary_is_deterministic():
    suite = build_default_suite()
    results = suite.run_input_cases(DEFAULT_INPUT_CASES) + suite.run_output_cases(DEFAULT_OUTPUT_CASES)

    summary_once = suite.summary(results)
    summary_again = suite.summary(results)

    assert summary_once == summary_again
    assert summary_once["total"] == len(results)
    assert summary_once["passed"] == len(results)
    assert summary_once["failed"] == 0
    assert summary_once["failed_cases"] == ()

    rerun_results = suite.run_input_cases(DEFAULT_INPUT_CASES) + suite.run_output_cases(DEFAULT_OUTPUT_CASES)
    assert suite.summary(rerun_results) == summary_once
