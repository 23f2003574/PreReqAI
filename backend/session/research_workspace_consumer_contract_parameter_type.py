from enum import (
    Enum,
)


class ResearchWorkspaceConsumerContractParameterType(
    str,
    Enum,
):
    """
    Describes the transport-independent
    logical type of a consumer contract
    parameter.
    """

    STRING = (
        "string"
    )

    INTEGER = (
        "integer"
    )

    BOOLEAN = (
        "boolean"
    )

    ENUM = (
        "enum"
    )

    ENTITY_ID = (
        "entity_id"
    )
