import re

from .base_tutor import (
    BaseTutor,
)

from .tutor_prompt_builder import (
    TutorPromptBuilder,
)

from .tutor_response import (
    TutorResponse,
)


def _normalise(value):
    return re.sub(r"[\s\-_]+", " ", value.lower())


class RuleBasedTutor(BaseTutor):
    """
    Temporary tutor used before the
    LLM tutor is introduced.
    """

    def __init__(self):

        self.prompt_builder = (
            TutorPromptBuilder()
        )

        self.last_prompt: str | None = None

    def answer(

        self,

        session,

        paper,

        context,

        question,

        mode,

    ):

        self.last_prompt = self.prompt_builder.build(

            session,

            paper,

            context,

            question,

            mode,
        )

        answer = self._built_in_answer(
            paper,
            context,
            question,
        )

        return TutorResponse(

            answer=answer or (
                "A tutoring model has not yet "
                "been configured."
            ),

            confidence=0.5 if answer else 0.0,

            supporting_concepts=context.concepts,

            supporting_sections=context.sections,

            suggested_followups=[

                "Explain this concept",

                "Show prerequisite path",

                "Summarize this section",
            ],
        )

    @staticmethod
    def _built_in_answer(paper, context, question):
        """Answer from the analysis already computed (definitions and
        prerequisite justifications) for the concepts the question is about."""

        text = _normalise(question)

        definitions = {
            e.concept: e.definition
            for e in getattr(paper, "concept_explanations", [])
        }

        reasons = {
            j.concept: j.justification
            for j in getattr(paper, "prerequisite_justifications", [])
        }

        asked = []

        # Longest names first and each match is removed, so "self-attention" does not also
        # answer for "Attention" and "paragraphs" or "improbable" match no concept at all.
        for name in sorted({**definitions, **reasons}, key=len, reverse=True):
            pattern = rf"(?<![a-z0-9]){re.escape(_normalise(name))}s?(?![a-z0-9])"
            if re.search(pattern, text):
                asked.append(name)
                text = re.sub(pattern, " ", text)

        for name in context.concepts:
            if name not in asked and name in definitions:
                asked.append(name)

        parts = []

        for name in asked:
            if name in definitions:
                parts.append(f"{name}: {definitions[name]}")
            if name in reasons:
                parts.append(f"Why it is needed here: {reasons[name]}")

        return " ".join(parts)
