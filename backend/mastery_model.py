"""An uncertainty-aware estimate of whether a learner has mastered a concept, from objectively graded answers only.

A deterministic Bayesian-knowledge-tracing-style update. The state is P(learner knows the concept). Before each graded answer the learner may have learned it (LEARN); then the answer is evidence:
* a correct answer is likelier from someone who knows it than from a guess. The guess probability depends on how sure the learner said they were: 0.35 (low), 0.25 (medium, the chance
  of a four-option question), 0.15 (high);
* a wrong answer is likelier from someone who does not know it, and a confident wrong answer is the strongest evidence of that: the slip probability is 0.20 (low), 0.10 (medium), 0.05 (high).
Self-reported answers never enter. The result carries the probability, a standard error SE = sqrt(p (1 - p) / (n + 1)) over the n graded answers (a simple, explicit uncertainty measure,
not a Bayesian credible interval) and the interval p +/- 1.645 SE clamped to [0, 1]. A concept counts as mastered only when p >= MASTERED_P, the lower end of the interval reaches
MASTERED_LOWER, at least MIN_ANSWERS answers were graded and at least MIN_QUESTIONS different questions were answered correctly and no more than MAX_CONFIDENT_WRONG answers were confidently wrong, so three lucky guesses (p about 0.98, lower end about 0.86) are
not enough: the answer minimum is what stops them. The parameters are fixed, reasoned values, NOT fitted to real learners: the probabilities are an explainable ranking of evidence, not calibrated predictions.
A profile keeps each question's counters and its most recent graded answers in order (`graded_history`); `sequence_from_counters` uses those as given and rebuilds only the older answers, which survive as counters, in a canonical order (earlier correct answers, then the misses)."""
from math import sqrt

PRIOR, LEARN = 0.30, 0.15
GUESS = {"low": 0.35, "medium": 0.25, "high": 0.15}
SLIP = {"low": 0.20, "medium": 0.10, "high": 0.05}
MASTERED_P, MASTERED_LOWER, MIN_ANSWERS, MIN_QUESTIONS, Z = 0.95, 0.85, 4, 2, 1.645
MAX_CONFIDENT_WRONG = 1  # a learner who was confidently wrong twice has not shown understanding, whatever they answered since (the rule the streak-based mastery had)
CONFIDENCE_P = {"low": 0.4, "medium": 0.65, "high": 0.9}  # what each stated confidence claims about being right, for the Brier score


def update(p, correct, confidence="medium"):
    """P(knows) after one graded answer."""
    confidence = confidence if confidence in GUESS else "medium"
    p = p + (1 - p) * LEARN
    guess, slip = GUESS[confidence], SLIP[confidence]
    if correct:
        return p * (1 - slip) / (p * (1 - slip) + (1 - p) * guess)
    return p * slip / (p * slip + (1 - p) * (1 - guess))


def estimate(answers):
    """{"p", "low", "high", "answers", "questions_correct", "mastered", "reason"} from [(correct, confidence, question_id)] in the order given; None when there are none."""
    answers = list(answers)
    if not answers:
        return None
    p = PRIOR
    for correct, confidence, _ in answers:
        p = update(p, correct, confidence)
    n = len(answers)
    se = sqrt(p * (1 - p) / (n + 1))
    low, high = max(0.0, p - Z * se), min(1.0, p + Z * se)
    questions = len({q for correct, _, q in answers if correct})
    confident_wrong = sum(1 for correct, confidence, _ in answers if not correct and confidence == "high")
    mastered = p >= MASTERED_P and low >= MASTERED_LOWER and n >= MIN_ANSWERS and questions >= MIN_QUESTIONS and confident_wrong <= MAX_CONFIDENT_WRONG
    if mastered:
        reason = f"{p:.2f} probability of knowing it (at least {low:.2f} with some confidence) from {n} graded answers on {questions} different questions"
    else:
        need = []
        if p < MASTERED_P or low < MASTERED_LOWER:
            need.append(f"the estimate is {p:.2f} (lower end {low:.2f}); mastery needs {MASTERED_P:.2f} and {MASTERED_LOWER:.2f}")
        if n < MIN_ANSWERS:
            need.append(f"only {n} graded answer{'s' if n != 1 else ''} (at least {MIN_ANSWERS} needed)")
        if confident_wrong > MAX_CONFIDENT_WRONG:
            need.append(f"{confident_wrong} confidently wrong answers (mastery allows at most {MAX_CONFIDENT_WRONG})")
        if questions < MIN_QUESTIONS:
            need.append(f"only {questions} question{'s' if questions != 1 else ''} answered correctly (at least {MIN_QUESTIONS} different ones needed)")
        reason = "; ".join(need)
    return {"p": round(p, 3), "low": round(low, 3), "high": round(high, 3), "answers": n, "questions_correct": questions, "mastered": mastered, "reason": reason}


_CONFIDENCE_OF_CODE = {"l": "low", "m": "medium", "h": "high"}


