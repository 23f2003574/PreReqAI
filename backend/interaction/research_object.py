from dataclasses import (
    dataclass,
    field,
)

from .object_action import (
    ObjectAction,
)
from .object_capabilities import (
    get_capabilities,
)
from .research_object_type import (
    ResearchObjectType,
)


@dataclass
class ResearchObject:
    """
    Represents an interactive object
    inside a research paper.
    """

    id: str

    object_type: ResearchObjectType

    title: str

    description: str

    metadata: dict = field(
        default_factory=dict,
    )

    def available_actions(
        self,
    ) -> list[ObjectAction]:
        """
        Lets callers ask the object what it
        supports instead of the caller having
        to know the object type.
        """

        return get_capabilities(
            self.object_type
        )

    def supports(
        self, action: ObjectAction
    ) -> bool:

        return (
            action
            in self.available_actions()
        )
