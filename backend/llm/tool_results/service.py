import dataclasses
import json
import re
from datetime import date, datetime

from ..context import LLMContextItem, estimate_text_tokens
from ..tool_execution import STATUSES, SUCCEEDED, LLMToolExecution
from .models import (
    DEFAULT_OUTPUT_TOKEN_BUDGET,
    TOOL_ROLE,
    InvalidToolResultError,
    LLMToolResult,
)

# Same secret-redaction convention used by backend.transformation_audit,
# backend.api_recommendation_export, and backend.llm.tool_execution.
_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"AKIA[A-Z0-9]{12,}"),
    re.compile(r"(?i)bearer\s+\S+"),
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*\S+"),
    re.compile(r"^[A-Fa-f0-9]{32,}$"),
    re.compile(r"^[A-Za-z0-9+/]{40,}={0,2}$"),
)

_REDACTED = "[REDACTED]"

# The truncation envelope is deliberately fixed and compact -- the numbers
# behind it live in the result's metadata, so the envelope's own size does
# not vary with them. That makes the smallest output this service can ever
# emit a constant, and therefore the smallest budget it can honour a
# derived value rather than a guessed one.
_TRUNCATION_REASON = "output exceeds token budget"


def _redact(value: str) -> str:
    for pattern in _SECRET_PATTERNS:
        if pattern.search(value):
            return _REDACTED
    return value


def _looks_secret(value: str) -> bool:
    return any(pattern.search(value) for pattern in _SECRET_PATTERNS)


_EMPTY_TRUNCATION_ENVELOPE = {
    "truncated": True,
    "reason": _TRUNCATION_REASON,
    "preview": "",
}

# The floor a token_budget must clear for this service to be able to honour
# it, measured with the project's own estimator against the smallest output
# it can emit.
MINIMUM_OUTPUT_TOKEN_BUDGET = estimate_text_tokens(
    json.dumps(_EMPTY_TRUNCATION_ENVELOPE, sort_keys=True, indent=2, default=str)
)


