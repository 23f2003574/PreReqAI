import re

from backend.models import (
    Paper,
)

from backend.concepts import ConceptRegistry

from backend.graph import (
    LearningPathGenerator,
)


_ALIASES = {concept.name: concept.aliases for concept in ConceptRegistry().all()}


def registry_aliases(name: str) -> tuple:
    return _ALIASES.get(name, ())


class LearningReportGenerator:
    """
    Produces a user-facing learning report
    from the internal Paper Object Model.
    """

    def __init__(self):

        self.learning_path_generator = (
            LearningPathGenerator()
        )

    @staticmethod
    def _equations(paper: Paper) -> list:
        """Each extracted equation with the detected concepts its section discusses, so a reader knows which
        concepts to be comfortable with before the mathematics. The link is the equation itself plus the 300
        characters of its section that lead up to it (the extractor only knows the equation's line and section)."""

        sections = {section.title: section.content.lower() for section in paper.sections}

        def context(equation) -> str:
            content = sections.get(equation.section, "")
            expression = equation.expression.lower()
            at = content.find(expression)
            return expression if at < 0 else content[max(0, at - 300):at + len(expression)]

        terms = {
            concept.name: (concept.name.lower(), *(alias.lower() for alias in registry_aliases(concept.name)))
            for concept in paper.concepts
        }

        return [
            {
                "id": equation.equation_id,
                "expression": equation.expression,
                "section": equation.section,
                "concepts": [
                    name for name, names in terms.items()
                    if any(re.search(rf"\b{re.escape(term)}s?\b", context(equation)) for term in names)
                ],
            }
            for equation in paper.equations
        ]

    def generate(
        self,
        paper: Paper,
    ) -> dict:

        study_order = {step.concept: step.order for step in paper.learning_plan}  # resources follow the plan

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

            "equations": self._equations(paper),

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
                # a concept the learner has finished is no longer something to study
                if action.title not in {
                    f"Study {item.concept}" for item in paper.study_progress if item.completed
                }
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
                in sorted(
                    paper.learning_resources,
                    key=lambda item: study_order.get(item.concept, len(study_order)),
                )
            ],

            "study_roadmap": [

                {
                    "step": roadmap.step,
                    "concept": roadmap.concept,
                    "resource": roadmap.resource_title,
                    "provider": roadmap.provider,
                    "estimated_hours": roadmap.estimated_hours,
                }

                for roadmap
                in paper.study_roadmap
            ],

            "study_progress": [

                {
                    "concept": progress.concept,
                    "completed": progress.completed,
                    "progress_percent": progress.progress_percent,
                }

                for progress
                in paper.study_progress
            ],

            "readiness": (

                {
                    "progress_percent":
                        paper.readiness.progress_percent,

                    "ready_to_read":
                        paper.readiness.ready_to_read,

                    "completed_concepts":
                        paper.readiness.completed_concepts,

                    "total_concepts":
                        paper.readiness.total_concepts,

                    "status":
                        paper.readiness.status,
                }

                if paper.readiness is not None
                else None
            ),

            "prerequisite_justifications": [

                {
                    "concept": item.concept,
                    "justification": item.justification,
                }

                for item
                in paper.prerequisite_justifications
            ],
        }
