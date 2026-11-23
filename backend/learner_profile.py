"""The optional persistent learner profile: the subjects a learner already knows or has studied, kept across papers.

A profile is a small versioned JSON file in the same envelope style as a saved session (see session/session_codec.py):

    {"format": "prereqai-learner-profile", "schema_version": 2, "known": ["Linear Algebra", ...], "studied": ["Probability", ...],
     "quiz": {"Softmax:1": {"concept": "Softmax", "attempts": 3, "knew": 2, "missed": 1, "streak": 1, "last_outcome": "knew",
                            "first_seen": "...Z", "last_seen": "...Z", "interval_hours": 12.0, "due": "...Z"}}}

Version 2 adds `quiz`: the learner's outcome history per question (see spaced_review.py for the review schedule). A version 1 file (no `quiz`) is read
as a version 2 profile with no quiz history, keeping its `known` and `studied`, and becomes version 2 the next time it is saved; the rewrite is checked
by reading it back before it replaces the file, so a faulty migration can never replace a valid profile.

It is separate from paper sessions, opt-in (the CLI's --profile FILE, the server's PREREQAI_PROFILE_DIR) and meant for the local, single-user
deployment: there are no accounts. Loading validates everything and never raises; a missing file is an empty profile, an unreadable one
(malformed, hostile, wrongly typed, from a newer version) is reported and left exactly as it is, never overwritten. Saving writes a temporary file,
syncs it and swaps it in, so an interrupted save keeps the previous profile.

Rules. Names are compared like everywhere else in PreReqAI (case, spaces, hyphens and underscores ignored) and stored once, in the spelling of
PreReqAI's own subjects; a name PreReqAI does not know is never added from a request, and one already in a file is kept untouched and not used
for anything. A subject is either known or studied: known wins. Explicit values given with a request add to the profile and never remove from
it; to forget a subject, edit the file. A profile subject that is not in a paper's study plan is simply not needed there (no warning)."""
import json
import math
import os
import re
import threading

from backend.filelock import locked
from pathlib import Path

FORMAT = "prereqai-learner-profile"
SCHEMA_VERSION = 2
MAX_QUESTIONS = 5000
_QUESTION_ID = re.compile(r"[^:\x00]{1,200}:\d{1,4}")
_COUNTS = ("attempts", "knew", "missed", "streak")
_HISTORY_CODE = re.compile(r"[01][lmh]")
MAX_BYTES = 1024 * 1024
MAX_SUBJECTS = 2000
MAX_NAME_CHARS = 200
PROFILE_DIR_ENV = "PREREQAI_PROFILE_DIR"
_NAME = re.compile(r"[A-Za-z0-9_-]{1,64}")
_lock = threading.RLock()  # kept for callers that import it; the read-modify-write blocks use filelock.locked(path), which also queues other processes


class ProfileError(ValueError):
    """The file is not a usable profile; the message says why."""


class ProfileInputError(ProfileError):
    """A request to change a profile was invalid (an unknown concept, too many names); the profile is untouched."""


def key(name):
    return re.sub(r"[\s\-_]+", " ", str(name)).strip().casefold()


def vocabulary():
    """{comparison key: PreReqAI's spelling} of the subjects a learner can know: registry concepts and prerequisite subjects."""
    from backend.concepts import ConceptRegistry
    from backend.prerequisites.prerequisite_detector import PrerequisiteDetector

    names = {c.name for c in ConceptRegistry().all()} | {p for targets in PrerequisiteDetector.PREREQUISITE_RULES.values() for p in targets}
    return {key(name): name for name in sorted(names)}


def _dedupe(names, vocab=None):
    seen, result = set(), []
    for name in names:
        k = key(name)
        if k and k not in seen:
            seen.add(k)
            result.append((vocab or {}).get(k, str(name).strip()))
    return result


def parse(raw):
    """(known, studied) from the bytes of a profile file, or ProfileError saying why it cannot be used."""
    profile = parse_full(raw)
    return profile["known"], profile["studied"]


