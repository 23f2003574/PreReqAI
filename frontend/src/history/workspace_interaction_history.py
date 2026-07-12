from .workspace_history_entry import (
    WorkspaceHistoryEntry,
)

from .workspace_history_view_model import (
    WorkspaceHistoryViewModel,
)


class WorkspaceInteractionHistory:
    """
    Transforms backend interaction
    events into navigable workspace
    history entries.
    """

    def __init__(

        self,

        correlation_provider=None,

    ):

        self.correlation_provider = (
            correlation_provider
        )

        self.view_model = (
            WorkspaceHistoryViewModel()
        )

    def load(

        self,

        interaction_history,

    ) -> WorkspaceHistoryViewModel:

        entries = [

            self._build_entry(

                event,

                index,
            )

            for index, event

            in enumerate(
                interaction_history.events
            )
        ]

        self.view_model = (

            WorkspaceHistoryViewModel(

                entries=entries
            )
        )

        return self.view_model

    def append(

        self,

        event,

    ):

        entry = self._build_entry(

            event,

            len(
                self.view_model.entries
            ),
        )

        self.view_model.entries.append(
            entry
        )

        return entry

    def select(

        self,

        entry_id: str,

    ):

        selected = None

        for entry in (

            self.view_model.entries
        ):

            entry.selected = (

                entry.id == entry_id
            )

            if entry.selected:

                selected = entry

        self.view_model.selected_entry_id = (

            entry_id

            if selected

            else None
        )

        return selected

    def _build_entry(

        self,

        event,

        index: int,

    ):

        action = (

            event.action.value

            if hasattr(

                event.action,

                "value",
            )

            else str(
                event.action
            )
        )

        interaction_id = getattr(

            event,

            "id",

            None,
        )

        if interaction_id is None:

            interaction_id = (

                f"{event.object_id}:"
                f"{action}:"
                f"{index + 1}"
            )

        artifact_ids = []

        if self.correlation_provider is not None:

            links = (

                self.correlation_provider
                .links_for_interaction(

                    str(
                        interaction_id
                    )
                )
            )

            artifact_ids = [

                link.artifact_id

                for link in links
            ]

        return WorkspaceHistoryEntry(

            id=str(
                interaction_id
            ),

            object_id=(
                event.object_id
            ),

            object_title=(
                event.object_title
            ),

            action=action,

            timestamp=(
                event.timestamp
            ),

            artifact_ids=artifact_ids,

            source=event,
        )
