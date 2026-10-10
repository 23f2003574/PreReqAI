from frontend.src.workspace import (

    WorkspaceEventType,

    WorkspaceState,

    WorkspaceStateCoordinator,
)


def test_coordinator_updates_workspace_state():

    state = (
        WorkspaceState()
    )

    coordinator = (

        WorkspaceStateCoordinator(

            state
        )
    )

    coordinator.emit(

        WorkspaceEventType.VIEW_CHANGED,

        payload="knowledge_graph",
    )

    assert (

        state.active_view

        == "knowledge_graph"
    )


def test_coordinator_records_events():

    state = (
        WorkspaceState()
    )

    coordinator = (

        WorkspaceStateCoordinator(

            state
        )
    )

    coordinator.emit(

        WorkspaceEventType.VIEW_CHANGED,

        payload="learning",
    )

    assert (

        len(
            coordinator.event_history
        )

        == 1
    )

    assert (

        coordinator
        .event_history[0]
        .event_type

        == WorkspaceEventType.VIEW_CHANGED
    )


def test_coordinator_notifies_subscribers():

    state = (
        WorkspaceState()
    )

    coordinator = (

        WorkspaceStateCoordinator(

            state
        )
    )

    received = []

    def handler(event):

        received.append(
            event
        )

    coordinator.subscribe(

        WorkspaceEventType.OBJECT_SELECTED,

        handler,
    )

    research_object = {

        "id": "attention"
    }

    coordinator.emit(

        WorkspaceEventType.OBJECT_SELECTED,

        payload=research_object,
    )

    assert (

        state.selected_object

        == research_object
    )

    assert (

        len(received)

        == 1
    )


def test_coordinator_unsubscribes_handlers():

    state = (
        WorkspaceState()
    )

    coordinator = (

        WorkspaceStateCoordinator(

            state
        )
    )

    received = []

    def handler(event):

        received.append(
            event
        )

    coordinator.subscribe(

        WorkspaceEventType.VIEW_CHANGED,

        handler,
    )

    coordinator.unsubscribe(

        WorkspaceEventType.VIEW_CHANGED,

        handler,
    )

    coordinator.emit(

        WorkspaceEventType.VIEW_CHANGED,

        payload="learning",
    )

    assert received == []
