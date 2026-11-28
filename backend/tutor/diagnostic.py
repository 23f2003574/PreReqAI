"""Objectively graded diagnostic questions: the same practice questions as the quiz, answered by picking one of four options instead of grading oneself.

A question's options are its correct answer and three answers to OTHER concepts' questions of the same bank (never the same text), put in an order fixed by the question id, so the
learner sees the same options on every request and the system can check the choice itself. The learner also says how sure they are (low, medium, high). The result records
`graded: True`, `correct` and `confidence` separately, and stores the outcome as knew/missed so existing progress and spaced review keep working. Confidence matters twice: a wrong answer given
with high confidence is counted (an overconfident learner is not rated mastered, see learner_profile.mastery) and the response tells the learner when their confidence and accuracy disagree.
Self-grading stays available (quiz/outcome) as a supplementary signal; it never establishes mastery."""
import hashlib

from backend import spaced_review
from . import quiz_session
from .quiz_session import ASKABLE, QuizError, question_id

CONFIDENCE = ("low", "medium", "high")
OPTIONS = 4


def _rank(identifier, text):
    return hashlib.sha256(f"{identifier}|{text}".encode("utf-8")).hexdigest()


def _norm(text):
    return " ".join(str(text).lower().split())


def _siblings(concept):
    """Concepts the prerequisite graph puts next to `concept`: its prerequisites, the concepts that need it and those that share a prerequisite with it, sorted."""
    from .math_quiz import MATH_SUBJECT

    if concept in MATH_SUBJECT:  # a mathematical subtopic: its neighbours are the other subtopics of the same subject and the subject's own questions
        return sorted({name for name, subject in MATH_SUBJECT.items() if subject == MATH_SUBJECT[concept] and name != concept} | {MATH_SUBJECT[concept]})
    from backend.prerequisites.prerequisite_detector import PrerequisiteDetector

    rules = PrerequisiteDetector.PREREQUISITE_RULES
    own = set(rules.get(concept, ()))
    return sorted({*own, *(name for name, needs in rules.items() if concept in needs), *(name for name, needs in rules.items() if name != concept and own & set(needs))} - {concept})


