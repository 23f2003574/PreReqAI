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

            "missing_prerequisites": [

                {
                    "concept": prerequisite.concept,
                    "satisfied": prerequisite.satisfied,
                    "reason": prerequisite.reason,
                }

                for prerequisite in paper.missing_prerequisites
            ],

            "learning_plan": [

                {
                    "step": step.order,
                    "concept": step.concept,
                    "estimated_hours": step.estimated_hours,
                }

                for step in paper.learning_plan
            ],

            "paper_difficulty": (

                {
                    "level": paper.difficulty.level,
                    "score": paper.difficulty.score,
                    "explanation": paper.difficulty.explanation,
                }

                if paper.difficulty is not None
                else None
            ),

            "study_time": (

                {
                    "total_hours":
                        paper.study_time.total_hours,

                    "recommended_days":
                        paper.study_time.recommended_days,

                    "hours_per_day":
                        paper.study_time.average_hours_per_day,
                }

                if paper.study_time is not None
                else None
            ),

            "difficulty_explanations": [

                {
                    "title": explanation.title,
                    "description": explanation.description,
                }

                for explanation
                in paper.difficulty_explanations
            ],

            "study_actions": [

                {
                    "priority": action.priority,
                    "title": action.title,
                    "description": action.description,
                }

                for action in paper.study_actions
            ],

            "learning_resources": [

                {
                    "concept": resource.concept,
                    "title": resource.title,
                    "provider": resource.provider,
                    "url": resource.url,
                    "estimated_hours": resource.estimated_hours,
                }

                for resource
                in paper.learning_resources
            ],
        }
