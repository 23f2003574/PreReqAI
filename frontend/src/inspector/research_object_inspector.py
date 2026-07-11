from .inspector_field import (
    InspectorField,
)

from .inspector_view_model import (
    InspectorViewModel,
)


class ResearchObjectInspector:
    """
    Builds contextual inspection data
    for selected research objects.
    """

    def inspect(

        self,

        research_object,

    ) -> InspectorViewModel:

        fields = [

            InspectorField(

                label=key,

                value=value,
            )

            for key, value

            in research_object
            .metadata
            .items()
        ]

        actions = [

            action.value

            for action

            in research_object
            .available_actions()
        ]

        return InspectorViewModel(

            object_id=(
                research_object.id
            ),

            title=(
                research_object.title
            ),

            object_type=(

                research_object
                .object_type
                .value
            ),

            description=(

                research_object
                .description
            ),

            fields=fields,

            actions=actions,
        )
