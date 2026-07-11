from .breadcrumb_item import (
    BreadcrumbItem,
)

from .breadcrumb_trail import (
    BreadcrumbTrail,
)


class NavigationBreadcrumbs:
    """
    Coordinates the visible research
    navigation trail.
    """

    def __init__(self):

        self.trail = (
            BreadcrumbTrail()
        )

    def enter(

        self,

        id: str,

        label: str,

        context_type: str,

        source=None,

    ):

        item = BreadcrumbItem(

            id=id,

            label=label,

            context_type=context_type,

            source=source,
        )

        self.trail.push(
            item
        )

        return item

    def navigate_to(

        self,

        index: int,

    ):

        return self.trail.navigate_to(

            index
        )

    def items(self):

        return list(
            self.trail.items
        )
