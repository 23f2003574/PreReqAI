import copy
import re
from datetime import datetime, timezone

from backend.code_fix_suggestions import LLMCodeFixSuggestionService
from backend.code_patch_planning import REPLACE, LLMCodePatchService
from backend.code_patch_validation import LLMCodePatchValidationService
from backend.compilation_execution import CompilerJobResult
from backend.generated_code_review import LLMGeneratedCodeReviewService

from .models import ROLLED_BACK, SUCCEEDED, LLMCodePatchExecution

_MISSING = object()
_SEGMENT_RE = re.compile(r"([^.\[\]]+)|\[(\d+)\]")


class PatchNotValidError(ValueError):
    """Raised when apply() is called for a plan whose Commit #4 validation is blocking (or missing)."""


class ApplicationNotValidatedError(ValueError):
    """Raised when apply()/rollback() can't proceed because an operation's location
    no longer exists in the actual generated output."""


class AlreadyAppliedError(ValueError):
    """Raised when apply() is called for a plan that has already been applied."""


class InvalidRollbackStateError(ValueError):
    """Raised when rollback() is called for an execution that isn't currently SUCCEEDED."""


class UnknownExecutionError(KeyError):
    """Raised when looking up an execution_id that was never created."""


def _parse_location(location: str) -> list:
    tokens = []
    for key, index in _SEGMENT_RE.findall(location):
        tokens.append(int(index) if index != "" else key)
    return tokens


def _navigate_container(output: dict, location: str):
    """Return (container, last_key) for a location path -- the exact same
    dot/bracket addressing scheme backend.generated_code_review already
    uses to build finding locations -- or (_MISSING, None) if any segment
    up to the container doesn't exist."""
    tokens = _parse_location(location)
    current = output
    for token in tokens[:-1]:
        if isinstance(token, int):
            if not isinstance(current, list) or not (0 <= token < len(current)):
                return _MISSING, None
        else:
            if not isinstance(current, dict) or token not in current:
                return _MISSING, None
        current = current[token]
    return current, tokens[-1]


def _get_at_path(output: dict, location: str):
    container, key = _navigate_container(output, location)
    if container is _MISSING:
        return _MISSING
    if isinstance(key, int):
        if not isinstance(container, list) or not (0 <= key < len(container)):
            return _MISSING
        return container[key]
    if not isinstance(container, dict) or key not in container:
        return _MISSING
    return container[key]


def _set_at_path(output: dict, location: str, value) -> None:
    container, key = _navigate_container(output, location)
    if container is _MISSING:
        raise ApplicationNotValidatedError(f"location {location!r} has no existing container to write into")
    container[key] = value


def _delete_at_path(output: dict, location: str) -> None:
    container, key = _navigate_container(output, location)
    if container is _MISSING or (isinstance(key, str) and key not in container):
        raise ApplicationNotValidatedError(f"location {location!r} has no existing container to delete from")
    del container[key]


def _top_level_key(location: str) -> str:
    return str(_parse_location(location)[0])


