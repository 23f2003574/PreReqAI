from backend.interaction import (
    ObjectAction,
)

from .action_menu_item import (
    ActionMenuItem,
)


class ObjectActionMenu:
    """
    Builds and executes educational
    actions for selected research
    objects.
    """

    def __init__(

        self,

        interaction_engine,

    ):

        self.interaction_engine = (
            interaction_engine
        )

    def build(

        self,

        research_object,

    ):

        return [

            ActionMenuItem(

                action=action,

                label=(

                    action.value
                    .replace("_", " ")
                    .title()
                ),

            )

            for action

            in research_object
            .available_actions()
        ]

    def execute(

        self,

        session,

        research_object,

        action: ObjectAction,

    ):

        if (

            action

            not in research_object
            .available_actions()
        ):

            raise ValueError(

                f"Action '{action.value}' "
                "is not supported by "
                f"'{research_object.title}'."
            )

        return (

            self.interaction_engine.interact(

                session,

                research_object,

                action,
            )
        )
