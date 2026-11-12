import functools
import re
import threading

from backend.concepts.concept_registry import ConceptRegistry
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


def _name_pattern(name, plural=True):
    """A regex for `name` as a whole word in normalised text ('paragraphs' or 'improbable' is not 'probability'), with an
    optional plural s; the one spelling every question-matching rule shares."""
    return rf"(?<![a-z0-9]){re.escape(_normalise(name))}{'s?' if plural else ''}(?![a-z0-9])"


_QUIZ_SUBJECT = re.compile(r"(?<![a-z0-9])(?:on|about|for)\s+([a-z0-9][a-z0-9 ]{0,60}?)\s*$")
_QUIZ_GENERIC = frozenset({"the", "this", "that", "these", "those", "a", "an", "it", "my", "me", "all", "everything", "paper", "papers", "concept",
                           "concepts", "topic", "topics", "so", "far", "here", "now", "today", "again", "more", "some", "of", "in"})

_CONCEPT_POINTER = re.compile(r"\b(this|that|the) concept\b|\b(explain|describe) it\b", re.IGNORECASE)


@functools.lru_cache(maxsize=1)
def _alias_spellings():
    """{normalised alias: concept name} for every registry alias, longest alias first; built once, not per question."""
    spellings = {_normalise(alias): concept.name for concept in ConceptRegistry().all() for alias in concept.aliases}
    return tuple((re.compile(_name_pattern(spelling, plural=False), re.IGNORECASE), spellings[spelling])
                 for spelling in sorted(spellings, key=len, reverse=True))


