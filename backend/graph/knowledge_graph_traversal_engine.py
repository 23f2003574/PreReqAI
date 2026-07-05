from collections import deque

from backend.models import (
    KnowledgeGraph,
)


class KnowledgeGraphTraversalEngine:
    """
    Provides traversal utilities for the
    Paper Knowledge Graph.
    """

    def neighbors(
        self,
        graph: KnowledgeGraph,
        node_id: str,
    ) -> list[str]:

        neighbors = []

        for edge in graph.edges:

            if edge.source == node_id:

                neighbors.append(edge.target)

        return neighbors

    def breadth_first_search(
        self,
        graph: KnowledgeGraph,
        start_node: str,
    ) -> list[str]:

        visited = set()

        queue = deque([start_node])

        traversal = []

        while queue:

            current = queue.popleft()

            if current in visited:
                continue

            visited.add(current)

            traversal.append(current)

            for neighbor in self.neighbors(
                graph,
                current,
            ):

                if neighbor not in visited:

                    queue.append(neighbor)

        return traversal
