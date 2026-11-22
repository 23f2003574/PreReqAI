"""Objectively graded diagnostic questions: the same practice questions as the quiz, answered by picking one of four options instead of grading oneself.

A question's options are its correct answer and three answers to OTHER concepts' questions of the same bank (never the same text), put in an order fixed by the question id, so the
learner sees the same options on every request and the system can check the choice itself. The learner also says how sure they are (low, medium, high). The result records
`graded: True`, `correct` and `confidence` separately, and stores the outcome as knew/missed so existing progress and spaced review keep working. Confidence matters twice: a wrong answer given
with high confidence is counted (an overconfident learner is not rated mastered, see learner_profile.mastery) and the response tells the learner when their confidence and accuracy disagree.
Self-grading stays available (quiz/outcome) as a supplementary signal; it never establishes mastery."""
import hashlib

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
    return {**question, "options": options_for(question["question_id"]), "weak_distractors": weak_distractors(question["question_id"]), "confidence_levels": list(CONFIDENCE), "graded": True}


def grade(session, identifier, choice, confidence):
    """Check `choice` (the index into the question's options) against the answer, record the attempt, and return the verdict with the correct answer and the explanation.
    QuizError for an unknown question, a question that was not served, a choice outside the options or an unknown confidence."""
    concept, number, item = quiz_session._lookup(identifier)
    identifier = question_id(concept, number)
    options = options_for(identifier)
    if confidence not in CONFIDENCE:
        raise QuizError("outcome", f"confidence must be one of {', '.join(CONFIDENCE)}, not {confidence!r}.", "Send the learner's confidence: low, medium or high.")
    if isinstance(choice, bool) or not isinstance(choice, int) or not 0 <= choice < len(options):
        raise QuizError("outcome", f"choice must be a number from 0 to {len(options) - 1}, the position of the option picked.", "Send the index of one of the served options.")
    if identifier not in session.quiz_pending:
        raise QuizError("state", f"Question {identifier!r} has not been asked in this session (or its answer is already recorded).", "Request a question with GET /diagnostic/question first.")
    session.quiz_pending.pop(identifier)
    correct = options[choice] == item["answer"]
    session.quiz_attempts.append({"question_id": identifier, "concept": concept, "outcome": "knew" if correct else "missed", "revealed": False, "graded": True, "correct": correct,
                                  "confidence": confidence, "chosen": options[choice]})
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
