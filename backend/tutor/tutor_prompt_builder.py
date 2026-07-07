from backend.models import (
    Paper,
)

from backend.session import (
    LearningSession,
    RetrievedContext,
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

Rules:

- Be educational.
- Prefer intuition before mathematics.
- Ground every answer in the supplied context.
- Avoid introducing unsupported claims.
"""
