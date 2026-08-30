import json
import re
from datetime import datetime, timezone

from ..context import LLMContextItem
from ..evaluation_cases import LLMEvaluationCaseService
from ..orchestration import LLMRequestOrchestrationService
from ..routing import LLMRouteRequest
from .models import FAILED, SUCCEEDED, LLMEvaluationRun

# Same secret-redaction convention already used by backend.llm.tool_results,
# backend.llm.tool_execution, backend.transformation_audit, and
# backend.api_recommendation_export. Kept local, as those modules keep their
# own copies, rather than refactoring them here.
_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"AKIA[A-Z0-9]{12,}"),
    re.compile(r"(?i)bearer\s+\S+"),
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*\S+"),
    re.compile(r"^[A-Fa-f0-9]{32,}$"),
    re.compile(r"^[A-Za-z0-9+/]{40,}={0,2}$"),
)

_REDACTED = "[REDACTED]"


def _redact(value):
    if value is None:
        return None
    for pattern in _SECRET_PATTERNS:
        if pattern.search(value):
            return _REDACTED
    return value


class DisabledEvaluationCaseError(ValueError):
    """Raised when run() is called for a case that exists but is disabled."""


class UnknownEvaluationRunError(KeyError):
    """Raised when looking up a run_id that was never recorded."""


class LLMEvaluationRunService:
    """Executes a Commit #1 evaluation case through the existing LLM pipeline.

    Reuses backend.llm.orchestration.LLMRequestOrchestrationService for the
    call itself (routing, context, budgets, caching, retry, fallback, usage,
    cost, auditing all stay exactly what that service already does) and
    backend.llm.context.LLMContextService to carry the case's input in --
    the same way backend.notebook_analysis.LLMNotebookAnalysisService turns
    its own input into a single "user" context item. No second execution
    path, and no scoring: run() only captures what came back for later
    commits to score.
    """

    def __init__(
        self,
        orchestration_service: LLMRequestOrchestrationService,
        context_service,
        case_service: LLMEvaluationCaseService,
        required_capabilities=("chat",),
    ):
        self._orchestration_service = orchestration_service
        self._context_service = context_service
        self._case_service = case_service
        self._required_capabilities = list(required_capabilities)
        self._runs = {}
        self._history = {}
        self._run_counter = 0

    def run(self, case_id: str) -> LLMEvaluationRun:
        case = self._case_service.get(case_id)
        if not case.enabled:
            raise DisabledEvaluationCaseError(f"case {case_id!r} is disabled")

        self._run_counter += 1
        run_id = f"eval-run-{self._run_counter}"
        request_id = f"{run_id}-{case_id}"

        route_request = LLMRouteRequest(
            task=case.task_type, required_capabilities=list(self._required_capabilities)
        )

        self._context_service.create(request_id)
        self._context_service.add(
            request_id,
            LLMContextItem(
                type="user", content=json.dumps(case.input, sort_keys=True), priority=1
            ),
        )

        started_at = datetime.now(timezone.utc)
        response, decision = self._orchestration_service.execute(
            route_request, request_id, request_id, temperature=0.0
        )
        completed_at = datetime.now(timezone.utc)

        run = LLMEvaluationRun(
            run_id=run_id,
            case_id=case_id,
            request_id=request_id,
            provider=decision.provider,
            model=decision.model,
            output=_redact(response.content) if response is not None else None,
            status=SUCCEEDED if response is not None else FAILED,
            started_at=started_at,
            completed_at=completed_at,
        )

        self._runs[run_id] = run
        self._history.setdefault(case_id, []).append(run_id)
        return run

    def get(self, run_id: str) -> LLMEvaluationRun:
        try:
            return self._runs[run_id]
        except KeyError:
            raise UnknownEvaluationRunError(run_id)

    def history(self, case_id: str) -> list:
        """All runs recorded for a case_id, in the order they were executed."""
        return [self._runs[run_id] for run_id in self._history.get(case_id, [])]
