from dataclasses import (
    dataclass,
    field,
)

from typing import (
    Callable,
)


@dataclass
class ResearchWorkspaceSubscription:
    """
    Represents one in-process subscription
    to workspace change events.
    """

    subscription_id: str

    callback: Callable

    entity_types: set[
        str
    ] = field(
        default_factory=set,
    )

    operations: set[
        str
    ] = field(
        default_factory=set,
    )

    active: bool = True

    def matches(

        self,

        event,

    ):

        if not self.active:

            return False

        if (

            self.entity_types

            and

            event.entity_type

            not in self.entity_types
        ):

            return False

        if (

            self.operations

            and

            event.operation.value

            not in self.operations
        ):

            return False

        return True
