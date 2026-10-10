from datetime import datetime, timezone

from backend.compilation_plan import LLMCompilationPlanningService
from backend.compilation_review import LLMCompilationReviewService, UnknownReviewError

from .compiler import FAILED, SUCCEEDED, Compiler, CompilerError, CompilerJobResult
from .models import LLMCompilationExecution


class UnreviewedPlanError(ValueError):
    """Raised when execute() is called for a plan that was never reviewed."""


class PlanNotApprovedError(ValueError):
    """Raised when execute() is called for a plan whose review status is not APPROVED."""


class InvalidCompilerOutputError(ValueError):
    """Raised when the compiler's own result doesn't satisfy its interface contract."""


class UnknownExecutionError(KeyError):
    """Raised when looking up an execution_id that was never created."""


class LLMCompilationExecutionService:
    """The only bridge between a Commit #11 plan and the existing deterministic compiler.

    Reuses Commit #11's LLMCompilationPlanningService and Commit #12's
    LLMCompilationReviewService as the sole gate: execute() never runs a
    plan that hasn't been reviewed and approved. The compiler itself is
    injected as a Compiler (see compiler.py) -- this service converts a plan
    into its input, calls it, and records what it returned; it never
    second-guesses, retries, or overrides the compiler's own verdict, and
    never accepts a result that doesn't satisfy the Compiler contract.
    """

    def __init__(
        self,
        plan_service: LLMCompilationPlanningService,
        review_service: LLMCompilationReviewService,
        compiler: Compiler,
    ):
        self._plan_service = plan_service
        self._review_service = review_service
        self._compiler = compiler
        self._executions = {}
        self._execution_counter = 0

    @staticmethod
    def _build_compiler_input(plan) -> dict:
        return {
            "notebook_id": plan.notebook_id,
            "plan_id": plan.plan_id,
            "candidates": [
                {
                    "candidate_id": candidate.candidate_id,
                    "function_name": candidate.function_name,
                    "endpoint": next(
                        (e for e in plan.endpoints if e["candidate_id"] == candidate.candidate_id), None
                    ),
                    "input_schema": {
                        "types": plan.schemas[candidate.candidate_id]["input"].types,
                        "required": plan.schemas[candidate.candidate_id]["input"].required,
                        "defaults": plan.schemas[candidate.candidate_id]["input"].defaults,
                    },
                    "output_schema": {
                        "types": plan.schemas[candidate.candidate_id]["output"].types,
                        "nullable": plan.schemas[candidate.candidate_id]["output"].nullable,
                    },
                }
                for candidate in plan.candidates
            ],
        }

    @staticmethod
    def _validate_compiler_result(result) -> None:
        if not isinstance(result, CompilerJobResult):
            raise InvalidCompilerOutputError(
                f"compiler must return a CompilerJobResult, got {type(result).__name__}"
            )
        if not isinstance(result.job_id, str) or not result.job_id.strip():
            raise InvalidCompilerOutputError("compiler result job_id must be a non-empty string")
        if result.status not in (SUCCEEDED, FAILED):
            raise InvalidCompilerOutputError(f"compiler result status {result.status!r} is not valid")
        if not isinstance(result.output, dict):
            raise InvalidCompilerOutputError("compiler result output must be a dict")

    def execute(self, plan_id: str) -> LLMCompilationExecution:
        try:
            approved = self._review_service.approved(plan_id)
        except UnknownReviewError as exc:
            raise UnreviewedPlanError(f"plan {plan_id!r} has not been reviewed") from exc

        if not approved:
            raise PlanNotApprovedError(f"plan {plan_id!r} was reviewed but not approved")

        plan = self._plan_service.get(plan_id)
        compiler_input = self._build_compiler_input(plan)

        self._execution_counter += 1
        execution_id = f"execution-{plan_id}-{self._execution_counter}"
        created_at = datetime.now(timezone.utc)

        try:
            result = self._compiler.compile(compiler_input)
        except CompilerError as exc:
            execution = LLMCompilationExecution(
                execution_id=execution_id,
                plan_id=plan_id,
                compiler_job_id=exc.job_id,
                status=FAILED,
                created_at=created_at,
                completed_at=datetime.now(timezone.utc),
            )
            self._executions[execution_id] = execution
            return execution

        self._validate_compiler_result(result)

        execution = LLMCompilationExecution(
            execution_id=execution_id,
            plan_id=plan_id,
            compiler_job_id=result.job_id,
            status=result.status,
            created_at=created_at,
            completed_at=datetime.now(timezone.utc),
        )
        self._executions[execution_id] = execution
        return execution

    def _get(self, execution_id: str) -> LLMCompilationExecution:
        try:
            return self._executions[execution_id]
        except KeyError:
            raise UnknownExecutionError(execution_id)

    def status(self, execution_id: str) -> str:
        return self._get(execution_id).status

    def compiler_job(self, execution_id: str):
        return self._get(execution_id).compiler_job_id