class LLMToolResultService:
    """Turns a Commit #5 execution record into context an LLM can safely read.

    Reuses rather than re-invents at every step:

        backend.llm.tool_execution  -- the record and its status vocabulary;
                                       nothing here re-runs a tool, and the
                                       service holds no handler to run one with
        backend.llm.context         -- LLMContextItem is the context protocol,
                                       and estimate_text_tokens is the project's
                                       own measure of size
        backend.serialization       -- the project's dataclasses.asdict() ->
                                       json.dumps(sort_keys=True) convention,
                                       as used by backend.api_recommendation_export

    Size is enforced the way LLMContextService.build already enforces it:
    against a token budget, using the same estimator. Where build() drops an
    over-budget item outright, an over-budget tool output is replaced by a
    preview plus an explicit truncation flag -- an LLM that asked for a tool
    result must be told one came back, and told that it was trimmed.
    """

    def __init__(self, token_budget: int = DEFAULT_OUTPUT_TOKEN_BUDGET):
        if not isinstance(token_budget, int) or isinstance(token_budget, bool) or token_budget <= 0:
            raise InvalidToolResultError("token_budget must be a positive integer")
        if token_budget < MINIMUM_OUTPUT_TOKEN_BUDGET:
            raise InvalidToolResultError(
                f"token_budget must be at least {MINIMUM_OUTPUT_TOKEN_BUDGET}: below "
                "that, even a bare truncation notice would not fit, so normalize() "
                "could produce a result validate() must refuse"
            )
        self._token_budget = token_budget

    @property
    def token_budget(self) -> int:
        return self._token_budget

    # -- normalization ----------------------------------------------------

    @classmethod
    def _json_safe(cls, value):
        """Convert a tool's return value to JSON-safe form, redacting strings.

        Follows the project's serialization convention: dataclasses via
        dataclasses.asdict, datetimes via isoformat, and anything with no
        JSON representation rendered as its str() -- which is then redacted
        like any other string.
        """
        if value is None or isinstance(value, (bool, int, float)):
            return value

        if isinstance(value, str):
            return _redact(value)

        if isinstance(value, (datetime, date)):
            return value.isoformat()

        if dataclasses.is_dataclass(value) and not isinstance(value, type):
            return cls._json_safe(dataclasses.asdict(value))

        if isinstance(value, dict):
            return {
                str(_redact(str(key))): cls._json_safe(item) for key, item in value.items()
            }

        if isinstance(value, (list, tuple, set, frozenset)):
            return [cls._json_safe(item) for item in value]

        return _redact(str(value))

    @staticmethod
    def _render(payload) -> str:
        """The project's JSON rendering convention, used for every measurement."""
        return json.dumps(payload, sort_keys=True, indent=2, default=str)

    def _truncated_output(self, rendered: str) -> dict:
        """An over-budget output replaced by a preview that does fit."""
        envelope = dict(_EMPTY_TRUNCATION_ENVELOPE)

        overhead = estimate_text_tokens(self._render(envelope))
        keep_chars = max(0, (self._token_budget - overhead) * 4)

        while True:
            envelope["preview"] = rendered[:keep_chars]
            if keep_chars == 0:
                return dict(envelope)
            if estimate_text_tokens(self._render(envelope)) <= self._token_budget:
                return dict(envelope)
            keep_chars = keep_chars * 3 // 4

    def normalize(self, execution) -> LLMToolResult:
        """Present one execution record as a structured, LLM-safe result.

        Reads the record only -- no tool is invoked, and none can be: this
        service holds no registry, no permissions, and no handlers.
        """
        if not isinstance(execution, LLMToolExecution):
            raise TypeError(
                f"Cannot normalize something that is not an LLMToolExecution: {execution!r}."
            )

        metadata = {
            "tool_name": _redact(execution.tool_name),
            "plan_id": _redact(execution.plan_id),
            "truncated": False,
        }

        if execution.status != SUCCEEDED:
            # A refused or failed call carries no output, only a reason. The
            # execution's error was already redacted by Commit #5; redacting
            # again is idempotent and keeps this service safe on its own.
            return LLMToolResult(
                execution_id=execution.execution_id,
                status=execution.status,
                output=None,
                error=_redact(execution.error or execution.status),
                metadata=metadata,
                completed_at=execution.completed_at,
            )

        output = self._json_safe(execution.result)
        rendered = self._render(output)
        estimated = estimate_text_tokens(rendered)
        metadata["estimated_tokens"] = estimated

        if estimated > self._token_budget:
            # Same budget discipline as LLMContextService.build, with a
            # preview kept so the model still learns what came back. The
            # preview is sized against the budget that is left once the
            # envelope around it has been measured, then shrunk until the
            # whole thing fits -- JSON escaping can expand a string, so the
            # first estimate is a ceiling, not an answer.
            output = self._truncated_output(rendered)
            metadata["truncated"] = True
            metadata["original_estimated_tokens"] = estimated
            metadata["token_budget"] = self._token_budget
            metadata["estimated_tokens"] = estimate_text_tokens(self._render(output))

        return LLMToolResult(
            execution_id=execution.execution_id,
            status=execution.status,
            output=output,
            error=None,
            metadata=metadata,
            completed_at=execution.completed_at,
        )

    # -- validation -------------------------------------------------------

    @classmethod
    def _secret_leaves(cls, value) -> bool:
        if isinstance(value, str):
            return _looks_secret(value)
        if isinstance(value, dict):
            return any(
                cls._secret_leaves(key) or cls._secret_leaves(item)
                for key, item in value.items()
            )
        if isinstance(value, (list, tuple)):
            return any(cls._secret_leaves(item) for item in value)
        return False

    def validate(self, result) -> bool:
        """Whether a result may enter LLM context. Raises if it may not."""
        if not isinstance(result, LLMToolResult):
            raise InvalidToolResultError(
                f"Not an LLMToolResult: {result!r}."
            )

        if not result.execution_id or not isinstance(result.execution_id, str):
            raise InvalidToolResultError("execution_id is required")

        if result.status not in STATUSES:
            raise InvalidToolResultError(
                f"status {result.status!r} is not one of {sorted(STATUSES)}"
            )

        if not isinstance(result.metadata, dict):
            raise InvalidToolResultError("metadata must be a dict")

        if result.status == SUCCEEDED:
            if result.error is not None:
                raise InvalidToolResultError("a succeeded result must carry no error")
        else:
            if result.output is not None:
                raise InvalidToolResultError(
                    f"a {result.status} result must carry no output"
                )
            if not result.error or not isinstance(result.error, str):
                raise InvalidToolResultError(
                    f"a {result.status} result must explain itself with an error"
                )

        try:
            rendered = self._render(result.output)
        except (TypeError, ValueError) as exc:
            raise InvalidToolResultError(f"output is not serializable: {exc}")

        if self._secret_leaves(result.output) or (
            result.error is not None and _looks_secret(result.error)
        ):
            raise InvalidToolResultError(
                "result still contains something that looks like a credential"
            )

        estimated = estimate_text_tokens(rendered)
        if estimated > self._token_budget:
            raise InvalidToolResultError(
                f"output of {estimated} estimated tokens exceeds the "
                f"{self._token_budget}-token budget"
            )

        return True

    # -- context ----------------------------------------------------------

    def context(self, result, priority: int = 0) -> LLMContextItem:
        """The result as an LLMContextItem, ready for LLMContextService.add.

        Always validates first: an invalid result never becomes context.
        Returns the existing context protocol's own type rather than a new
        one, so the item goes straight into LLMContextService and comes out
        of build() as a {"role": "tool", "content": ...} message.
        """
        self.validate(result)

        payload = {
            "execution_id": result.execution_id,
            "status": result.status,
            "tool": result.metadata.get("tool_name"),
        }
        if result.status == SUCCEEDED:
            payload["output"] = result.output
            if result.metadata.get("truncated"):
                payload["truncated"] = True
        else:
            payload["error"] = result.error

        return LLMContextItem(
            type=TOOL_ROLE,
            content=self._render(payload),
            priority=priority,
        )
