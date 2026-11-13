"""The interactive quiz: one question at a time without its answer, an explicit reveal, a recorded outcome (knew / missed) and a per-concept
mastery summary, all kept on the learning session. Deterministic: the next question depends only on the session's own attempts. The
text-based quiz of the tutor ("Quiz me on Softmax") is separate and unchanged."""

import re

from .quiz_bank import QUIZ_BANK

OUTCOMES = ("knew", "missed")
MASTERY_STREAK = 2  # this many "knew" in a row, most recent last, is "mastered"


class QuizError(Exception):
    """A request the quiz cannot honour: `kind` is "unsupported" (a concept without questions), "unknown" (a question id that does not
    exist), "state" (the question was not served, or its outcome is already recorded) or "outcome" (not knew/missed)."""

    def __init__(self, kind, message, hint=""):
        super().__init__(message)
        self.kind, self.hint = kind, hint


def _key(name):
    return re.sub(r"[\s_\-]+", " ", str(name)).strip().lower()


def question_id(concept, number):
    return f"{concept}:{number}"


def _lookup(identifier):
    """(concept, number, item) for a question id such as "Softmax:2"; QuizError("unknown") for anything else."""
    concept, _, number = str(identifier).rpartition(":")
    if concept in QUIZ_BANK and number.isdigit() and 1 <= int(number) <= len(QUIZ_BANK[concept]):
        return concept, int(number), QUIZ_BANK[concept][int(number) - 1]
    raise QuizError("unknown", f"There is no quiz question {identifier!r}.",
                    "Use the question_id from GET /quiz/question; ids look like 'Softmax:1'.")


def _attempts(session):
    return getattr(session, "quiz_attempts", [])


def _paper_topics(session):
    return [concept.name for concept in getattr(getattr(session, "paper", None), "concepts", []) if concept.name in QUIZ_BANK]


def next_question(session, concept=None):
    """Serve one question without its answer. With a concept: its least-practised question (ties: the first). Without: among the paper's
    concepts with questions, the one with the lowest mastery (least attempted, then fewest "knew"), then by name. Marks it as served."""
    if concept is not None:
        named = {_key(name): name for name in QUIZ_BANK}.get(_key(concept))
        if named is None:
            raise QuizError("unsupported", f"PreReqAI has no practice questions for {concept!r}.",
                            "Name a concept with questions, for example one listed in the session's concepts.")
        topics = [named]
    else:
        topics = _paper_topics(session)
        if not topics:
            raise QuizError("unsupported", "None of this paper's concepts has practice questions.", "Try the text quiz or another paper.")
    summary = {entry["concept"]: entry for entry in progress(session)["concepts"]}
    chosen = min(topics, key=lambda name: (summary.get(name, {}).get("attempts", 0), summary.get(name, {}).get("knew", 0), name))
    taken = {}
    for attempt in _attempts(session):
        taken[attempt["question_id"]] = taken.get(attempt["question_id"], 0) + 1
    number = min(range(1, len(QUIZ_BANK[chosen]) + 1), key=lambda n: (taken.get(question_id(chosen, n), 0), n))
    identifier = question_id(chosen, number)
    session.quiz_pending[identifier] = session.quiz_pending.get(identifier) or {"revealed": False}
    item = QUIZ_BANK[chosen][number - 1]
    return {"question_id": identifier, "concept": chosen, "difficulty": item["difficulty"], "question": item["question"]}


def reveal(session, identifier):
    """The answer to a question that was served; remembered so the outcome can be recorded after it."""
    _, _, item = _lookup(identifier)
    if identifier not in session.quiz_pending:
        raise QuizError("state", f"Question {identifier!r} has not been asked in this session (or its outcome is already recorded).",
                        "Request a question with GET /quiz/question first.")
    session.quiz_pending[identifier]["revealed"] = True
    return {"question_id": identifier, "answer": item["answer"]}


def record(session, identifier, outcome):
    """Record `knew` or `missed` for a served question, once: the question is then no longer pending, so a repeated submission is refused
    instead of counted twice."""
    concept, _, _ = _lookup(identifier)
    if outcome not in OUTCOMES:
        raise QuizError("outcome", f"outcome must be 'knew' or 'missed', not {outcome!r}.", "Send {\"outcome\": \"knew\"} or {\"outcome\": \"missed\"}.")
    if identifier not in session.quiz_pending:
        raise QuizError("state", f"No outcome is awaited for {identifier!r}: it was not asked, or its outcome is already recorded.",
                        "Request a question with GET /quiz/question; each question is answered once.")
    revealed = session.quiz_pending.pop(identifier)["revealed"]
    session.quiz_attempts.append({"question_id": identifier, "concept": concept, "outcome": outcome, "revealed": revealed})
    return progress(session)


def progress(session):
    """{"attempts", "concepts": [{concept, attempts, knew, missed, mastery, status}]} for the concepts attempted so far, by name.
    mastery is the share of attempts that were "knew". status: "mastered" after MASTERY_STREAK "knew" in a row, "progressing" when the
    latest attempt was "knew", "needs_practice" when it was "missed"."""
    by_concept = {}
    for attempt in _attempts(session):
        by_concept.setdefault(attempt["concept"], []).append(attempt["outcome"])
    concepts = []
    for name in sorted(by_concept):
        outcomes = by_concept[name]
        streak = next((i for i, o in enumerate(reversed(outcomes)) if o != "knew"), len(outcomes))  # trailing "knew" run
        knew = outcomes.count("knew")
        concepts.append({
            "concept": name, "attempts": len(outcomes), "knew": knew, "missed": len(outcomes) - knew,
            "mastery": round(knew / len(outcomes), 2),
            "status": "mastered" if streak >= MASTERY_STREAK else "progressing" if outcomes[-1] == "knew" else "needs_practice",
        })
    return {"attempts": len(_attempts(session)), "concepts": concepts}
