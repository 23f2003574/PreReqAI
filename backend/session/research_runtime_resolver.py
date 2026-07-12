from .research_runtime_registry import (
    ResearchRuntimeRegistry,
)


class ResearchRuntimeResolver:
    """
    Resolves durable session identifiers
    into currently available runtime
    research entities.
    """

    def __init__(

        self,

        registry:
            ResearchRuntimeRegistry,

    ):

        self.registry = registry

    def resolve_object(

        self,

        object_id: str | None,

    ):

        if object_id is None:

            return None

        return self.registry.get_object(
            object_id
        )

    def resolve_section(

        self,

        section_id: str | None,

    ):

        if section_id is None:

            return None

        return self.registry.get_section(
            section_id
        )

    def resolve_graph_node(

        self,

        node_id: str | None,

    ):

        if node_id is None:

            return None

        return self.registry.get_graph_node(
            node_id
        )
