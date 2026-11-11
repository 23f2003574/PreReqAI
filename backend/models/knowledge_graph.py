from dataclasses import dataclass, field


@dataclass
class GraphNode:

    node_id: str

    node_type: str

    label: str


@dataclass
class GraphEdge:

    source: str

    target: str

    relationship: str


@dataclass
class KnowledgeGraph:

    nodes: list[GraphNode] = field(default_factory=list)

    edges: list[GraphEdge] = field(default_factory=list)

    def add_node(
        self,
        node: GraphNode,
    ):

        self.nodes.append(node)

    def add_edge(
        self,
        edge: GraphEdge,
    ):

        # A self-loop is a malformed relationship: it would make a concept its own prerequisite.
        if edge.source == edge.target:

            raise ValueError(f"Graph edge cannot connect {edge.source!r} to itself")

        # A prerequisite cycle (A needs B needs A) has no valid study order. Only "depends_on" edges are prerequisites: a
        # "co_occurs_with" edge is naturally mutual. The error names the whole cycle so the bad relationship can be found.
        if edge.relationship == "depends_on":

            route = self._prerequisite_route(edge.target, edge.source)

            if route is not None:

                cycle = " -> ".join(node.replace("concept:", "") for node in [edge.source, *route])

                raise ValueError(f"Graph edge {edge.source!r} -> {edge.target!r} would create a prerequisite cycle: {cycle}")

        self.edges.append(edge)

    def _prerequisite_route(self, start: str, goal: str) -> list[str] | None:
        """The nodes from `start` to `goal` (both included) along existing "depends_on" edges, or None when there is no route."""

        parents, pending = {start: None}, [start]

        while pending:

            node = pending.pop()

            if node == goal:

                route = []

                while node is not None:

                    route.append(node)
                    node = parents[node]

                return route[::-1]

            for edge in self.edges:

                if edge.relationship == "depends_on" and edge.source == node and edge.target not in parents:

                    parents[edge.target] = node
                    pending.append(edge.target)

        return None

    def node_exists(
        self,
        node_id: str,
    ) -> bool:

        return any(
            node.node_id == node_id
            for node in self.nodes
        )
