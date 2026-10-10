from typing import Any


class ResearchRuntimeRegistry:
    """
    Stores runtime research entities
    by durable identifiers so persisted
    session references can be resolved.
    """

    def __init__(self):

        self._objects: dict[
            str,
            Any,
        ] = {}

        self._sections: dict[
            str,
            Any,
        ] = {}

        self._graph_nodes: dict[
            str,
            Any,
        ] = {}

    def register_object(

        self,

        research_object,

    ):

        object_id = str(
            research_object.id
        )

        self._objects[
            object_id
        ] = research_object

        return research_object

    def register_section(

        self,

        section,

    ):

        section_id = str(
            section.id
        )

        self._sections[
            section_id
        ] = section

        return section

    def register_graph_node(

        self,

        graph_node,

    ):

        node_id = str(
            graph_node.id
        )

        self._graph_nodes[
            node_id
        ] = graph_node

        return graph_node

    def register_objects(

        self,

        research_objects,

    ):

        for research_object in research_objects:

            self.register_object(
                research_object
            )

    def register_sections(

        self,

        sections,

    ):

        for section in sections:

            self.register_section(
                section
            )

    def register_graph_nodes(

        self,

        graph_nodes,

    ):

        for graph_node in graph_nodes:

            self.register_graph_node(
                graph_node
            )

    def get_object(

        self,

        object_id: str,

    ):

        return self._objects.get(
            str(object_id)
        )

    def get_section(

        self,

        section_id: str,

    ):

        return self._sections.get(
            str(section_id)
        )

    def get_graph_node(

        self,

        node_id: str,

    ):

        return self._graph_nodes.get(
            str(node_id)
        )

    def clear(self):

        self._objects.clear()

        self._sections.clear()

        self._graph_nodes.clear()
