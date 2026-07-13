from dataclasses import (
    dataclass,
)

from typing import Any


@dataclass
class ResearchSessionStateDifference:
    """
    Represents one differing field
    between two research sessions.
    """

    field_name: str

    first_value: Any

    second_value: Any

    def to_dict(self):

        return {

            "field_name":
                self.field_name,

            "first_value":
                self.first_value,

            "second_value":
                self.second_value,
        }
