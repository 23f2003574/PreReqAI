import re

from backend.concepts.concept_explanation_engine import ConceptExplanationEngine

from .base_tutor import (
    BaseTutor,
)

from .quiz_bank import QUIZ_BANK

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
    "Information Theory": "The mathematics of information: entropy and KL divergence, which measure uncertainty and the distance between distributions.",
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
            self._quiz_answer(paper, question)
            or self._concept_time_answer(paper, question)
            or self._resources_answer(paper, question)
            or self._concept_prerequisites_answer(paper, question)
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
    def _quiz_answer(paper, question):
        """'Quiz me on Softmax' -> that concept's practice questions with their answers; with no concept named, the
        paper's own concepts that have questions. Empty for a question that does not ask for a quiz."""

        text = _normalise(question)

        if not re.search(r"(?<![a-z0-9])(quiz|test me|self test)(?![a-z0-9])", text):
            return ""

        named = [name for name in QUIZ_BANK if re.search(rf"(?<![a-z0-9]){re.escape(_normalise(name))}s?(?![a-z0-9])", text)]
        mentioned = [name for name in ConceptExplanationEngine.EXPLANATIONS if re.search(rf"(?<![a-z0-9]){re.escape(_normalise(name))}s?(?![a-z0-9])", text)]

        if mentioned and not named:
            return "There are no practice questions yet for " + ", ".join(mentioned) + "."

        topics = named or [c.name for c in getattr(paper, "concepts", []) if c.name in QUIZ_BANK]

        if not topics:
            return "There are no practice questions yet for " + (", ".join(named) if named else "this paper") + "."

        lines = []
        for name in topics:
            for number, item in enumerate(QUIZ_BANK[name], 1):
                lines.append(f"{name} Q{number} ({item['difficulty']}): {item['question']} Answer: {item['answer']}")

        return " ".join(lines)

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
        # (and a prerequisite that is itself a registry concept, such as Attention behind a graph attention paper,
        # is explained from the same built-in definitions the paper's own concepts use)
        definitions = {
            name: PREREQUISITE_DEFINITIONS[name] if name in PREREQUISITE_DEFINITIONS else ConceptExplanationEngine.EXPLANATIONS[name][0]
            for name in reasons
            if name in PREREQUISITE_DEFINITIONS or name in ConceptExplanationEngine.EXPLANATIONS
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
    def _concept_prerequisites_answer(paper, question):
        """'Which prerequisites does Softmax need?' -> what that paper concept builds on (the same rules as the
        prerequisite tree), with the ones the learner has already studied or knows marked."""
        from backend.prerequisites.prerequisite_detector import PrerequisiteDetector

        text = _normalise(question)

        if not re.search(r"\b(prerequisites?|prereqs?|depends?|requires?|builds? on|does .* needs?|needs? to (know|understand))\b", text):
            return ""

        rules = PrerequisiteDetector.PREREQUISITE_RULES
        detected = {concept.name for concept in getattr(paper, "concepts", [])}
        # Longest names first and each match removed, as in _built_in_answer: "self-attention" is not "attention".
        named = []
        for name in sorted((n for n in detected if rules.get(n)), key=len, reverse=True):
            pattern = rf"(?<![a-z0-9]){re.escape(_normalise(name))}s?(?![a-z0-9])"
            if re.search(pattern, text):
                named.append(name)
                text = re.sub(pattern, " ", text)

        done = RuleBasedTutor._studied(paper)
        known = {item.concept for item in getattr(paper, "missing_prerequisites", []) if item.satisfied}

        def label(prerequisite):
            return f"{prerequisite} (studied)" if prerequisite in done else f"{prerequisite} (known or covered)" if prerequisite in known else prerequisite

        return " ".join(f"{name} builds on {', '.join(label(p) for p in rules[name])}." for name in named)

    @staticmethod
    def _concept_time_answer(paper, question):
        """'How long will calculus take?' -> the planned hours for that concept (not its definition, nor the whole plan's)."""
        text = _normalise(question)
        if not re.search(r"\b(how (long|many hours|many days|much time)|hours?|time (to|will|does|needed))\b", text):
            return ""
        plan = sorted(getattr(paper, "learning_plan", []), key=lambda step: -len(step.concept))
        for step in plan:
            pattern = rf"(?<![a-z0-9]){re.escape(_normalise(step.concept))}(?![a-z0-9])"
            if re.search(pattern, text):
                done = " You have already studied it." if step.concept in RuleBasedTutor._studied(paper) else ""
                return f"{step.concept}: about {step.estimated_hours} hours of study.{done}"
        return ""

    @staticmethod
    def _resources_answer(paper, question):
        """'Which resources/courses should I use for X?' -> the curated study link(s) already in the analysis:
        the named concept's, or every concept still to study (in study order) when none is named."""

        text = _normalise(question)

        if not re.search(r"\b(resources?|courses?|tutorials?|where (can|do|should) i (learn|study))\b", text):
            return ""

        resources = list(getattr(paper, "learning_resources", []))
        named = [r for r in resources if re.search(rf"(?<![a-z0-9]){re.escape(_normalise(r.concept))}(?![a-z0-9])", text)]
        if not named:  # a prerequisite that needs no study (marked known, or covered by the paper) has no resource: say why
            for item in sorted(getattr(paper, "missing_prerequisites", []), key=lambda item: -len(item.concept)):
                if item.satisfied and re.search(rf"(?<![a-z0-9]){re.escape(_normalise(item.concept))}(?![a-z0-9])", text):
                    return f"{item.concept} is not in your study plan, so there is no resource to suggest for it: {item.reason}."
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
                f"{int(days)} {'day' if int(days) == 1 else 'days'} at {estimate.average_hours_per_day:g} hours a day."
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

        if re.search(r"\b(equations?|formulas?|formulae)\b", text):
            equations = getattr(paper, "equations", [])
            if not equations:
                return "No equations were extracted from this paper."
            shown = "; ".join(f"({item.equation_id}) {' '.join(item.expression.split())} [{item.section}]" for item in equations[:5])
            more = f" and {len(equations) - 5} more" if len(equations) > 5 else ""
            return f"The paper has {len(equations)} extracted equation{'s' if len(equations) != 1 else ''}: {shown}{more}."

        if re.search(r"\b(progress|how (much|many)\b.*\b(completed?|done|finished|studied))\b", text):
            readiness = getattr(paper, "readiness", None)
            if readiness is None:
                return ""
            done = [step.concept for step in sorted(getattr(paper, "learning_plan", []), key=lambda step: step.order)
                    if step.concept in RuleBasedTutor._studied(paper)]
            listed = f" Studied: {', '.join(done)}." if done else ""
            return f"You have studied {readiness.completed_concepts} of {readiness.total_concepts} planned prerequisites ({readiness.progress_percent}%).{listed}"

        if re.search(r"\b(concepts|topics)\b", text) and re.search(r"\b(cover|covers|covered|discuss|discusses|mention|mentions|contain|contains|about|main|key|detected|find|found|use|uses|used|include|includes|involve|involves|rely|relies)\b", text):
            concepts = sorted(getattr(paper, "concepts", []), key=lambda item: -item.occurrences)
            if not concepts:
                return ""
            listed = ", ".join(f"{item.name} ({item.occurrences}x)" for item in concepts)
            return f"The paper discusses these concepts, most mentioned first: {listed}."

        if re.search(r"\b(paper|article)\b.*\babout\b|\babout\b.*\b(paper|article)\b", text):  # "what is the paper about?"
            concepts = sorted(getattr(paper, "concepts", []), key=lambda item: -item.occurrences)[:3]
            if not concepts:
                return ""
            title = getattr(getattr(paper, "metadata", None), "title", "") or "This paper"
            return f"{title} is mostly about: {', '.join(item.name for item in concepts)} (the concepts it mentions most)."

        if re.search(r"\b(ready|readiness)\b", text):
            readiness = getattr(paper, "readiness", None)
            if readiness is None:
                return ""
            verdict = "You are ready to read the paper." if readiness.ready_to_read else "You are not ready to read the paper yet."
            return f"{verdict} {readiness.status}: {readiness.completed_concepts} of {readiness.total_concepts} planned concepts ready ({readiness.progress_percent}%)."

        return ""
