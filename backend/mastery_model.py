"""An uncertainty-aware estimate of whether a learner has mastered a concept, from objectively graded answers only.

A deterministic Bayesian-knowledge-tracing-style update. The state is P(learner knows the concept). Before each graded answer the learner may have learned it (LEARN); then the answer is evidence:
* a correct answer is likelier from someone who knows it than from a guess. The guess probability depends on how sure the learner said they were: 0.35 (low), 0.25 (medium, the chance
  of a four-option question), 0.15 (high);
* a wrong answer is likelier from someone who does not know it, and a confident wrong answer is the strongest evidence of that: the slip probability is 0.20 (low), 0.10 (medium), 0.05 (high).
Self-reported answers never enter. The result carries the probability, a standard error SE = sqrt(p (1 - p) / (n + 1)) over the n graded answers (a simple, explicit uncertainty measure,
not a Bayesian credible interval) and the interval p +/- 1.645 SE clamped to [0, 1]. A concept counts as mastered only when p >= MASTERED_P, the lower end of the interval reaches
MASTERED_LOWER, at least MIN_ANSWERS answers were graded and at least MIN_QUESTIONS different questions were answered correctly and no more than MAX_CONFIDENT_WRONG answers were confidently wrong, so three lucky guesses (p about 0.98, lower end about 0.86) are
not enough: the answer minimum is what stops them. The parameters are fixed, reasoned values, NOT fitted to real learners: the probabilities are an explainable ranking of evidence, not calibrated predictions.
Forgetting (`apply_decay`, used by learner_profile.mastery): without new graded evidence the probability falls toward PRIOR; 90% of the distance above the prior is assumed kept after each review interval (the question's own `interval_hours`, at least a day), counted from the latest graded answer (its schema 3 time, else last_seen). A concept mastered at its last answer lapses to "needs_refresh" once the decayed probability is below REFRESH_P (0.80) and returns to mastered when new graded answers arrive. These numbers are a reasoned heuristic, NOT a forgetting curve fitted to learners and not a calibrated probability.
A profile keeps each question's counters and its most recent graded answers in order (`graded_history`); `sequence_from_counters` uses those as given and rebuilds only the older answers, which survive as counters, in a canonical order (earlier correct answers, then the misses)."""
from datetime import timedelta
from math import sqrt

RETENTION_AT_INTERVAL, MIN_INTERVAL_DAYS, REFRESH_P = 0.90, 1.0, 0.80

PRIOR, LEARN = 0.30, 0.15
GUESS = {"low": 0.35, "medium": 0.25, "high": 0.15}
SLIP = {"low": 0.20, "medium": 0.10, "high": 0.05}
MASTERED_P, MASTERED_LOWER, MIN_ANSWERS, MIN_QUESTIONS, Z = 0.95, 0.85, 4, 2, 1.645
SPACING_HOURS, MIN_BLOCKS = 12.0, 2  # answers given within SPACING_HOURS of the first answer of a block are one block of evidence; durable mastery needs MIN_BLOCKS blocks (see `spaced_blocks`)
REPEAT_WEIGHT, QUESTION_CAP = 0.7, 1.5  # the nth answer to the same question moves the estimate REPEAT_WEIGHT ** (n - 1) as far as a first answer (a repeated question is partly remembered, not fresh evidence), and one question is worth at most QUESTION_CAP independent answers however often it is repeated
MIN_EFFECTIVE = 3.0  # durable mastery needs at least this many independent answers' worth of evidence once repeats are discounted and capped: four answers on two questions (1.5 + 1.5) reach it, one question asked three or five times plus one other (1.5 + 1) does not
RECENT_ANSWERS = 2  # durable mastery needs the latest RECENT_ANSWERS answers (in time order) to be correct: a recent miss is evidence the earlier successes may no longer hold
MAX_CONFIDENT_WRONG = 1  # a learner who was confidently wrong twice has not shown understanding, whatever they answered since (the rule the streak-based mastery had)
ACCURACY_LOWER, ACCURACY_Z = 0.70, 1.645  # sustained accuracy: the one-sided (95%) Wilson lower bound of the share of graded answers that were correct must reach ACCURACY_LOWER. A learner who is right 60 percent of the time
# passes the probability test by luck of the draw at some point in thirty answers (33 percent of simulated ones did); a history that contains misses must show it (a 95 percent knower with a slip needs a longer run). A history with no miss is judged as before: four right answers still count, which leaves a 60 percent learner a 0.6**4 chance of a lucky opening run.
CONFIDENCE_P = {"low": 0.4, "medium": 0.65, "high": 0.9}  # what each stated confidence claims about being right, for the Brier score


