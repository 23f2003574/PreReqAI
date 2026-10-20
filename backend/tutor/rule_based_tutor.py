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


PREREQUISITE_DEFINITIONS = {
    "Linear Algebra": "The mathematics of vectors, matrices and linear transformations.",
    "Probability": "The mathematics of uncertainty: how likely events are and how to reason about random outcomes.",
    "Calculus": "The mathematics of change: derivatives and gradients, and integrals.",
    "Neural Networks": "Models built from layers of simple units whose weights are learned from data by gradient descent.",
    "Graphs": "Structures of nodes connected by edges, used to model relationships between things.",
    "Markov Decision Process": "A framework for sequential decisions where an agent's actions change its state and earn rewards.",
}


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

        answer = (
            self._resources_answer(paper, question)
            or self._built_in_answer(paper, context, question)
            or self._study_plan_answer(paper, question)
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

        reasons = {
            j.concept: j.justification
            for j in getattr(paper, "prerequisite_justifications", [])
        }

        # a prerequisite the paper never names (Probability, Calculus...) has no paper-concept explanation
        definitions = {
            name: PREREQUISITE_DEFINITIONS[name] for name in reasons if name in PREREQUISITE_DEFINITIONS
        }

        definitions.update({
            e.concept: e.definition
            for e in getattr(paper, "concept_explanations", [])
        })

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

    @staticmethod
    def _resources_answer(paper, question):
        """'Which resources/courses should I use for X?' -> the curated study link(s) already in the analysis:
        the named concept's, or every concept still to study (in study order) when none is named."""

        text = _normalise(question)

        if not re.search(r"\b(resources?|courses?|tutorials?|where (can|do|should) i (learn|study))\b", text):
            return ""

        resources = list(getattr(paper, "learning_resources", []))
        named = [r for r in resources if re.search(rf"(?<![a-z0-9]){re.escape(_normalise(r.concept))}(?![a-z0-9])", text)]
        if named:
            chosen = named
        else:
            done = RuleBasedTutor._studied(paper)
            order = {step.concept: step.order for step in getattr(paper, "learning_plan", [])}
            chosen = sorted((r for r in resources if r.concept not in done), key=lambda r: order.get(r.concept, len(order) + 1))
        if not chosen:
            return ""
        listed = "; ".join(f"{r.concept}: {r.title} ({r.provider}, ~{r.estimated_hours} h) {r.url}" for r in chosen)
        return f"Suggested resources: {listed}."

    @staticmethod
    def _studied(paper):
        return {item.concept for item in getattr(paper, "study_progress", []) if item.completed}

    @staticmethod
    def _study_plan_answer(paper, question):
        """Answer paper-level study questions (what to learn first, how long,
        how hard) from the learning plan, study time and difficulty already computed."""

        text = _normalise(question)

        if re.search(r"\b(how (long|many hours|many days|much time)|time (to|will|does))\b", text):
            estimate = getattr(paper, "study_time", None)
            if estimate is None:
                return ""
            plan = getattr(paper, "learning_plan", [])
            done = RuleBasedTutor._studied(paper)
            if not plan and estimate.total_hours == 0:  # nothing was planned (e.g. everything marked known), so nothing was studied either
                return "There are no prerequisites left to study, so no preparation time is left."
            if estimate.total_hours == 0 or (plan and all(step.concept in done for step in plan)):
                return "You have studied every planned prerequisite; no preparation time is left."
            hours = sum(step.estimated_hours for step in plan if step.concept not in done) if plan else estimate.total_hours
            if hours == estimate.total_hours:
                days = estimate.recommended_days
            else:  # progress was made: re-plan the remaining hours at the same daily pace
                days = max(1, -(-hours // max(estimate.average_hours_per_day, 1)))
            return (
                f"Plan about {hours} hours of preparation, roughly "
                f"{int(days)} days at {estimate.average_hours_per_day:g} hours a day."
            )

        if re.search(r"\b(how (hard|difficult)|difficulty)\b", text):
            difficulty = getattr(paper, "difficulty", None)
            if difficulty is None:
                return ""
            return f"Difficulty: {difficulty.level}. {difficulty.explanation}".strip()

        if re.search(
            r"\b(prerequisites?|prereqs?|background|study|learn|know|read first|start with|before reading)\b", text
        ):
            steps = sorted(getattr(paper, "learning_plan", []), key=lambda step: step.order)
            if not steps:
                if getattr(paper, "concepts", None):  # concepts were found but nothing is left to study
                    return "There are no prerequisites left to study for this paper."
                return ""
            done = RuleBasedTutor._studied(paper)
            todo = [step for step in steps if step.concept not in done]
            if not todo:
                return "You have studied every planned prerequisite; you are ready to read the paper."
            listed = "; ".join(
                f"{step.order}. {step.concept} (~{step.estimated_hours} h)" for step in todo
            )
            finished = f" Already studied: {', '.join(c for c in (s.concept for s in steps) if c in done)}." if done else ""
            return f"Study these in order before the paper: {listed}.{finished}"

        if re.search(r"\b(ready|readiness)\b", text):
            readiness = getattr(paper, "readiness", None)
            if readiness is None:
                return ""
            verdict = "You are ready to read the paper." if readiness.ready_to_read else "You are not ready to read the paper yet."
            return f"{verdict} {readiness.status}: {readiness.completed_concepts} of {readiness.total_concepts} planned concepts ready ({readiness.progress_percent}%)."

        return ""