def _quiz_entries(value):
    """The validated quiz history of a profile: {question_id: entry}; ProfileError for anything that is not one."""
    from backend import spaced_review

    if not isinstance(value, dict) or len(value) > MAX_QUESTIONS:
        raise ProfileError(f"'quiz' must be an object of at most {MAX_QUESTIONS} questions")
    result = {}
    for identifier, entry in value.items():
        if not (isinstance(identifier, str) and _QUESTION_ID.fullmatch(identifier) and isinstance(entry, dict)):
            raise ProfileError(f"'quiz' has an invalid question {str(identifier)[:40]!r}")
        counts = [entry.get(name) for name in _COUNTS]
        if (not all(isinstance(n, int) and not isinstance(n, bool) and 0 <= n <= 10**6 for n in counts) or entry["knew"] + entry["missed"] != entry["attempts"]
                or not isinstance(entry.get("concept"), str) or not entry["concept"].strip() or len(entry["concept"]) > MAX_NAME_CHARS
                or entry.get("last_outcome") not in ("knew", "missed") or any(spaced_review.parse_time(entry.get(f)) is None for f in ("first_seen", "last_seen", "due"))
                or isinstance(entry.get("interval_hours"), bool) or not isinstance(entry.get("interval_hours"), (int, float)) or not math.isfinite(entry["interval_hours"])):
            raise ProfileError(f"'quiz' has an invalid entry for {identifier!r}")
        graded = {name: entry[name] for name in spaced_review.GRADED_FIELDS if name in entry}  # optional: an entry saved before assessed answers existed has none (read as zero)
        if not all(isinstance(n, int) and not isinstance(n, bool) and 0 <= n <= 10**6 for n in graded.values()) or graded.get("graded_correct", 0) > graded.get("graded_attempts", 0):
            raise ProfileError(f"'quiz' has an invalid entry for {identifier!r}")
        if "graded_history" in entry:  # the last graded answers in order (spaced_review.HISTORY_LIMIT at most): "1h" is correct with high confidence, "0l" wrong with low confidence
            history = entry["graded_history"]
            if (not isinstance(history, list) or len(history) > spaced_review.HISTORY_LIMIT or len(history) > graded.get("graded_attempts", 0)
                    or not all(isinstance(code, str) and _HISTORY_CODE.fullmatch(code) for code in history)):
                raise ProfileError(f"'quiz' has an invalid entry for {identifier!r}")
            graded = {**graded, "graded_history": list(history)}
        if "ease" in entry or "last_grade" in entry:  # present only on entries reviewed with a grade (again, hard, good, easy)
            if (isinstance(entry.get("ease"), bool) or not isinstance(entry.get("ease"), (int, float)) or not 1.3 <= entry["ease"] <= 3.5 or entry.get("last_grade") not in spaced_review.GRADES):
                raise ProfileError(f"'quiz' has an invalid entry for {identifier!r}")
            graded = {**graded, "ease": entry["ease"], "last_grade": entry["last_grade"]}
        result[identifier] = {**graded, "concept": entry["concept"].strip(), **{name: entry[name] for name in _COUNTS}, "last_outcome": entry["last_outcome"],
                              "first_seen": entry["first_seen"], "last_seen": entry["last_seen"], "interval_hours": entry["interval_hours"], "due": entry["due"]}
    return result


def parse_full(raw):
    """{"known": [...], "studied": [...], "quiz": {...}} from the bytes of a version 1 or 2 profile file, or ProfileError saying why it cannot be used."""
    try:
        data = json.loads(raw.decode("utf-8-sig"), parse_constant=lambda c: (_ for _ in ()).throw(ValueError(f"constant {c}")))
    except (UnicodeDecodeError, ValueError, RecursionError) as error:
        raise ProfileError(f"it is not valid JSON ({error})") from None
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise ProfileError(f"it is not a PreReqAI learner profile (its format must be {FORMAT!r})")
    version = data.get("schema_version")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise ProfileError("its schema_version is missing or not a positive integer")
    if version > SCHEMA_VERSION:
        raise ProfileError(f"it was saved by a newer PreReqAI (profile version {version}; this one reads up to {SCHEMA_VERSION})")
    lists = []
    for field in ("known", "studied"):
        values = data.get(field, [])
        if (not isinstance(values, list) or len(values) > MAX_SUBJECTS
                or not all(isinstance(v, str) and 0 < len(v.strip()) <= MAX_NAME_CHARS and "\x00" not in v for v in values)):
            raise ProfileError(f"{field!r} must be a list of at most {MAX_SUBJECTS} non-empty names of at most {MAX_NAME_CHARS} characters")
        lists.append(values)
    vocab = vocabulary()
    known = _dedupe(lists[0], vocab)
    quiz = _quiz_entries(data["quiz"]) if version >= 2 and "quiz" in data else {}  # a version 1 file has no quiz history
    return {"known": known, "studied": [name for name in _dedupe(lists[1], vocab) if key(name) not in {key(k) for k in known}], "quiz": quiz}


