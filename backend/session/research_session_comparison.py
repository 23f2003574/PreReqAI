from dataclasses import (
    dataclass,
    field,
)

from .research_state_change import (
    ResearchStateChange,
)


@dataclass
class ResearchSessionComparison:
    """
    Contains meaningful differences
    between the current research state
    and a target historical state.
    """

    changes: list[
        ResearchStateChange
    ] = field(
        default_factory=list,
    )

    @property
    def has_changes(self) -> bool:

        return bool(
            self.changes
        )

    @property
    def change_count(self) -> int:

        return len(
            self.changes
        )

    def changed_fields(self):

        return [

            change.field

            for change

            in self.changes
        ]

    def to_dict(self):

        return {

            "has_changes":
                self.has_changes,

            "change_count":
                self.change_count,

            "changed_fields":
                self.changed_fields(),

            "changes": [

                change.to_dict()

                for change

                in self.changes
            ],
        }