def update(p, correct, confidence="medium"):
    """P(knows) after one graded answer."""
    confidence = confidence if confidence in GUESS else "medium"
    p = p + (1 - p) * LEARN
    guess, slip = GUESS[confidence], SLIP[confidence]
    if correct:
        return p * (1 - slip) / (p * (1 - slip) + (1 - p) * guess)
    return p * slip / (p * slip + (1 - p) * (1 - guess))


def wilson_lower(correct, total, z=ACCURACY_Z):
    """The Wilson score lower bound (one-sided at z=1.645, 95%) of a proportion `correct` / `total`; 0.0 without answers."""
    if total <= 0:
        return 0.0
    share, z2 = correct / total, z * z
    return max(0.0, (share + z2 / (2 * total) - z * sqrt(share * (1 - share) / total + z2 / (4 * total * total))) / (1 + z2 / total))


def spaced_blocks(times):
    """How many separate blocks of evidence `times` (datetimes, None for an answer of unknown time) make: a block starts at the first answer at least SPACING_HOURS after the start of the previous block, so a cramming
    session is one block however many answers it holds. An answer of unknown time (a profile saved before schema 3, or an answer that rolled out of the kept history) never makes a block of its own: it is
    assumed to share the block of the earliest known answer, the conservative reading, so old untimed answers plus one sitting are still one block. With no known time at all this is 1 when there are answers."""
    times = list(times)
    known = sorted(t for t in times if t is not None)
    blocks, start = 0, None
    for moment in known:
        if start is None or (moment - start).total_seconds() >= SPACING_HOURS * 3600:
            blocks, start = blocks + 1, moment
    return blocks if known else (1 if times else 0)


def last_block_start(times):
    """The start time of the newest block of evidence in `times` (see spaced_blocks), or None when no time is known."""
    start = None
    for moment in sorted(t for t in times if t is not None):
        if start is None or (moment - start).total_seconds() >= SPACING_HOURS * 3600:
            start = moment
    return start


