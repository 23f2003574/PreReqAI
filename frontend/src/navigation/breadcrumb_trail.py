from dataclasses import (
    dataclass,
    field,
)

from .breadcrumb_item import (
    BreadcrumbItem,
)


@dataclass
class BreadcrumbTrail:
    """
    Represents the learner's current
    hierarchical research path.
    """

    items: list[
        BreadcrumbItem
    ] = field(
        default_factory=list,
    )

    def push(

        self,

        item: BreadcrumbItem,

    ):

        existing_index = next(

            (

                index

                for index, current

                in enumerate(
                    self.items
                )

                if (

                    current.id
                    == item.id

                    and

                    current.context_type
                    == item.context_type
                )
            ),

            None,
        )

        if existing_index is not None:

            self.items = (

                self.items[
                    :existing_index + 1
                ]
            )

            return

        self.items.append(
            item
        )

    def navigate_to(

        self,

        index: int,

    ):

        if (

            index < 0

            or index >= len(
                self.items
            )
        ):

            raise IndexError(

                "Breadcrumb index "
                "is out of range."
            )

        selected = (

            self.items[index]
        )

        self.items = (

            self.items[
                :index + 1
            ]
        )

        return selected

    def clear(self):

        self.items.clear()

    @property
    def current(self):

        if not self.items:

            return None

        return self.items[-1]