def load_full(path):
    """(profile, problem): the profile as {"known", "studied", "quiz"} and "" for a readable or missing file, else an empty profile and why it cannot be used."""
    target = Path(path)
    empty = {"known": [], "studied": [], "quiz": {}}
    try:
        if not target.exists():
            return empty, ""
        if target.stat().st_size > MAX_BYTES:
            raise ProfileError(f"it is larger than {MAX_BYTES} bytes")
        return parse_full(target.read_bytes()), ""
    except ProfileError as error:
        return empty, f"the learner profile {target} was not used and was left unchanged: {error}"
    except OSError as error:
        return empty, f"the learner profile {target} could not be read ({getattr(error, 'strerror', None) or error}); it was left unchanged"


def load(path):
    """(known, studied, problem): problem is "" for a readable or missing file, else why the file cannot be used (then nothing is returned from it)."""
    target = Path(path)
    try:
        if not target.exists():
            return [], [], ""
        if target.stat().st_size > MAX_BYTES:
            raise ProfileError(f"it is larger than {MAX_BYTES} bytes")
        known, studied = parse(target.read_bytes())
        return known, studied, ""
    except ProfileError as error:
        return [], [], f"the learner profile {target} was not used and was left unchanged: {error}"
    except OSError as error:
        return [], [], f"the learner profile {target} could not be read ({getattr(error, 'strerror', None) or error}); it was left unchanged"


def save(path, known, studied, quiz=None):
    """Write the profile atomically: the previous file stays intact if anything fails (the error is raised, the temporary file removed).
    `quiz` None keeps the quiz history the file already has; the text is read back and checked before it replaces the file."""
    target = Path(path)
    known = _dedupe(known)
    studied = [name for name in _dedupe(studied) if key(name) not in {key(k) for k in known}]
    if quiz is None:
        quiz, problem = load_full(target)
        if problem:
            raise ProfileError(problem)
        quiz = quiz["quiz"]
    text = json.dumps({"format": FORMAT, "schema_version": SCHEMA_VERSION, "known": known, "studied": studied, "quiz": quiz}, indent=2) + "\n"
    written = parse_full(text.encode("utf-8"))  # a faulty rewrite raises here, before the previous file is touched
    if written["quiz"] != _quiz_entries(quiz):
        raise ProfileError("the quiz history did not survive being written; the profile was not changed")
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        with locked(target):  # the swap itself is exclusive across processes too (a caller's read-modify-write block holds the same lock around it)
            with open(temp, "w", encoding="utf-8") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, target)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise


def record_quiz(path, question_id, concept, outcome, moment=None, graded=None):
    """Remember one answered question in the profile (its history and next review time); returns the question's entry. ProfileError when the
    profile cannot be used (it is then left untouched) or the question or outcome is invalid; a concept PreReqAI does not know is refused."""
    from backend import spaced_review

    if outcome not in ("knew", "missed") or not _QUESTION_ID.fullmatch(str(question_id)):
        raise ProfileError("an outcome is 'knew' or 'missed' and a question id looks like 'Softmax:1'")
    name = vocabulary().get(key(concept))
    if name is None:
        raise ProfileError(f"{concept!r} is not a concept PreReqAI knows")
    with locked(path):
        profile, problem = load_full(path)
        if problem:
            raise ProfileError(problem)
        quiz = profile["quiz"]
        if question_id not in quiz and len(quiz) >= MAX_QUESTIONS:
            raise ProfileError(f"the profile already holds {MAX_QUESTIONS} questions")
        quiz[question_id] = spaced_review.update(quiz.get(question_id), name, outcome, moment or spaced_review.now(), graded)
        save(path, profile["known"], profile["studied"], quiz)
    return quiz[question_id]