def _canonical_question(question):
    """The question with registry alias spellings (SGD, backprop, RNN...) replaced by the concept's own name, so every
    matching rule (quiz, time, prerequisites, definitions) understands them as the detector does."""
    text = question
    for pattern, name in _alias_spellings():
        text = pattern.sub(name, text)
    return text


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

        # One tutor serves every session; the prompt of the last answer is kept per thread so a concurrent request
        # for another session can neither overwrite it nor be read through it.
        self._local = threading.local()

    @property
    def last_prompt(self) -> "str | None":
        return getattr(self._local, "last_prompt", None)

    @last_prompt.setter
    def last_prompt(self, value):
        self._local.last_prompt = value

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

        question = _canonical_question(question)

        pointer = _CONCEPT_POINTER.search(question)
        topic = getattr(session, "active_concept", None)

        if pointer and topic:  # "Explain this concept" with a topic means that topic's concept

            question = question[:pointer.start()] + topic + question[pointer.end():]

        answer = (
            self._quiz_answer(paper, session, question)
            or self._concept_time_answer(paper, question)
            or self._resources_answer(paper, question)
            or self._concept_prerequisites_answer(paper, question)
            or self._built_in_answer(paper, context, question)
            or self._overview_answer(paper, question)
            or self._study_plan_answer(paper, question)
            or (self._name_a_concept_answer(paper) if pointer and not topic else "")
        )

        unsupported = "" if answer else self._unsupported_concept_answer(question)

        return TutorResponse(

            answer=answer or unsupported or (
                "A tutoring model has not yet "
                "been configured."
            ),

            confidence=0.5 if answer else 0.0,

            supporting_concepts=context.concepts,

            supporting_sections=context.sections,

            suggested_followups=[

                "Explain this concept",

                "Show prerequisite path",

                "Summarize this paper",
            ],
        )

    @staticmethod
    def _quiz_answer(paper, session, question):
        """'Quiz me on Softmax' -> that concept's practice questions with their answers; with no concept named, the
        paper's own concepts that have questions. Empty for a question that does not ask for a quiz."""

        text = _normalise(question)

        if not re.search(r"(?<![a-z0-9])(quiz|test me|self test)(?![a-z0-9])", text):
            return ""

        named = [name for name in QUIZ_BANK if re.search(_name_pattern(name), text)]
        # 'Self-Attention' contains 'Attention': a concept named only inside a longer named concept is not named itself
        named = [name for name in named
                 if not any(other != name and _normalise(name) in _normalise(other) for other in named)]
        # prerequisites such as Calculus or Probability are named in questions too, but have no questions of their own
        known_names = [*ConceptExplanationEngine.EXPLANATIONS, *PREREQUISITE_DEFINITIONS]
        mentioned = [name for name in dict.fromkeys(known_names) if re.search(_name_pattern(name), text)]

        if mentioned and not named:
            return "There are no practice questions yet for " + ", ".join(mentioned) + "."

        # the session's topic (ask --topic / the `topic` field) scopes the quiz like it scopes every other answer
        topic = getattr(session, "active_concept", None)

        # "Quiz me on Quantum Gravity": a topic PreReqAI does not know is not answered with questions about other concepts
        wanted = _QUIZ_SUBJECT.search(text)
        if wanted and not named and not topic and set(wanted.group(1).split()) - _QUIZ_GENERIC:
            return f"I can't quiz you on '{wanted.group(1)}': it is not a concept PreReqAI supports. Ask for a quiz on a concept from the study plan, or say 'quiz me'."

        if topic and not named:
            if topic not in QUIZ_BANK:
                return f"There are no practice questions yet for {topic}."
            named = [topic]

        topics = named or [c.name for c in getattr(paper, "concepts", []) if c.name in QUIZ_BANK]

        if not topics:
            return "There are no practice questions yet for this paper."

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
        # Registry aliases (SGD, backprop, CNN...) are spellings the detector already treats as the same concept.
        spellings = {name: name for name in {**definitions, **reasons}}
        for concept in ConceptRegistry().all():
            if concept.name in spellings:
                spellings.update({alias: concept.name for alias in concept.aliases})

        for spelling in sorted(spellings, key=len, reverse=True):
            name = spellings[spelling]
            pattern = _name_pattern(spelling)
            if re.search(pattern, text):
                if name not in asked:
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

    _DEFINITION_QUESTION = re.compile(
        r"^\s*(?:what\s+(?:is|are)|what's|explain|define|tell\s+me\s+about)\s+(?:an?\s+|the\s+)?(?P<name>[^?.!]+?)\s*[?.!]*\s*$",
        re.IGNORECASE,
    )

    @staticmethod
    def _unsupported_concept_answer(question):
        """A definition question nothing built-in could answer: name the concept as unsupported instead of leaving only the
        generic placeholder. No definition or prerequisite is invented for it."""

        match = RuleBasedTutor._DEFINITION_QUESTION.match(question or "")

        if not match:
            return ""

        name = match.group("name").strip()

        if not name or re.match(r"(this|that|these|those|it|them|paper|the paper)\b", name, re.IGNORECASE):
            return ""

        registered = {*PREREQUISITE_DEFINITIONS, *ConceptExplanationEngine.EXPLANATIONS}
        for concept in ConceptRegistry().all():
            registered.add(concept.name)
            registered.update(concept.aliases)

        text = _normalise(name)
        if any(re.search(_name_pattern(spelling), text) for spelling in registered):
            return ""  # a registered concept the paper does not discuss: not "unsupported", so keep the plain placeholder

        return (f"'{name}' is not in PreReqAI's built-in concept registry, so there is no built-in definition or "
                f"prerequisite information for it. A tutoring model has not yet been configured.")

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
            pattern = _name_pattern(name)
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
            pattern = _name_pattern(step.concept, plural=False)
            if re.search(pattern, text):
                done = " You have already studied it." if step.concept in RuleBasedTutor._studied(paper) else ""
                return f"{step.concept}: about {step.estimated_hours} hours of study.{done}"
        # A concept the learner already knows (or the paper covers) is not in the plan, so it has no hours: say so rather than
        # falling through to its definition, which does not answer "how long".
        satisfied = sorted(
            (item.concept for item in getattr(paper, "missing_prerequisites", []) if item.satisfied),
            key=len, reverse=True,
        )
        for name in satisfied:
            if re.search(_name_pattern(name, plural=False), text):
                return f"{name}: no study time needed. You already know it or the paper covers it, so it is not in your study plan."
        return ""

    @staticmethod
    def _resources_answer(paper, question):
        """'Which resources/courses should I use for X?' -> the curated study link(s) already in the analysis:
        the named concept's, or every concept still to study (in study order) when none is named."""

        text = _normalise(question)

        if not re.search(r"\b(resources?|courses?|tutorials?|where (can|do|should) i (learn|study))\b", text):
            return ""

        resources = list(getattr(paper, "learning_resources", []))
        named = [r for r in resources if re.search(_name_pattern(r.concept, plural=False), text)]
        if not named:  # a prerequisite that needs no study (marked known, or covered by the paper) has no resource: say why
            for item in sorted(getattr(paper, "missing_prerequisites", []), key=lambda item: -len(item.concept)):
                if item.satisfied and re.search(_name_pattern(item.concept, plural=False), text):
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
    def _nothing_detected(paper):
        """True when the analysis ran (readiness was evaluated) and found no concept at all: its empty plan says nothing."""
        readiness = getattr(paper, "readiness", None)
        return readiness is not None and readiness.total_concepts == 0 and not getattr(paper, "concepts", None)

    @staticmethod
    def _overview_answer(paper, question):
        """'Summarize the paper' -> an overview built from the analysis (concepts, difficulty, preparation and readiness);
        it is not a generated summary of the paper's text."""

        if not re.search(r"\b(summari[sz]e|summary|overview)\b", _normalise(question)):
            return ""

        concepts = [c.name for c in getattr(paper, "concepts", [])]
        if not concepts:
            return NO_CONCEPTS_ANSWER if RuleBasedTutor._nothing_detected(paper) else ""

        shown = ", ".join(concepts[:8]) + (f" and {len(concepts) - 8} more" if len(concepts) > 8 else "")
        parts = [f"{getattr(getattr(paper, 'metadata', None), 'title', None) or 'This paper'} covers {len(concepts)} concept{'s' if len(concepts) != 1 else ''}: {shown}."]

        difficulty = getattr(paper, "difficulty", None)
        if difficulty is not None:
            parts.append(f"Difficulty: {difficulty.level}.")

        done = RuleBasedTutor._studied(paper)
        hours = sum(step.estimated_hours for step in getattr(paper, "learning_plan", []) if step.concept not in done)
        if hours:
            parts.append(f"Preparation left: about {hours} hours.")

        readiness = getattr(paper, "readiness", None)
        if readiness is not None:
            parts.append(f"Readiness: {readiness.status} ({readiness.completed_concepts} of {readiness.total_concepts} planned concepts ready).")

        parts.append("This overview comes from the paper's analysis, not a generated summary of its text.")
        return " ".join(parts)

    @staticmethod
    def _name_a_concept_answer(paper):
        """'Explain this concept' with no concept in focus (no topic): say how to pick one, instead of the placeholder."""

        names = [c.name for c in getattr(paper, "concepts", [])]

        if not names:
            return ""

        return ("Name the concept to explain, for example 'What is " + names[0] + "?', or ask with that concept as the topic. "
                "Concepts in this paper: " + ", ".join(names) + ".")

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
            if RuleBasedTutor._nothing_detected(paper) and not plan:
                return NO_CONCEPTS_ANSWER
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
                return NO_CONCEPTS_ANSWER if RuleBasedTutor._nothing_detected(paper) else ""
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
            if RuleBasedTutor._nothing_detected(paper):  # "Ready to Read (100%)" over an empty plan would be a verdict about nothing
                return NO_CONCEPTS_ANSWER
            verdict = "You are ready to read the paper." if readiness.ready_to_read else "You are not ready to read the paper yet."
            return f"{verdict} {readiness.status}: {readiness.completed_concepts} of {readiness.total_concepts} planned concepts ready ({readiness.progress_percent}%)."

        return ""


# Study, time and readiness questions about a paper in which no known concept was found: say so instead of a verdict or a placeholder.
NO_CONCEPTS_ANSWER = ("No concepts this release knows were detected in this paper, so there is no study plan and I cannot say "
                      "whether you are ready; check that the PDF has selectable text, or try a paper in a covered area (machine learning).")


# Shown with a placeholder answer: the question matched nothing the built-in tutor can answer, so say what it can.
ANSWERABLE_HINT = ("Questions this release can answer: 'What is <concept>?' for a concept in the study plan, "
                   "'What should I study first?', 'How long will it take?', 'How difficult is it?', 'Am I ready?', "
                   "'How much have I completed?', 'Which prerequisites does <concept> need?', 'Which equations are in the paper?', "
                   "'Summarize this paper' and 'Quiz me'.")

