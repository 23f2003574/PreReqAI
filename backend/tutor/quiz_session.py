"""The interactive quiz: one question at a time without its answer, an explicit reveal, a recorded outcome (knew / missed) and a per-concept
mastery summary, all kept on the learning session. Deterministic: the next question depends only on the session's own attempts. The
text-based quiz of the tutor ("Quiz me on Softmax") is separate and unchanged."""

import re

from .quiz_bank import QUIZ_BANK, SUBJECT_QUIZ_BANK

ASKABLE = {**QUIZ_BANK, **SUBJECT_QUIZ_BANK}  # questions that can be served by name; the default pick still uses QUIZ_BANK (paper concepts) only

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
    if concept in ASKABLE and number.isdigit() and 1 <= int(number) <= len(ASKABLE[concept]):
        return concept, int(number), ASKABLE[concept][int(number) - 1]
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
        named = {_key(name): name for name in ASKABLE}.get(_key(concept))
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
    number = min(range(1, len(ASKABLE[chosen]) + 1), key=lambda n: (taken.get(question_id(chosen, n), 0), n))
    identifier = question_id(chosen, number)
    session.quiz_pending[identifier] = session.quiz_pending.get(identifier) or {"revealed": False}
    item = ASKABLE[chosen][number - 1]
    return {"question_id": identifier, "concept": chosen, "difficulty": item["difficulty"], "question": item["question"],
            "number": number, "of": len(ASKABLE[chosen])}  # which of the concept's questions this is, and how many it has


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


# A "you may already know this" suggestion is evidence, not a verdict: the quiz is self-graded, so it asks for more than the "mastered" streak. All must hold
# for a subject that is still in the study plan and not studied: at least SUGGEST_MIN_ATTEMPTS answers, a "knew" share of at least SUGGEST_MIN_SHARE, the
# "mastered" streak (MASTERY_STREAK "knew" in a row, latest last) and "knew" on at least SUGGEST_MIN_DISTINCT different questions (so repeating one
# question cannot do it). The learner always decides: nothing is marked known here; the page offers the existing /known endpoint.
SUGGEST_MIN_ATTEMPTS = 3
SUGGEST_MIN_SHARE = 0.75
SUGGEST_MIN_DISTINCT = 2


def known_suggestions(session):
    """[{concept, attempts, knew, mastery, distinct_questions, reason}] for the planned, unstudied subjects whose quiz results meet the thresholds above,
    by concept name, one entry each. A concept the learner already knows is not in the plan, so it is never suggested again; neither is a studied one.
    Reads the quiz attempts only: scores, mastery and the plan are not changed."""
    paper = getattr(session, "paper", None)
    planned = {item.concept for item in getattr(paper, "study_progress", []) if not item.completed}
    knew_on = {}
    for attempt in _attempts(session):
        if attempt["outcome"] == "knew":
            knew_on.setdefault(attempt["concept"], set()).add(attempt["question_id"])
    found = []
    for entry in progress(session)["concepts"]:
        name, distinct = entry["concept"], len(knew_on.get(entry["concept"], ()))
        if (name in planned and entry["status"] == "mastered" and entry["attempts"] >= SUGGEST_MIN_ATTEMPTS
                and entry["mastery"] >= SUGGEST_MIN_SHARE and distinct >= SUGGEST_MIN_DISTINCT):
            found.append({"concept": name, "attempts": entry["attempts"], "knew": entry["knew"], "mastery": entry["mastery"],
                          "distinct_questions": distinct,
                          "reason": f"You said you knew {entry['knew']} of your {entry['attempts']} {name} answers, including the last {MASTERY_STREAK} in a row "
                                    f"and {distinct} different questions."})
    return found


def topics(session):
    """[{concept, kind, questions}]: what the learner can be quizzed on in this session, so a page offers only topics that have questions. "paper": a
    detected concept with questions; "prerequisite": a subject or concept in the study plan with questions (a known concept has left the plan). One
    entry per name, paper concepts first. Any other name is refused by next_question as before."""
    paper = getattr(session, "paper", None)
    found = [{"concept": name, "kind": "paper", "questions": len(ASKABLE[name])} for name in dict.fromkeys(_paper_topics(session))]
    for item in getattr(paper, "study_progress", []):
        if item.concept in ASKABLE and all(entry["concept"] != item.concept for entry in found):
            found.append({"concept": item.concept, "kind": "prerequisite", "questions": len(ASKABLE[item.concept])})
    return found


def pending(session):
    """The questions served but not yet answered (no answers): [{question_id, concept, difficulty, question, revealed}], so a reloaded page can continue."""
    found = []
    for identifier, state in getattr(session, "quiz_pending", {}).items():
        try:
            concept, _, item = _lookup(identifier)
        except QuizError:
            continue
        found.append({"question_id": identifier, "concept": concept, "difficulty": item["difficulty"], "question": item["question"],
                      "revealed": bool(state.get("revealed"))})
    return found