def record_review(path, question_id, concept, grade, moment=None, difficulty="Medium", graded=None):
    """Remember a review answered with a grade (again, hard, good, easy): the question's ease and next review time follow spaced_review.graded_update. Same errors as record_quiz."""
    from backend import spaced_review

    if grade not in spaced_review.GRADES or not _QUESTION_ID.fullmatch(str(question_id)):
        raise ProfileError("a grade is again, hard, good or easy and a question id looks like 'Softmax:1'")
    name = vocabulary().get(key(concept))
    if name is None:
        raise ProfileError(f"{concept!r} is not a concept PreReqAI knows")
    with locked(path):
        profile, problem = load_full(path)
        if problem:
            raise ProfileError(problem)
        quiz = profile["quiz"]
        if question_id not in quiz and len(quiz) >= MAX_QUESTIONS:
            raise ProfileError(f"the profile already holds {MAX_QUESTIONS} questions")
        quiz[question_id] = spaced_review.graded_update(quiz.get(question_id), name, grade, moment or spaced_review.now(), difficulty, graded)
        save(path, profile["known"], profile["studied"], quiz)
    return quiz[question_id]


def review_schedule(path, today=None, cap=10, horizon_days=30):
    """(schedule, problem): the profile's due and upcoming reviews laid out over days under a daily cap (see spaced_review.schedule)."""
    from backend import spaced_review

    profile, problem = load_full(path)
    if problem:
        return {"days": [], "deferred": [], "cap": cap, "backlog_days": 0}, problem
    moment = spaced_review.now()
    queue = spaced_review.queue(profile["quiz"], moment, upcoming_limit=len(profile["quiz"]))
    return spaced_review.schedule([*queue["due"], *queue["upcoming"]], today or moment.date(), cap, horizon_days), ""


def review_queue(path, moment=None, upcoming_limit=10):
    """(queue, problem): the due and upcoming reviews of a profile (see spaced_review.queue), or an empty queue and why the profile cannot be used."""
    from backend import spaced_review

    profile, problem = load_full(path)
    return spaced_review.queue(profile["quiz"], moment or spaced_review.now(), upcoming_limit), problem


def mastery(quiz):
    """[{concept, questions, attempts, knew, missed, status, evidence, graded_attempts, graded_correct, high_confidence_wrong, last_seen}] per concept of a profile's quiz history, by name.
    Mastery needs ASSESSED evidence, answers the system checked itself (see backend/tutor/diagnostic.py); a self-reported "knew" never establishes it.
    status: "needs_practice" when any question was last missed; "mastered" when the uncertainty-aware estimate of backend/mastery_model.py says so (a high probability whose lower end is also high,
    from enough graded answers on at least two different questions; confident wrong answers weigh heavily); p_mastery, mastery_low, mastery_high and mastery_reason explain it; "self_reported" when the old self-graded rule (two questions, each "knew" with a
    streak of 2) holds but the assessed evidence does not; otherwise "progressing". evidence: "assessed" when the concept has any assessed answer, else "self_reported"."""
    by_concept = {}
    for entry in quiz.values():
        by_concept.setdefault(entry["concept"], []).append(entry)
    result = []
    for concept in sorted(by_concept):
        entries = by_concept[concept]
        graded = sum(e.get("graded_attempts", 0) for e in entries)
        confident_wrong = sum(e.get("high_confidence_wrong", 0) for e in entries)
        from backend import mastery_model

        estimate = mastery_model.estimate_entries([(e.get("question_id", str(n)), e) for n, e in enumerate(sorted(entries, key=lambda e: (e.get("first_seen", ""), e.get("last_seen", ""))))])
        if any(e["last_outcome"] == "missed" for e in entries):
            status = "needs_practice"
        elif estimate is not None and estimate["mastered"]:
            status = "mastered"
        elif not graded and len(entries) >= 2 and all(e["streak"] >= 2 for e in entries):
            status = "self_reported"
        else:
            status = "progressing"
        result.append({"concept": concept, "questions": len(entries), "attempts": sum(e["attempts"] for e in entries), "knew": sum(e["knew"] for e in entries),
                       "missed": sum(e["missed"] for e in entries), "status": status, "evidence": "assessed" if graded else "self_reported", "graded_attempts": graded,
                       "graded_correct": sum(e.get("graded_correct", 0) for e in entries), "high_confidence_wrong": confident_wrong, "last_seen": max(e["last_seen"] for e in entries),
                       **({"p_mastery": estimate["p"], "mastery_low": estimate["low"], "mastery_high": estimate["high"], "mastery_reason": estimate["reason"]} if estimate else {})})
    return result


