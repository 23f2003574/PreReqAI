from dataclasses import (
    dataclass,
    field,
)

from .workspace_history_entry import (
    WorkspaceHistoryEntry,
)


@dataclass
class WorkspaceHistoryViewModel:
    """
    Represents the visual interaction
    history of the current research
    session.
    """

    entries: list[
        WorkspaceHistoryEntry
    ] = field(
        default_factory=list,
    )

    selected_entry_id: str | None = None
