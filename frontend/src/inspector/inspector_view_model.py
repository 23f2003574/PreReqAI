from dataclasses import (
    dataclass,
    field,
)

from .inspector_field import (
    InspectorField,
)


@dataclass
class InspectorViewModel:
    """
    Represents the visual information
    displayed for a selected research
    object.
    """

    object_id: str

    title: str

    object_type: str

    description: str

    fields: list[
        InspectorField
    ] = field(
        default_factory=list,
    )

    actions: list[str] = field(
        default_factory=list,
    )
