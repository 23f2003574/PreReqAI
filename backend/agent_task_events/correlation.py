from .models import CORRELATION_ESTABLISHED, AgentTaskEvent
from .query import LLMAgentTaskEventQueryService
from .service import LLMAgentTaskEventService


class InvalidAgentTaskEventCorrelationError(ValueError):
    """Raised when correlate()/get_related()/get_children() is given
    invalid arguments."""


class LLMAgentTaskEventCorrelationService:
    """Traces related events from one logical task operation together --
    not a second, competing tracing system (Rule: "Do not introduce
    distributed tracing infrastructure" / "Do not invent a parallel
    tracing system"): there is no span registry, no ACTIVE/COMPLETED
    lifecycle, and no store of its own here, the way
    backend.session.execution_trace_service.ExecutionTraceService keeps
    for its own spans -- this service only ever reads and writes through
    Commit #1's own LLMAgentTaskEventService/Commit #2's own
    LLMAgentTaskEventQueryService, over the three plain reference fields
    Commit #4 added directly to AgentTaskEvent
    (correlation_id/parent_event_id/operation_id).

    correlate() is this service's one mutating operation (Rule: "Read/
    query operations remain read-only" -- get_related()/get_children()
    are the read/query operations that rule describes; correlate() is
    deliberately not one of them): it appends a lightweight
    CORRELATION_ESTABLISHED marker event for task_id carrying
    correlation_id, via Commit #1's own emit() -- never a second event
    store, and never a payload (Rule: "Correlation metadata must
    reference events/operations, not duplicate payloads" -- correlation_id
    itself is the only thing this marker event carries beyond what any
    other emit() call already would).

    Any event -- not only a CORRELATION_ESTABLISHED marker -- can carry a
    correlation_id/parent_event_id by passing them directly to Commit #1's
    own emit(); get_related()/get_children() find all of them, not only
    ones created via correlate().

    get_related()/get_children() never scan a second store: both read
    through query_service.query() (Commit #2's own store.all() path,
    already in Commit #1's own append order with Commit #2's own
    deterministic tie-break) and then apply one more equality filter on
    top, the same "the store/query layer owns ordering, this layer only
    adds one more predicate" split Commit #2 itself already established
    for event_types/time-range filtering.

    query_service defaults to a fresh LLMAgentTaskEventQueryService bound
    to event_service's own store, so correlate()'s writes are always
    visible to get_related()/get_children() by default. Passing both
    explicitly is the caller's responsibility to keep pointed at the same
    store -- the same "no usable zero-argument default when the caller
    overrides one collaborator without the other" discipline this
    project's other composed services already require.
    """

    def __init__(
        self,
        event_service: LLMAgentTaskEventService = None,
        query_service: LLMAgentTaskEventQueryService = None,
    ):
        self._event_service = event_service if event_service is not None else LLMAgentTaskEventService()
        self._query_service = (
            query_service
            if query_service is not None
            else LLMAgentTaskEventQueryService(store=self._event_service.store)
        )

    def correlate(self, task_id: str, correlation_id: str) -> AgentTaskEvent:
        """Emit a CORRELATION_ESTABLISHED event for task_id carrying
        correlation_id -- the mechanism by which later get_related() calls
        can find it, and by which other emit() calls for the same or a
        different task_id can be tied to the same logical operation by
        passing the same correlation_id themselves.

        Raises:
            InvalidAgentTaskEventCorrelationError: If correlation_id is
                not a non-empty string
            InvalidAgentTaskEventError: If task_id is not a non-empty
                string (Commit #1's own emit()/error, propagated
                unchanged)
        """
        self._require_text(correlation_id, "correlation_id")
        return self._event_service.emit(task_id, CORRELATION_ESTABLISHED, correlation_id=correlation_id)

    def get_related(self, correlation_id: str) -> list:
        """Every persisted event carrying correlation_id, across every
        task, in the same chronological order Commit #2's own query()
        already guarantees. An empty list when nothing matches -- this
        service holds no opinion on whether correlation_id was ever
        actually established.

        Raises:
            InvalidAgentTaskEventCorrelationError: If correlation_id is
                not a non-empty string
        """
        self._require_text(correlation_id, "correlation_id")
        events = self._query_service.query()
        return [event for event in events if event.correlation_id == correlation_id]

    def get_children(self, event_id: str) -> list:
        """Every persisted event whose parent_event_id is event_id,
        across every task, in the same chronological order Commit #2's
        own query() already guarantees. An empty list when event_id has
        no recorded children -- this service holds no opinion on whether
        event_id itself was ever actually recorded.

        Raises:
            InvalidAgentTaskEventCorrelationError: If event_id is not a
                non-empty string
        """
        self._require_text(event_id, "event_id")
        events = self._query_service.query()
        return [event for event in events if event.parent_event_id == event_id]

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskEventCorrelationError(
                f"{field_name} is required and must be a non-empty string"
            )