def distractor_pool(identifier):
    """(related, unrelated, correct): the candidate wrong answers of a question, each tier ordered so that texts close to the correct one in length come first (then by a hash of the question id, so
    the order is fixed). related: the other answers of the same concept, the common misconceptions the tutor knows for it, then the answers of its siblings in the prerequisite graph; unrelated:
    answers to other concepts' questions (a learner can rule these out without knowing the concept). A candidate equal to, containing or contained in the correct answer is never used."""
    concept, number, item = quiz_session._lookup(identifier)
    identifier, correct = question_id(concept, number), item["answer"]
    from .misconception_registry import COMMON_MISCONCEPTIONS

    def usable(text):
        low, mine = _norm(text), _norm(correct)
        return bool(low) and low != mine and low not in mine and mine not in low

    def ordered(texts):
        unique = list(dict.fromkeys(t for t in texts if usable(t)))
        return sorted(unique, key=lambda t: (abs(len(t) - len(correct)) // 12, _rank(identifier, t)))

    same = [q["answer"] for q in ASKABLE.get(concept, []) if q is not item]
    sibling = [q["answer"] for name in _siblings(concept) for q in ASKABLE.get(name, [])]
    related = list(dict.fromkeys([*ordered(same), *ordered(COMMON_MISCONCEPTIONS.get(concept, [])), *ordered(sibling)]))
    other = [q["answer"] for name, items in ASKABLE.items() if name != concept for q in items if len(q["answer"]) <= 2 * max(len(correct), 40)]
    return related, [t for t in ordered(other) if t not in related], correct


def options_for(identifier):
    """The four answer texts of a question in their fixed order; QuizError("unknown") for an id that is not a question. Distractors come from the same concept and its neighbours first; answers to
    unrelated concepts fill in only when fewer than three related ones exist (see `distractor_report`, `weak_distractors`)."""
    concept, number, item = quiz_session._lookup(identifier)
    identifier = question_id(concept, number)
    related, unrelated, correct = distractor_pool(identifier)
    chosen = [*related, *unrelated][:OPTIONS - 1]
    return sorted([correct, *chosen], key=lambda text: _rank("order|" + identifier, text))  # a different hash from the one that picked the distractors, or the answer would tend to come last


def order_for_attempt(identifier, attempt):
    """The options of a question in the order for its `attempt`-th serving (0 for the first, which is the fixed order of options_for): the same four texts, ordered by a hash that includes the attempt number, and never in
    the order of the serving before it, so a learner who sees a question again cannot answer it by where the right option stood."""
    base = options_for(identifier)
    if attempt <= 0:
        return base

    def arranged(number):
        return base if number <= 0 else sorted(base, key=lambda text: _rank(f"order|{identifier}|{number}", text))

    order, before = arranged(attempt), arranged(attempt - 1)
    return order if order != before else [*order[1:], order[0]]


def _times_served(session, identifier):
    return sum(1 for attempt in session.quiz_attempts if attempt.get("question_id") == identifier)


def weak_distractors(identifier):
    """True when fewer than three related distractors exist for the question, so the learner can rule some options out without knowing the concept."""
    related, _, _ = distractor_pool(identifier)
    return len(related) < OPTIONS - 1


def distractor_report():
    """{"questions", "weak": [question ids], "concepts_without_related": [concepts whose every question is weak]} over every askable question."""
    weak, by_concept = [], {}
    for concept, items in ASKABLE.items():
        for number in range(1, len(items) + 1):
            identifier = question_id(concept, number)
            by_concept.setdefault(concept, []).append(weak_distractors(identifier))
            if by_concept[concept][-1]:
                weak.append(identifier)
    return {"questions": sum(len(v) for v in by_concept.values()), "weak": weak, "concepts_without_related": sorted(c for c, flags in by_concept.items() if all(flags))}


def serve(session, concept=None):
    """The next question (as quiz_session.next_question picks it) with its options and no answer."""
    question = quiz_session.next_question(session, concept)
    pending = session.quiz_pending[question["question_id"]]
    if not pending.get("options"):  # a question that is served again before it is answered (a reload, a retry) keeps the order it was first shown in
        pending["options"] = order_for_attempt(question["question_id"], _times_served(session, question["question_id"]))
    return {**question, "options": list(pending["options"]), "weak_distractors": weak_distractors(question["question_id"]), "confidence_levels": list(CONFIDENCE), "graded": True}


def option_origin(text, concept):
    """The concept a wrong answer text belongs to: the concept whose own question has it as its answer, or whose known misconception it is; None for the concept's own answers and for text of no known concept.
    A learner who picks the answer of concept B for a question of concept A has confused A with B."""
    wanted = _norm(text)
    from .misconception_registry import COMMON_MISCONCEPTIONS

    for name, items in ASKABLE.items():
        if name != concept and not name.startswith("Math: ") and any(_norm(q["answer"]) == wanted for q in items):
            return name
    for name, texts in COMMON_MISCONCEPTIONS.items():
        if name != concept and any(_norm(t) == wanted for t in texts):
            return name
    return None


def grade(session, identifier, choice, confidence):
    """Check `choice` (the index into the question's options) against the answer, record the attempt, and return the verdict with the correct answer and the explanation.
    QuizError for an unknown question, a question that was not served, a choice outside the options or an unknown confidence."""
    concept, number, item = quiz_session._lookup(identifier)
    identifier = question_id(concept, number)
    served = (session.quiz_pending.get(identifier) or {}).get("options")
    options = list(served) if served else options_for(identifier)  # the order the learner was shown (a pending question of an older session has none: the fixed order)
    if confidence not in CONFIDENCE:
        raise QuizError("outcome", f"confidence must be one of {', '.join(CONFIDENCE)}, not {confidence!r}.", "Send the learner's confidence: low, medium or high.")
    if isinstance(choice, bool) or not isinstance(choice, int) or not 0 <= choice < len(options):
        raise QuizError("outcome", f"choice must be a number from 0 to {len(options) - 1}, the position of the option picked.", "Send the index of one of the served options.")
    if identifier not in session.quiz_pending:
        raise QuizError("state", f"Question {identifier!r} has not been asked in this session (or its answer is already recorded).", "Request a question with GET /diagnostic/question first.")
    session.quiz_pending.pop(identifier)
    correct = options[choice] == item["answer"]
    session.quiz_attempts.append({"question_id": identifier, "concept": concept, "outcome": "knew" if correct else "missed", "revealed": False, "graded": True, "correct": correct,
                                  "confidence": confidence, "chosen": options[choice], "at": spaced_review.stamp(spaced_review.now()),
                                  **({"confused_with": origin} if not correct and (origin := option_origin(options[choice], concept)) else {})})  # the time the answer was given: the spacing rule needs it (an attempt of an older session has none)
    from .quiz_bank import QUIZ_EXPLANATIONS

    verdict = {"question_id": identifier, "correct": correct, "confidence": confidence, "answer": item["answer"], "calibration": calibration_note(correct, confidence)}
    if (concept, item["question"]) in QUIZ_EXPLANATIONS:
        verdict["explanation"] = QUIZ_EXPLANATIONS[(concept, item["question"])]
    return verdict


def calibration_note(correct, confidence):
    if confidence == "high" and not correct:
        return "You were sure and it was wrong: this counts against rating the concept mastered until you answer it correctly."
    if confidence == "low" and correct:
        return "Right, though you were unsure: a few more correct answers will make it count."
    return ""


def assessed_summary(session):
    """{concept: {graded, correct, high_confidence_wrong}} from the session's assessed attempts."""
    found = {}
    for attempt in quiz_session._attempts(session):
        if attempt.get("graded"):
            entry = found.setdefault(attempt["concept"], {"graded": 0, "correct": 0, "high_confidence_wrong": 0})
            entry["graded"] += 1
            entry["correct"] += bool(attempt["correct"])
            entry["high_confidence_wrong"] += attempt["confidence"] == "high" and not attempt["correct"]
    return found
