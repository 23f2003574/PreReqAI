from typing import Callable

from .workspace_event import (
    WorkspaceEvent,
)

from .workspace_event_type import (
    WorkspaceEventType,
)

from .workspace_state import (
    WorkspaceState,
)


class WorkspaceStateCoordinator:
    """
    Coordinates state transitions
    across the visual research workspace.
    """

    def __init__(

        self,

        state: WorkspaceState,

    ):

        self.state = state

        self._handlers: dict[

            WorkspaceEventType,

            list[Callable],

        ] = {}

        self.event_history: list[
            WorkspaceEvent
        ] = []

    def subscribe(

        self,

        event_type: WorkspaceEventType,

        handler: Callable,

    ):

        handlers = (

            self._handlers.setdefault(

                event_type,

                [],
            )
        )

        if handler not in handlers:

            handlers.append(
                handler
            )

    def unsubscribe(

        self,

        event_type: WorkspaceEventType,

        handler: Callable,

    ):

        handlers = self._handlers.get(

            event_type,

            [],
        )

        if handler in handlers:

            handlers.remove(
                handler
            )

    def dispatch(

        self,

        event: WorkspaceEvent,

    ):

        self._apply_state_transition(
            event
        )

        self.event_history.append(
            event
        )

        for handler in list(

            self._handlers.get(

                event.event_type,

                [],
            )
        ):

            handler(
                event
            )

        return event

    def emit(

        self,

        event_type: WorkspaceEventType,

        payload=None,

        metadata=None,

    ):

        event = WorkspaceEvent(

            event_type=event_type,

            payload=payload,

            metadata=(

                metadata

                if metadata is not None

                else {}
            ),
        )

        return self.dispatch(
            event
        )

    def _apply_state_transition(

        self,

        event: WorkspaceEvent,

    ):

        if (

            event.event_type

            == WorkspaceEventType.PAPER_LOADED
        ):

            self.state.active_paper = (
                event.payload
            )

        elif (

            event.event_type

            == WorkspaceEventType.SECTION_SELECTED
        ):

            self.state.metadata[

                "selected_section"

            ] = event.payload

        elif (

            event.event_type

            == WorkspaceEventType.OBJECT_SELECTED
        ):

            self.state.selected_object = (
                event.payload
            )

        elif (

            event.event_type

            == WorkspaceEventType.GRAPH_NODE_SELECTED
        ):

            self.state.metadata[

                "selected_graph_node"

            ] = event.payload

        elif (

            event.event_type

            == WorkspaceEventType.VIEW_CHANGED
        ):

            self.state.active_view = str(
                event.payload
            )

        elif (

            event.event_type

            == WorkspaceEventType.LEARNING_CONTENT_PRESENTED
        ):

            self.state.metadata[

                "active_learning_content"

            ] = event.payload

        elif (

            event.event_type

            == WorkspaceEventType.HISTORY_UPDATED
        ):

            self.state.metadata[

                "interaction_history"

            ] = event.payload

        elif (

            event.event_type

            == WorkspaceEventType.RECOMMENDATIONS_UPDATED
        ):

            self.state.metadata[

                "recommendations"

            ] = event.payload
