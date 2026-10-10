import re

from backend.agent_execution_memory import LLMAgentMemoryService
from backend.agent_plan_execution import LLMAgentPlanExecutionService

from .in_memory_store import InMemoryLLMAgentMemoryFeedbackStore
from .models import MAX_RATING, MIN_RATING, VALID_FEEDBACK_TYPES, LLMAgentMemoryFeedback
from .store import LLMAgentMemoryFeedbackStore

# Same secret-detection convention already kept locally by
# backend.agent_execution_memory, backend.llm.project_context,
# backend.llm.tool_execution, backend.llm.tool_results,
# backend.llm.tool_audit, and backend.agent_execution_reporting -- kept
# local here too rather than refactoring any of those.
_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"AKIA[A-Z0-9]{12,}"),
    re.compile(r"(?i)bearer\s+\S+"),
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*\S+"),
    re.compile(r"^[A-Fa-f0-9]{32,}$"),
    re.compile(r"^[A-Za-z0-9+/]{40,}={0,2}$"),
)


def _looks_secret(value: str) -> bool:
    return any(pattern.search(value) for pattern in _SECRET_PATTERNS)


class UnknownAgentMemoryFeedbackError(KeyError):
    """Raised when get() is given a feedback_id that was never recorded."""


class InvalidFeedbackTypeError(ValueError):
    """Raised when feedback_type is not one of VALID_FEEDBACK_TYPES."""


class InvalidRatingError(ValueError):
    """Raised when rating is given but is not a number in [MIN_RATING, MAX_RATING]."""


class SecretFeedbackCommentError(ValueError):
    """Raised when comment appears to carry a secret, credential, or raw
    sensitive tool output."""


class LLMAgentMemoryFeedbackService:
    """Records explicit feedback about how a Commit #1 memory performed.

    Not a second feedback framework: persistence is the exact save/get/
    list_for_memory split backend.agent_execution_memory already uses (an
    InMemoryLLMAgentMemoryFeedbackStore by default, or the JSON-file-backed
    store built on the same backend.storage.AtomicJsonFile Commit #1
    itself uses), and comment is screened with the exact same
    secret-detection convention every other module here already keeps
    locally.

    record() never takes memory_id or execution_id on faith: it reads
    Commit #1's own LLMAgentMemoryService.get(memory_id) and Commit #12's
    own LLMAgentPlanExecutionService.get(execution_id), each propagating
    that service's own "unknown" error unchanged rather than a feedback-
    specific wrapper, so a caller sees exactly why the reference did not
    resolve. Neither call ever mutates what it reads -- record() only
    ever appends a new LLMAgentMemoryFeedback; it never adjusts
    memory_id's own content, outcome, or score. Feedback is an input for
    later learning, not a verified fact this service acts on by itself.

    There is no update() or remove(): every record() call for the same
    memory_id adds to that memory's feedback history rather than
    replacing an earlier judgment, so list_for_memory() always returns
    the complete, chronological trail.
    """

    def __init__(
        self,
        memory_service: LLMAgentMemoryService,
        plan_execution_service: LLMAgentPlanExecutionService,
        store: LLMAgentMemoryFeedbackStore = None,
    ):
        self._memory_service = memory_service
        self._plan_execution_service = plan_execution_service
        self.store = store if store is not None else InMemoryLLMAgentMemoryFeedbackStore()

    def record(self, memory_id: str, feedback: dict) -> LLMAgentMemoryFeedback:
        """Append one feedback record for memory_id.

        `feedback` carries execution_id, feedback_type, and optionally
        rating/comment. execution_id need not be the execution that
        produced memory_id -- it is whichever execution the memory was
        consulted for when this feedback was formed.

        Raises:
            UnknownAgentMemoryError: If memory_id was never recorded by
                Commit #1 (propagated, not wrapped)
            UnknownAgentPlanExecutionError: If execution_id was never
                recorded by Commit #12 (propagated, not wrapped)
            InvalidFeedbackTypeError, InvalidRatingError,
            SecretFeedbackCommentError: If feedback itself fails validation
        """
        # Existence checks only -- neither call mutates memory_id or
        # execution_id, and this service never re-derives feedback_type/
        # rating from what they return the way Commit #1's own outcome is
        # derived from a verified execution status. A human or upstream
        # process's judgment is recorded as given, not second-guessed.
        self._memory_service.get(memory_id)
        execution_id = feedback.get("execution_id")
        self._plan_execution_service.get(execution_id)

        feedback_type = feedback.get("feedback_type")
        rating = feedback.get("rating")
        comment = feedback.get("comment", "")

        self._validate_feedback_type(feedback_type)
        self._validate_rating(rating)
        self._validate_comment(comment)

        record = LLMAgentMemoryFeedback(
            memory_id=memory_id,
            execution_id=execution_id,
            feedback_type=feedback_type,
            rating=rating,
            comment=comment,
        )
        return self.store.save(record)

    def get(self, feedback_id: str) -> LLMAgentMemoryFeedback:
        record = self.store.get(feedback_id)
        if record is None:
            raise UnknownAgentMemoryFeedbackError(feedback_id)
        return record

    def list_for_memory(self, memory_id: str) -> list:
        """Every feedback record for memory_id, oldest first -- the
        complete history, never collapsed to a single latest judgment."""
        return self.store.list_for_memory(memory_id)

    @staticmethod
    def _validate_feedback_type(feedback_type):
        if feedback_type not in VALID_FEEDBACK_TYPES:
            raise InvalidFeedbackTypeError(
                f"feedback_type {feedback_type!r} is not one of {sorted(VALID_FEEDBACK_TYPES)}"
            )

    @staticmethod
    def _validate_rating(rating):
        if rating is None:
            return
        if isinstance(rating, bool) or not isinstance(rating, (int, float)):
            raise InvalidRatingError(f"rating {rating!r} must be a number")
        if not (MIN_RATING <= rating <= MAX_RATING):
            raise InvalidRatingError(f"rating {rating!r} must be between {MIN_RATING} and {MAX_RATING}")

    @staticmethod
    def _validate_comment(comment):
        if not isinstance(comment, str):
            raise ValueError("comment must be a string")
        if _looks_secret(comment):
            raise SecretFeedbackCommentError(
                "comment appears to contain a secret, credential, or raw sensitive "
                "tool output and cannot be stored"
            )