def decode_timed_history(history):
    """[(correct, confidence, time or None)] from an entry's `graded_history` codes ("1h@2026-11-23T13:03:48Z": correct, high confidence, given at that UTC time; "0l": wrong with low confidence and no known time),
    in the order the answers were given; codes that are not valid are skipped."""
    from backend import spaced_review

    result = []
    for code in history or []:
        if not isinstance(code, str) or len(code) < 2 or code[0] not in "01" or code[1] not in _CONFIDENCE_OF_CODE or (len(code) > 2 and code[2] != "@"):
            continue
        result.append((code[0] == "1", _CONFIDENCE_OF_CODE[code[1]], spaced_review.parse_time(code[3:]) if len(code) > 3 else None))
    return result


def decode_history(history):
    """[(correct, confidence)] from an entry's `graded_history` codes, in the order the answers were given (see decode_timed_history); codes that are not valid are skipped."""
    return [(ok, confidence) for ok, confidence, _ in decode_timed_history(history)]


def _canonical(attempts, correct, streak, sure_right, sure_wrong, question_id):
    wrong = max(0, attempts - correct)
    streak = min(streak, correct)
    sure_right, sure_wrong = min(sure_right, correct), min(sure_wrong, wrong)
    rights = ["high"] * sure_right + ["medium"] * (correct - sure_right)
    wrongs = ["high"] * sure_wrong + ["medium"] * (wrong - sure_wrong)
    early, late = rights[:max(0, correct - streak)], rights[max(0, correct - streak):]
    return [(True, c, question_id) for c in early] + [(False, c, question_id) for c in wrongs] + [(True, c, question_id) for c in late]


def sequence_from_counters(entry, question_id=""):
    """[(correct, confidence, question_id)] for one profile question entry's assessed answers; [] for an entry without any.
    The most recent answers are kept as they were given (`graded_history`, at most spaced_review.HISTORY_LIMIT of them, with their real order and their low, medium or high confidence). Answers
    older than that, or from a profile saved before the history existed, are known only as counters, so they are rebuilt in a canonical order placed BEFORE the history (earlier correct
    answers, then the misses; every answer without a recorded confidence counts as medium, and a confident one as high): an approximation, and the conservative one (misses after the successes)."""
    history = decode_history(entry.get("graded_history"))
    attempts, correct = entry.get("graded_attempts", 0), entry.get("graded_correct", 0)
    if not history:
        return _canonical(attempts, correct, entry.get("graded_streak", 0), entry.get("high_confidence_right", 0), entry.get("high_confidence_wrong", 0), question_id)
    history = history[-attempts:] if attempts else []
    older = max(0, attempts - len(history))
    kept_right, kept_wrong = sum(1 for ok, _ in history if ok), sum(1 for ok, _ in history if not ok)
    sure_right_kept, sure_wrong_kept = sum(1 for ok, c in history if ok and c == "high"), sum(1 for ok, c in history if not ok and c == "high")
    rebuilt = _canonical(older, min(older, max(0, correct - kept_right)), 0, max(0, entry.get("high_confidence_right", 0) - sure_right_kept),
                         max(0, entry.get("high_confidence_wrong", 0) - sure_wrong_kept), question_id) if older else []
    return rebuilt + [(ok, confidence, question_id) for ok, confidence in history]


def estimate_entries(entries):
    """The estimate for a concept's profile question entries ([(question_id, entry)] in a fixed order); None when none has an assessed answer."""
    answers = [item for question_id, entry in entries for item in sequence_from_counters(entry, question_id)]
    return estimate(answers)


def estimate_attempts(attempts):
    """The estimate from a session's attempt dicts of one concept, in the order they were made; only graded attempts count."""
    return estimate([(bool(a["correct"]), a.get("confidence", "medium"), a["question_id"]) for a in attempts if a.get("graded")])


def calibration(attempts):
    """{"answers", "brier", "by_confidence": {level: {answers, accuracy}}} over the graded attempts: the Brier score of the confidence the learner stated (low 0.4, medium 0.65, high 0.9 as the
    probability of being right) against what happened; lower is better, 0.25 is what saying 0.5 every time scores. None without graded answers. This describes the learner's own
    self-assessment, not the model."""
    graded = [a for a in attempts if a.get("graded")]
    if not graded:
        return None
    score = sum((CONFIDENCE_P.get(a.get("confidence"), 0.65) - bool(a["correct"])) ** 2 for a in graded) / len(graded)
    levels = {}
    for a in graded:
        level = levels.setdefault(a.get("confidence") if a.get("confidence") in CONFIDENCE_P else "medium", {"answers": 0, "correct": 0})
        level["answers"] += 1
        level["correct"] += bool(a["correct"])
    return {"answers": len(graded), "brier": round(score, 3), "by_confidence": {k: {"answers": v["answers"], "accuracy": round(v["correct"] / v["answers"], 2)} for k, v in sorted(levels.items())}}