def estimate(answers, times=None):
    """{"p", "low", "high", "answers", "questions_correct", "mastered", "reason"} from [(correct, confidence, question_id)] in the order given; None when there are none.
    `times` (one datetime or None per answer, optional) adds the spacing rule: when any answer has a known time, mastery also needs MIN_BLOCKS blocks of evidence (`spaced_blocks`), so answers given in one sitting
    never establish durable mastery however well they went; the result then carries `spaced_blocks`. With no times given (or none known, as in profiles saved before schema 3) the rule is not applied."""
    answers = list(answers)
    if not answers:
        return None
    p, seen, per_question = PRIOR, {}, {}
    for correct, confidence, question in answers:
        seen[question] = seen.get(question, 0) + 1
        weight = REPEAT_WEIGHT ** (seen[question] - 1)  # evidence of a question already answered counts less (a partial update toward the full one)
        p, per_question[question] = p + weight * (update(p, correct, confidence) - p), per_question.get(question, 0.0) + weight
    weight_total = sum(min(QUESTION_CAP, value) for value in per_question.values())
    n = len(answers)
    se = sqrt(p * (1 - p) / (n + 1))
    low, high = max(0.0, p - Z * se), min(1.0, p + Z * se)
    questions = len({q for correct, _, q in answers if correct})
    confident_wrong = sum(1 for correct, confidence, _ in answers if not correct and confidence == "high")
    timed = times is not None and any(t is not None for t in times)
    blocks = spaced_blocks(times) if timed else None
    ready_at = last_block_start(times) + timedelta(hours=SPACING_HOURS) if timed else None
    spaced = not timed or blocks >= MIN_BLOCKS
    order = sorted(range(n), key=lambda i: (0,) if not timed or times[i] is None else (1, times[i]))  # time order; answers of unknown time are the oldest
    recent_miss = any(not answers[i][0] for i in order[-RECENT_ANSWERS:])
    accuracy_low = wilson_lower(sum(1 for correct, _, _ in answers if correct), n)
    right = sum(1 for correct, _, _ in answers if correct)
    accurate = right == n or accuracy_low >= ACCURACY_LOWER  # a history with no miss is judged by the probability and answer-count rules as before; one with misses must also show sustained accuracy
    mastered = accurate and p >= MASTERED_P and low >= MASTERED_LOWER and n >= MIN_ANSWERS and questions >= MIN_QUESTIONS and confident_wrong <= MAX_CONFIDENT_WRONG and spaced and not recent_miss and weight_total >= MIN_EFFECTIVE - 1e-9
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
        if not accurate and n >= MIN_ANSWERS:
            need.append(f"accuracy is not yet shown to be sustained: the lower bound of the share of correct answers is {accuracy_low:.2f} ({sum(1 for correct, _, _ in answers if correct)} of {n}); mastery needs {ACCURACY_LOWER:.2f}")
        if weight_total < MIN_EFFECTIVE - 1e-9 and n >= MIN_ANSWERS:
            need.append(f"the answers are only worth {weight_total:.2f} independent answers because questions were repeated (at least {MIN_EFFECTIVE:g} needed): answer other questions")
        if recent_miss and n >= MIN_ANSWERS:
            need.append(f"one of the last {RECENT_ANSWERS} answers was wrong (recent_miss): answer correctly {RECENT_ANSWERS} times in a row to show the earlier success still holds")
        if not spaced:
            need.append(f"all answers fall in {blocks} block of evidence (answers at least {SPACING_HOURS:.0f} hours apart start a new block); durable mastery needs {MIN_BLOCKS}: answer again on another day (from {ready_at.strftime('%Y-%m-%d %H:%M')} UTC)")
        reason = "; ".join(need)
    return {"p": round(p, 3), "low": round(low, 3), "high": round(high, 3), "answers": n, "questions_correct": questions, "mastered": mastered, "recent_miss": recent_miss, "effective_answers": round(weight_total, 2), "accuracy_low": round(accuracy_low, 3), "reason": reason, **({"spaced_blocks": blocks, **({"spacing_ready_at": ready_at.strftime("%Y-%m-%dT%H:%M:%SZ")} if not spaced else {})} if timed else {})}


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


def timed_sequence_from_counters(entry, question_id=""):
    """(sequence_from_counters(...), times): the same answers and, for each, the datetime it was given. An answer rebuilt from counters (it rolled out of the kept history) is dated by the entry's
    `graded_first_at`, the time of its first timed answer, so what the history forgot is still known to have happened no later than the answers that replaced it; without that field (profiles saved before
    it existed) or for an answer recorded without a time the time is None (see spaced_blocks)."""
    from backend import spaced_review

    sequence = sequence_from_counters(entry, question_id)
    recent = decode_timed_history(entry.get("graded_history"))
    recent = recent[-len(sequence):] if sequence else []
    first = spaced_review.parse_time(entry.get("graded_first_at"))
    return sequence, [first] * (len(sequence) - len(recent)) + [t for _, _, t in recent]


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
    answers, times = [], []
    for question_id, entry in entries:
        sequence, moments = timed_sequence_from_counters(entry, question_id)
        answers.extend(sequence)
        times.extend(moments)
    # The questions' histories are concatenated above, which is not the order the answers were given in: put them in time order (untimed answers, the oldest, keep their place first; ties keep entry order)
    order = sorted(range(len(answers)), key=lambda i: (0,) if times[i] is None else (1, times[i]))
    return estimate([answers[i] for i in order], [times[i] for i in order])


