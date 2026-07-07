from backend.models import (
    Paper,
)

from backend.session import (
    LearningSession,
    RetrievedContext,
    TutorMode,
)


class TutorPromptBuilder:
    """
    Constructs prompts for every tutoring model.
    """

    def build(

        self,

        session: LearningSession,

        paper: Paper,

        context: RetrievedContext,

        question: str,

        mode: TutorMode,

    ) -> str:

        concepts = ", ".join(
            context.concepts
        )

        sections = ", ".join(
            context.sections
        )

        return f"""
You are PreReqAI.

Your objective is to help a learner understand
a research paper.

Paper:
{paper.metadata.title}

Current Topic:
{session.active_concept}

Relevant Concepts:
{concepts}

Relevant Sections:
{sections}

Learner Question:
{question}

Teaching Mode:
{mode.value}

Instructions:
{self._mode_instruction(mode)}

Rules:

- Ground every answer in the supplied context.
- Avoid introducing unsupported claims.
"""

    def _mode_instruction(

        self,

        mode: TutorMode,

    ) -> str:

        instructions = {

            TutorMode.INTUITION:
                "Explain ideas intuitively before introducing formal definitions.",

            TutorMode.MATHEMATICS:
                "Focus on mathematical derivations and notation.",

            TutorMode.IMPLEMENTATION:
                "Explain implementation details with practical examples.",

            TutorMode.PREREQUISITES:
                "Relate the answer to prerequisite concepts.",

            TutorMode.SUMMARY:
                "Provide a concise summary.",

            TutorMode.ANALOGY:
                "Use analogies from everyday life whenever possible.",
        }

        return instructions[mode]