def mastered(quiz):
    """{concept: {questions, attempts, knew, last_seen}} for the concepts a profile's quiz history rates mastered (see mastery()): the evidence other papers' plans may offer as "you may
    already know this". It is only ever offered; nothing is removed from a plan because of it."""
    return {item["concept"]: {"questions": item["questions"], "attempts": item["attempts"], "knew": item["knew"], "last_seen": item["last_seen"]}
            for item in mastery(quiz) if item["status"] == "mastered"}


def _canonical(names, label, vocab, problems):
    kept = []
    for name in names:
        if not isinstance(name, str) or not 0 < len(name.strip()) <= MAX_NAME_CHARS:
            problems.append(f"{label}: {str(name)[:40]!r} is not a concept name")
        elif key(name) not in vocab:
            problems.append(f"{label}: {name.strip()!r} is not a concept PreReqAI knows")
        else:
            kept.append(vocab[key(name)])
    return kept


def update_profile(path, add_known=(), add_studied=(), forget=(), forget_quiz=()):
    """Change a profile atomically and return (profile, notes). `add_known` / `add_studied` add concepts (known wins over studied); `forget` removes concepts from both
    lists; `forget_quiz` removes the quiz history of concepts (a profile's mastery is otherwise never touched). A missing file starts an empty profile. ProfileInputError
    for any invalid name or too long a list (nothing is written); ProfileError for an unreadable profile (left as it is); OSError when it cannot be saved (the previous
    file is kept)."""
    lists = {"add_known": list(add_known), "add_studied": list(add_studied), "forget": list(forget), "forget_quiz": list(forget_quiz)}
    if any(len(names) > 200 for names in lists.values()):
        raise ProfileInputError("at most 200 concepts can be changed in one request")
    vocab, problems = vocabulary(), []
    canonical = {label: _canonical(names, label, vocab, problems) for label, names in lists.items()}
    if problems:
        raise ProfileInputError("; ".join(problems))
    with locked(path):
        profile, problem = load_full(path)
        if problem:
            raise ProfileError(problem)
        known, studied, quiz, notes = profile["known"], profile["studied"], profile["quiz"], []
        gone = {key(name) for name in canonical["forget"]}
        known = [name for name in known if key(name) not in gone]
        studied = [name for name in studied if key(name) not in gone]
        known = _dedupe([*known, *canonical["add_known"]], vocab)
        for name in canonical["add_studied"]:
            if key(name) in {key(k) for k in known}:
                notes.append(f"{name} is already known, so it was not also marked studied")
        studied = [name for name in _dedupe([*studied, *canonical["add_studied"]], vocab) if key(name) not in {key(k) for k in known}]
        wiped = {key(name) for name in canonical["forget_quiz"]}
        quiz = {identifier: entry for identifier, entry in quiz.items() if key(entry["concept"]) not in wiped}
        save(path, known, studied, quiz)
    return {"known": known, "studied": studied, "quiz": quiz}, notes


