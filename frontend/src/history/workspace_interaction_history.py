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

    def __init__(self):

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

    @staticmethod
    def _build_entry(

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

        return WorkspaceHistoryEntry(

            id=(

                f"{event.object_id}:"
                f"{action}:"
                f"{index + 1}"
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

            source=event,
        )