def estimate_attempts(attempts):
    """The estimate from a session's attempt dicts of one concept, in the order they were made; only graded attempts count. An attempt carries `at`, the UTC time it was given, from the day attempts were
    timestamped: with any time known the spacing rule applies exactly as for a profile (answers of one sitting are one block and never durable mastery); a session whose attempts have no time at all keeps
    the earlier behaviour (no spacing rule), and the result then says so with `timed: False`."""
    from backend import spaced_review

    graded = [a for a in attempts if a.get("graded")]
    times = [spaced_review.parse_time(a.get("at")) for a in graded]
    result = estimate([(bool(a["correct"]), a.get("confidence", "medium"), a["question_id"]) for a in graded], times)
    if result is not None:
        result["timed"] = any(t is not None for t in times)
    return result


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


def retention(days, interval_days):
    """The share of what was known that is assumed still known `days` after the last evidence: RETENTION_AT_INTERVAL (0.90) when `days` equals the review interval, falling by that factor for each further interval
    (RETENTION_AT_INTERVAL ** (days / interval)); 1.0 at once and never rising with time. The interval is the question's own review interval, never shorter than MIN_INTERVAL_DAYS."""
    return RETENTION_AT_INTERVAL ** (max(0.0, days) / max(MIN_INTERVAL_DAYS, interval_days))


def decay(p, days, interval_days):
    """`p` after `days` without new evidence: it falls toward the prior PRIOR (what a learner with no evidence is assumed to know) by the retention factor, so it never rises, never drops below PRIOR and equals `p` at day 0."""
    return PRIOR + (p - PRIOR) * retention(days, interval_days) if p > PRIOR else p


def last_evidence_time(entries):
    """The latest time a graded answer was given among profile question entries: the newest timestamp in a schema 3 `graded_history`, else (schema 2 answers carry none) the entry's `last_seen`; None when no entry has a graded answer."""
    from backend import spaced_review

    times = []
    for entry in entries:
        if not entry.get("graded_attempts"):
            continue
        timed = [t for _, _, t in decode_timed_history(entry.get("graded_history")) if t is not None]
        seen = spaced_review.parse_time(entry.get("last_seen"))
        times.append(max(timed) if timed else seen)
    return max((t for t in times if t is not None), default=None)


def apply_decay(result, days, interval_days):
    """The estimate `result` (from estimate / estimate_entries) after `days` without new graded evidence, with `interval_days` as the review interval. p, low and high decay toward PRIOR (see decay); the
    estimate at the last answer is kept as `p_at_last_answer`. A concept that was mastered at its last answer stays mastered while its decayed probability is at least REFRESH_P (0.80); below that `lapsed` is True,
    `mastered` is False and `reason` says how far it fell: it needs a refresh, which new graded answers give (they restart the clock and re-enter the estimate). A reasoned heuristic, NOT a forgetting curve fitted to learners."""
    if result is None:
        return None
    p, low, high = (round(decay(result[name], days, interval_days), 3) for name in ("p", "low", "high"))
    lapsed = bool(result["mastered"]) and p < REFRESH_P
    out = {**result, "p": p, "low": min(low, p), "high": max(high, p), "p_at_last_answer": result["p"], "retention": round(retention(days, interval_days), 3), "days_since_evidence": round(max(0.0, days), 1),
           "interval_days": round(max(MIN_INTERVAL_DAYS, interval_days), 1), "lapsed": lapsed, "mastered": bool(result["mastered"]) and not lapsed}
    if lapsed:
        out["reason"] = (f"it was {result['p']:.2f} at the last graded answer {days:.0f} days ago and the model puts it at {p:.2f} now (assumed {int(RETENTION_AT_INTERVAL * 100)}% retained after each {out['interval_days']:.0f}-day "
                         f"review interval; mastery lapses below {REFRESH_P:.2f}): answer a few questions again to confirm it")
    return out
