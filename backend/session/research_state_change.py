from dataclasses import (
    asdict,
    dataclass,
)

from typing import Any

from .research_state_change_type import (
    ResearchStateChangeType,
)


@dataclass
class ResearchStateChange:
    """
    Represents one meaningful difference
    between two research session states.
    """

    field: str

    change_type: (
        ResearchStateChangeType
    )

    current_value: Any

    target_value: Any

    added_values: (
        list[Any] | None
    ) = None

    removed_values: (
        list[Any] | None
    ) = None

    def to_dict(self):

        data = asdict(self)

        data["change_type"] = (
            self.change_type.value
        )

        return data
