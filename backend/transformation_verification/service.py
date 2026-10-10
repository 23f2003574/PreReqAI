import ast
from datetime import datetime, timezone

from backend.api_candidates import LLMAPICandidateService
from backend.code_transformation import LLMCodeTransformationService
from backend.test_generation import EDGE, VALID, LLMTestGenerationService
from backend.transformation_diff import LLMTransformationDiffService
from backend.transformation_execution import SUCCEEDED, LLMTransformationExecutionService

from .models import LLMTransformationVerification


class ExecutionNotAppliedError(ValueError):
    """Raised when verify() is called for an execution that isn't currently SUCCEEDED
    (i.e. it was never applied, or it has since been rolled back)."""


class UnknownVerificationError(KeyError):
    """Raised when syntax()/tests()/blocking() is called before verify() for an execution_id."""


def _blocking(category: str, target: str, message: str) -> dict:
    return {"category": category, "target": target, "message": message, "blocking": True}


def _advisory(category: str, target: str, message: str) -> dict:
    return {"category": category, "target": target, "message": message, "blocking": False}


def _function_names(tree: ast.Module) -> list:
    return [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]


def _parameter_names(tree: ast.Module, function_name: str) -> tuple:
    for node in tree.body:
        if not (isinstance(node, ast.FunctionDef) and node.name == function_name):
            continue

        args = node.args
        positional = list(args.posonlyargs) + list(args.args)
        required = {a.arg for a in positional[: len(positional) - len(args.defaults)]}
        optional = {a.arg for a in positional[len(positional) - len(args.defaults) :]}
        for kwonly, default in zip(args.kwonlyargs, args.kw_defaults):
            (required if default is None else optional).add(kwonly.arg)

        return required | optional, required

    return set(), set()


class LLMTransformationVerificationService:
    """Verifies a Commit #5 applied execution before it may be accepted as a valid build input.

    Reuses LLMTransformationExecutionService (only a SUCCEEDED, i.e.
    currently-applied, execution can be verified -- one that was never
    applied or has since been rolled back is rejected) and, once syntax
    passes, backend.api_candidates + backend.test_generation from the
    original notebook-to-API series to find any tests already generated for
    the transformed function. Like every generator/validator throughout
    this codebase, verification never executes the transformed function --
    it checks deterministically whether each generated test's input is
    still compatible with the function's actual parameter signature (via
    `ast`), which is enough to catch a transformation that silently broke
    an existing test's assumptions without ever running arbitrary code.
    Producing a verification never modifies notebook source, the
    execution, or anything upstream of it.
    """

    def __init__(
        self,
        execution_service: LLMTransformationExecutionService,
        diff_service: LLMTransformationDiffService,
        transformation_service: LLMCodeTransformationService,
        api_candidate_service: LLMAPICandidateService,
        test_generation_service: LLMTestGenerationService,
    ):
        self._execution_service = execution_service
        self._diff_service = diff_service
        self._transformation_service = transformation_service
        self._api_candidate_service = api_candidate_service
        self._test_generation_service = test_generation_service
        self._verifications = {}
        self._verification_counter = 0

    def _check_tests(self, execution, parsed_cells: dict) -> tuple:
        findings = []
        tests_passed = True

        diff = self._diff_service.get(execution.diff_id)
        plan = self._transformation_service.get(diff.plan_id)
        candidates_by_function = {
            candidate.function_name: candidate
            for candidate in self._api_candidate_service.candidates(plan.notebook_id)
        }

        any_tests_checked = False
        for applied in execution.applied_cells:
            tree = parsed_cells[applied["cell_index"]]
            for function_name in _function_names(tree):
                candidate = candidates_by_function.get(function_name)
                if candidate is None:
                    continue

                generated_tests = self._test_generation_service.tests(candidate.candidate_id)
                if not generated_tests:
                    continue

                all_params, required_params = _parameter_names(tree, function_name)

                # INVALID tests deliberately violate the original schema (a
                # missing required field or a wrong type) -- that's the
                # point of them, so only VALID/EDGE tests are checked for
                # parameter compatibility with the transformed signature.
                for test in generated_tests:
                    if test.category not in (VALID, EDGE):
                        continue

                    any_tests_checked = True
                    input_fields = set(test.input)
                    unknown_fields = sorted(input_fields - all_params)
                    missing_required = sorted(required_params - input_fields)
                    if not unknown_fields and not missing_required:
                        continue

                    tests_passed = False
                    reasons = []
                    if unknown_fields:
                        reasons.append(f"references removed parameters {unknown_fields}")
                    if missing_required:
                        reasons.append(f"is missing now-required parameters {missing_required}")
                    findings.append(
                        _blocking(
                            "TEST_FAILURE",
                            test.test_id,
                            f"generated test for {function_name!r} " + "; ".join(reasons),
                        )
                    )

        if not any_tests_checked:
            findings.append(
                _advisory(
                    "NO_TESTS_FOUND",
                    execution.execution_id,
                    "no generated tests were found for the transformed function(s)",
                )
            )

        return tests_passed, findings

    def verify(self, execution_id: str) -> LLMTransformationVerification:
        execution = self._execution_service.get(execution_id)
        if execution.status != SUCCEEDED:
            raise ExecutionNotAppliedError(
                f"execution {execution_id!r} is not an applied transformation (status={execution.status!r})"
            )

        findings = []
        syntax_valid = True
        parsed_cells = {}
        for applied in execution.applied_cells:
            try:
                parsed_cells[applied["cell_index"]] = ast.parse(applied["applied_source"])
            except SyntaxError as exc:
                syntax_valid = False
                findings.append(
                    _blocking(
                        "SYNTAX_ERROR", str(applied["cell_index"]), f"applied source does not parse: {exc}"
                    )
                )

        if syntax_valid:
            tests_passed, test_findings = self._check_tests(execution, parsed_cells)
            findings.extend(test_findings)
        else:
            tests_passed = False
            findings.append(
                _advisory(
                    "TESTS_SKIPPED", execution_id, "tests were skipped because syntax validation failed"
                )
            )

        self._verification_counter += 1
        verification = LLMTransformationVerification(
            verification_id=f"verification-{execution_id}-{self._verification_counter}",
            execution_id=execution_id,
            syntax_valid=syntax_valid,
            tests_passed=tests_passed,
            findings=findings,
            verified_at=datetime.now(timezone.utc),
        )
        self._verifications[execution_id] = verification
        return verification

    def _get(self, execution_id: str) -> LLMTransformationVerification:
        try:
            return self._verifications[execution_id]
        except KeyError:
            raise UnknownVerificationError(execution_id)

    def syntax(self, execution_id: str) -> bool:
        return self._get(execution_id).syntax_valid

    def tests(self, execution_id: str) -> bool:
        return self._get(execution_id).tests_passed

    def blocking(self, execution_id: str) -> bool:
        return any(finding["blocking"] for finding in self._get(execution_id).findings)
