from itertools import combinations

from backend.models import (
    GraphEdge,
    Paper,
)


class ParagraphConceptRelationshipBuilder:
    """
    Creates concept relationships based on
    paragraph-level co-occurrence.

    Concepts mentioned within the same paragraph
    are considered semantically related.
    """

    def build(
        self,
        paper: Paper,
    ) -> Paper:

        existing_edges = {

            (
                edge.source,
                edge.target,
                edge.relationship,
            )

            for edge in paper.knowledge_graph.edges
        }

        for paragraph in paper.paragraphs:

            present = []

            paragraph_text = paragraph.content.lower()

            for concept in paper.concepts:

                if concept.name.lower() in paragraph_text:

                    present.append(concept.name)

            for source, target in combinations(
                sorted(set(present)),
                2,
            ):

                edge = (

                    f"concept:{source}",

                    f"concept:{target}",

                    "co_occurs_with",
                )

                if edge in existing_edges:

                    continue

                paper.knowledge_graph.add_edge(

                    GraphEdge(

                        source=edge[0],

                        target=edge[1],

                        relationship=edge[2],
                    )
                )

                existing_edges.add(edge)

        return paper