def profile_names(directory):
    """The names of the profiles in the directory (files NAME.json with a valid name), sorted."""
    folder = Path(directory).expanduser()
    if not folder.is_dir():
        return []
    return sorted(item.stem for item in folder.glob("*.json") if _NAME.fullmatch(item.stem) and item.is_file())


def profile_path(directory, name=None):
    """The file of the named profile inside the configured directory ("default" when no name is given); None for an invalid name."""
    name = "default" if name in (None, "") else name
    return Path(directory).expanduser() / f"{name}.json" if _NAME.fullmatch(str(name)) else None


def configured_directory():
    value = os.environ.get(PROFILE_DIR_ENV, "").strip()
    return value or None


class ProfileRun:
    """One analysis with a profile: `known` and `studied` are what to analyse with (the profile first, then the explicit values); `warnings`
    are about the profile; finish(outcome) saves the progress of a successful analysis and returns the outcome with the profile's notes."""

    def __init__(self, path, known, studied):
        self.path, self.vocab = Path(path), vocabulary()
        self.profile_known, self.profile_studied, problem = load(self.path)
        self.warnings = [problem] if problem else []
        self.readable = not problem
        self.explicit_known, self.explicit_studied = list(known), list(studied)
        self.known = _dedupe([*self.profile_known, *known])
        self.studied = [n for n in _dedupe([*self.profile_studied, *studied]) if key(n) not in {key(k) for k in self.known}]  # known wins
        self.save_known, self.save_studied = self._valid(self.explicit_known, "known"), self._valid(self.explicit_studied, "studied")

    def _valid(self, names, label):
        kept = []
        for name in _dedupe(n for value in names for n in str(value).split(",")):
            if key(name) in self.vocab:
                kept.append(self.vocab[key(name)])
            else:
                self.warnings.append(f"{label} {name!r} is not a subject PreReqAI knows, so it was not saved to the learner profile")
        return kept

    def _personalise(self, outcome):
        """Attach the personalised plan to the report and the session (only runs that use a profile have one; the paper's own analysis is unchanged)."""
        from backend.prerequisites.personalised_plan import build_plan
        from backend.session import session_manager

        session = session_manager.get(outcome.get("session_id") or "")
        if session is None:
            return
        plan = build_plan(session.paper, {"known": self.profile_known, "studied": self.profile_studied})
        outcome["report"]["personalised_plan"] = session.report["personalised_plan"] = plan
        session.profile = self.path.stem  # quiz outcomes of this session go to this profile
        session_manager.save(session)

    def finish(self, outcome):
        implicit = {key(n) for n in (*self.profile_known, *self.profile_studied)} - {key(n) for n in (*self.explicit_known, *self.explicit_studied)}
        if isinstance(outcome, dict):
            names = outcome.get("warnings") or []  # a profile subject that this paper's plan does not contain is not a problem
            kept = [w for w in names if not any(f" {n!r} is not in this paper's study plan" in w for n in (*self.profile_known, *self.profile_studied)
                                                if key(n) in implicit)]
            outcome["warnings"] = [*kept, *self.warnings]
        if not isinstance(outcome, dict) or outcome.get("status") != "success":
            return outcome
        if not self.readable:
            outcome["warnings"].append(f"the learner profile {self.path} was not updated, so this analysis's progress was not saved")
            return outcome
        done = [item["concept"] for item in outcome.get("report", {}).get("study_progress", []) if item.get("completed")]
        with locked(self.path):
            known, studied, problem = load(self.path)  # read again: another run may have saved since this one started
            if problem:
                outcome["warnings"].append(problem)
                return outcome
            known = _dedupe([*known, *self.save_known], self.vocab)
            studied = _dedupe([*studied, *self.save_studied, *done], self.vocab)
            try:
                save(self.path, known, studied)
            except OSError as error:
                outcome["warnings"].append(f"the learner profile {self.path} could not be saved ({getattr(error, 'strerror', None) or error}); "
                                           "the previous profile is unchanged")
                return outcome
        self._personalise(outcome)
        outcome["profile"] = {"path": str(self.path), "known": known, "studied": [n for n in studied if key(n) not in {key(k) for k in known}]}
        return outcome
