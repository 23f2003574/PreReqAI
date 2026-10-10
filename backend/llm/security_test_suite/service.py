from ..models import LLMRequest, LLMResponse
from ..security_audit import INPUT, OUTPUT
from ..security_policy_simulation import LLMSecurityPolicySimulationService
from .models import LLMSecurityTestCase, LLMSecurityTestResult

_MODEL = "gpt-4o-security-test-suite"


class LLMSecurityTestSuite:
    """Reusable harness exercising the real Commit #5 decision -- via
    Commit #7's simulation -- against representative safe, sensitive, and
    malicious cases.

    Adds no detection or policy logic of its own: run_input_cases()/
    run_output_cases() only wrap each case's fixture content into a real
    LLMRequest/LLMResponse -- exactly the shapes Commit #1/#2 already
    validate -- and hand it to
    LLMSecurityPolicySimulationService.simulate_input()/simulate_output(),
    the same read-only preview Commit #7 already provides. Because
    simulation never calls enforce_input()/enforce_output() or an
    LLMSecurityAuditService, running this suite -- for any number of
    cases, any number of times -- never blocks, redacts, or writes any
    Commit #5/#6 state (see Rules: "Test execution must not mutate
    production policy state"). summary() is a pure function of the
    results already produced; it re-runs nothing and is deterministic
    for the same results regardless of call order.

    A caller supplies whichever LLMSecurityPolicySimulationService (and,
    through it, whichever LLMSecurityPolicyService/
    LLMSensitiveDataPolicyService) they want exercised -- this suite is
    the harness, not a fixed policy configuration, so the same harness
    can verify a default (fail-closed) configuration and any number of
    custom, REDACT-configured ones the same way.
    """

    def __init__(self, simulation_service: LLMSecurityPolicySimulationService = None):
        self._simulation = simulation_service or LLMSecurityPolicySimulationService()

    def run_input_cases(self, cases) -> list:
        """Run every LLMSecurityTestCase in `cases` as an LLMRequest."""
        return [self._run_input(case) for case in cases]

    def run_output_cases(self, cases) -> list:
        """Run every LLMSecurityTestCase in `cases` as an LLMResponse."""
        return [self._run_output(case) for case in cases]

    def _run_input(self, case: LLMSecurityTestCase) -> LLMSecurityTestResult:
        request = LLMRequest(model=_MODEL, messages=[{"role": "user", "content": case.content}])
        simulation = self._simulation.simulate_input(request)
        return self._result(case, INPUT, simulation)

    def _run_output(self, case: LLMSecurityTestCase) -> LLMSecurityTestResult:
        response = LLMResponse(content=case.content, model=_MODEL, usage={})
        simulation = self._simulation.simulate_output(response)
        return self._result(case, OUTPUT, simulation)

    @staticmethod
    def _result(case: LLMSecurityTestCase, direction: str, simulation) -> LLMSecurityTestResult:
        return LLMSecurityTestResult(
            name=case.name,
            direction=direction,
            expected_decision=case.expected_decision,
            actual_decision=simulation.decision,
            passed=simulation.decision == case.expected_decision,
            policy_ids=simulation.policies,
            finding_types=tuple(sorted({finding.category for finding in simulation.findings})),
            redactions=simulation.redactions,
        )

    @staticmethod
    def summary(results) -> dict:
        """A deterministic roll-up of already-produced results.

        Same shape regardless of call order or how many times it is
        called for the same `results` -- a pure function with no state
        of its own and no re-evaluation of any case.
        """
        results = list(results)

        by_decision = {}
        for result in results:
            by_decision[result.actual_decision] = by_decision.get(result.actual_decision, 0) + 1

        failed_cases = tuple(result.name for result in results if not result.passed)

        return {
            "total": len(results),
            "passed": sum(1 for result in results if result.passed),
            "failed": len(failed_cases),
            "failed_cases": failed_cases,
            "by_decision": dict(sorted(by_decision.items())),
        }
