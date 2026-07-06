from backend.models import (
    Paper,
)

from backend.graph import (
    LearningPathGenerator,
)


class LearningReportGenerator:
    """
    Produces a user-facing learning report
    from the internal Paper Object Model.
    """

    def __init__(self):

        self.learning_path_generator = (
            LearningPathGenerator()
        )

    def generate(
        self,
        paper: Paper,
    ) -> dict:

        return {

            "paper": {

                "title": paper.metadata.title,

                "author": paper.metadata.author,

                "pages": paper.metadata.page_count,
            },

            "statistics": {

                "sections": len(paper.sections),

                "paragraphs": len(paper.paragraphs),

                "equations": len(paper.equations),

                "figures": len(paper.figures),

                "tables": len(paper.tables),

                "references": len(paper.references),

                "algorithms": len(paper.algorithms),

                "concepts": len(paper.concepts),
            },

            "concepts": [

                concept.name

                for concept in paper.concepts
            ],

            "learning_paths": {

                explanation.concept: (
                    self.learning_path_generator.generate(
                        paper.knowledge_graph,
                        explanation.concept,
                    )
                )

                for explanation in paper.concept_explanations
            },

            "difficulty": {

                explanation.concept:

                explanation.difficulty

                for explanation in paper.concept_explanations
            },

            "prerequisites": [

                {
                    "concept": prerequisite.concept,
                    "reason": prerequisite.reason,
                    "confidence": prerequisite.confidence,
                }

                for prerequisite in paper.prerequisites
            ],
        }