class LLMCodePatchExecutionService:
    """Applies a Commit #3 patch plan -- once Commit #4 has validated it clean --
    to the actual generated output it targets, atomically.

    Reuses LLMCodePatchValidationService.blocking() (must be False) as the
    sole gate -- apply() never re-derives validity itself, and never
    touches generated output for a plan that hasn't cleared it. The real
    output to write into is located by walking the same chain every
    earlier commit already built -- plan -> Commit #2 suggestion -> Commit
    #1 review -> the exact CompilerJobResult backend.generated_code_review
    retained from that review's own review() call -- the only "generated
    code" this codebase has, never a new file format. Every operation's
    location is confirmed to still exist in that live output before any
    mutation happens, so a precondition failure -- not validated, already
    applied, or a location that no longer exists -- always leaves the
    generated output completely unchanged. Applying a plan is then just a
    sequence of in-place dict writes at already-confirmed paths, which
    cannot partially fail; rollback() reads this service's own record of
    each write's original value to restore them the same way.
    """

    def __init__(
        self,
        review_service: LLMGeneratedCodeReviewService,
        fix_service: LLMCodeFixSuggestionService,
        patch_service: LLMCodePatchService,
        validation_service: LLMCodePatchValidationService,
    ):
        self._review_service = review_service
        self._fix_service = fix_service
        self._patch_service = patch_service
        self._validation_service = validation_service
        self._executions = {}
        self._execution_id_by_plan = {}
        self._original_values = {}
        self._execution_counter = 0

    def _resolve_output(self, plan) -> CompilerJobResult:
        suggestion = self._fix_service.get(plan.suggestion_id)
        review = self._review_service.get(suggestion.review_id)
        return self._review_service.get_generated_output(review.target)

    def apply(self, plan_id: str) -> LLMCodePatchExecution:
        if plan_id in self._execution_id_by_plan:
            raise AlreadyAppliedError(f"plan {plan_id!r} has already been applied")

        if self._validation_service.blocking(plan_id):
            raise PatchNotValidError(f"plan {plan_id!r} has not passed validation")

        plan = self._patch_service.get(plan_id)
        generated_output = self._resolve_output(plan)

        # Every operation's location is confirmed present before any
        # mutation -- a missing location here fails the whole apply() with
        # nothing written.
        for operation in plan.operations:
            if _get_at_path(generated_output.output, operation["location"]) is _MISSING:
                raise ApplicationNotValidatedError(
                    f"plan {plan_id!r} targets {operation['location']!r}, which no longer exists "
                    "in the generated output"
                )

        original_values = tuple(
            (operation["location"], copy.deepcopy(_get_at_path(generated_output.output, operation["location"])))
            for operation in plan.operations
        )

        for operation in plan.operations:
            if operation["op"] == REPLACE:
                _set_at_path(generated_output.output, operation["location"], operation["value"])
            else:
                _delete_at_path(generated_output.output, operation["location"])

        changed_files = tuple(sorted({_top_level_key(operation["location"]) for operation in plan.operations}))

        self._execution_counter += 1
        now = datetime.now(timezone.utc)
        execution = LLMCodePatchExecution(
            execution_id=f"patch-execution-{plan_id}-{self._execution_counter}",
            plan_id=plan_id,
            status=SUCCEEDED,
            changed_files=changed_files,
            created_at=now,
            completed_at=now,
        )
        self._executions[execution.execution_id] = execution
        self._execution_id_by_plan[plan_id] = execution.execution_id
        self._original_values[execution.execution_id] = original_values
        return execution

    def _get(self, execution_id: str) -> LLMCodePatchExecution:
        try:
            return self._executions[execution_id]
        except KeyError:
            raise UnknownExecutionError(execution_id)

    def status(self, execution_id: str) -> str:
        return self._get(execution_id).status

    def get(self, execution_id: str) -> LLMCodePatchExecution:
        return self._get(execution_id)

    def rollback(self, execution_id: str) -> LLMCodePatchExecution:
        execution = self._get(execution_id)
        if execution.status != SUCCEEDED:
            raise InvalidRollbackStateError(
                f"execution {execution_id!r} cannot be rolled back from status {execution.status!r}"
            )

        plan = self._patch_service.get(execution.plan_id)
        generated_output = self._resolve_output(plan)
        original_values = self._original_values[execution_id]

        for location, _ in original_values:
            container, _ = _navigate_container(generated_output.output, location)
            if container is _MISSING:
                raise ApplicationNotValidatedError(
                    f"cannot rollback execution {execution_id!r}: {location!r} no longer exists"
                )

        for location, original_value in original_values:
            _set_at_path(generated_output.output, location, original_value)

        rolled_back = LLMCodePatchExecution(
            execution_id=execution.execution_id,
            plan_id=execution.plan_id,
            status=ROLLED_BACK,
            changed_files=execution.changed_files,
            created_at=execution.created_at,
            completed_at=datetime.now(timezone.utc),
        )
        self._executions[execution_id] = rolled_back
        return rolled_back
