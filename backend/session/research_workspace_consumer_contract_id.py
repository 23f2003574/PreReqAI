from enum import (
    Enum,
)


class ResearchWorkspaceConsumerContractId(
    str,
    Enum,
):
    """
    Identifies a stable, transport-
    independent consumer read contract
    exposed by the research workspace.
    """

    WORKSPACE_CAPABILITIES = (
        "workspace.capabilities"
    )

    WORKSPACE_READINESS = (
        "workspace.readiness"
    )

    WORKSPACE_BOOTSTRAP = (
        "workspace.bootstrap"
    )

    WORKSPACE_ATTENTION = (
        "workspace.attention"
    )

    WORKSPACE_ACTIONS = (
        "workspace.actions"
    )

    SESSION_ACTIONS = (
        "session.actions"
    )
