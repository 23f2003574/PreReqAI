"""A deterministic simulation of learners answering the diagnostic, to measure what the mastery estimate (backend/mastery_model.py) does with evidence it should and should not accept.

Four kinds of simulated learner answer four-option questions (confidence "medium"), one answer a day over `days` days, drawing from a concept's questions in rotation (a concept has two or three):
* guesser: picks at random, so is right a quarter of the time. Declaring it mastered at any point is a FALSE MASTERY;
* partial: knows part of the concept and is right 60 percent of the time. Mastery at any point is also false;
* knower: right 95 percent of the time (a slip is possible). Reaching mastery within the days is TRUE MASTERY, and the median number of answers it took is reported;
* crammer: a knower who answers all of its questions in one sitting (a few minutes apart). Mastery from one sitting is a false durable mastery.
Every learner draws from random.Random(seed + index), so the numbers are reproducible. This measures the DESIGN of the estimate on simulated learners; it is not evidence about real learners, and the
simulated answer probabilities are assumptions, not data. The gate (python -m backend.prereqai_eval --gate) holds ceilings on the false rates and a floor on the true rate."""
import random
from datetime import datetime, timedelta, timezone
from statistics import median

from backend import mastery_model

START = datetime(2026, 11, 1, 9, tzinfo=timezone.utc)
KINDS = {"guesser": 0.25, "partial": 0.60, "knower": 0.95, "crammer": 0.95}


def run_learner(kind, seed, days=30, questions=("q1", "q2", "q3")):
    """The number of answers after which the estimate first said mastered for one simulated learner, or None when it never did."""
    rng, answers, times = random.Random(seed), [], []
    for number in range(days):
        question = questions[number % len(questions)]
        answers.append((rng.random() < KINDS[kind], "medium", question))
        times.append(START + (timedelta(minutes=3 * number) if kind == "crammer" else timedelta(days=number)))
        if mastery_model.estimate(answers, times)["mastered"]:
            return len(answers)
    return None


def evaluate(learners=400, seed=2026, days=30):
    """{"learners", "days", "false_mastery_guesser", "false_mastery_partial", "false_mastery_crammer", "true_mastery_knower", "median_answers_to_mastery"} over `learners` simulated learners of each kind."""
    reached = {kind: [run_learner(kind, seed + index, days) for index in range(learners)] for kind in KINDS}

    def share(kind):
        return sum(value is not None for value in reached[kind]) / learners

    needed = [value for value in reached["knower"] if value is not None]
    return {"learners": learners, "days": days, "false_mastery_guesser": share("guesser"), "false_mastery_partial": share("partial"), "false_mastery_crammer": share("crammer"),
            "true_mastery_knower": share("knower"), "median_answers_to_mastery": median(needed) if needed else None}
