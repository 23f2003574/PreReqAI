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
SCHEMA_VERSION = 3
MAX_QUESTIONS = 5000
_QUESTION_ID = re.compile(r"[^:\x00]{1,200}:\d{1,4}")
_COUNTS = ("attempts", "knew", "missed", "streak")
_HISTORY_CODE = re.compile(r"[01][lmh](@\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)?")
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
        if "graded_history" in entry:  # the last graded answers in order (spaced_review.HISTORY_LIMIT at most): "1h@<UTC time>" is correct with high confidence at that time, "0l" wrong with low confidence (schema 2: no time)
            history = entry["graded_history"]
            if (not isinstance(history, list) or len(history) > spaced_review.HISTORY_LIMIT or len(history) > graded.get("graded_attempts", 0)
                    or not all(isinstance(code, str) and _HISTORY_CODE.fullmatch(code) for code in history)):
                raise ProfileError(f"'quiz' has an invalid entry for {identifier!r}")
            graded = {**graded, "graded_history": list(history)}
        if "graded_first_at" in entry:  # when the first timed answer was given; it dates the answers that rolled out of graded_history (an optional field added in schema 3, so no version bump)
            if spaced_review.parse_time(entry["graded_first_at"]) is None:
                raise ProfileError(f"'quiz' has an invalid entry for {identifier!r}")
            graded = {**graded, "graded_first_at": entry["graded_first_at"]}
        if "confusions" in entry:  # {other concept: times its answer was picked for this question}, an optional field (no version bump)
            found = entry["confusions"]
            if (not isinstance(found, dict) or len(found) > spaced_review.MAX_CONFUSIONS
                    or not all(isinstance(k, str) and 0 < len(k) <= MAX_NAME_CHARS and isinstance(v, int) and not isinstance(v, bool) and 0 < v <= 10**6 for k, v in found.items())):
                raise ProfileError(f"'quiz' has an invalid entry for {identifier!r}")
            graded = {**graded, "confusions": dict(found)}
        if "ease" in entry or "last_grade" in entry:  # present only on entries reviewed with a grade (again, hard, good, easy)
            if (isinstance(entry.get("ease"), bool) or not isinstance(entry.get("ease"), (int, float)) or not 1.3 <= entry["ease"] <= 3.5 or entry.get("last_grade") not in spaced_review.GRADES):
                raise ProfileError(f"'quiz' has an invalid entry for {identifier!r}")
            graded = {**graded, "ease": entry["ease"], "last_grade": entry["last_grade"]}
        result[identifier] = {**graded, "concept": entry["concept"].strip(), **{name: entry[name] for name in _COUNTS}, "last_outcome": entry["last_outcome"],
                              "first_seen": entry["first_seen"], "last_seen": entry["last_seen"], "interval_hours": entry["interval_hours"], "due": entry["due"]}
    return result


def parse_full(raw):
    """{"known": [...], "studied": [...], "quiz": {...}} from the bytes of a version 1, 2 or 3 profile file (older versions are read without loss and written as version 3), or ProfileError saying why it cannot be used."""
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


_CACHE_LIMIT = 32
_cache = {}  # resolved path -> (file signature, parsed profile)
_cache_lock = threading.Lock()
cache_stats = {"hits": 0, "parses": 0}


def _signature(target):
    info = target.stat()
    return (info.st_mtime_ns, info.st_size, info.st_ino)


def load_cached(path):
    """Like load_full, for read-only callers that ask again and again (every plan, calendar and curriculum request reads the session's profile): the parsed profile is kept while the file's modification
    time, size and inode are unchanged, so a save (which replaces the file) or any edit makes the next call parse it again. A file that is missing, unreadable or unusable is never cached. Each call gets
    its own copy, so a caller that changes it cannot change what the next one reads."""
    from copy import deepcopy

    target = Path(path)
    try:
        signature = _signature(target)
    except OSError:
        return load_full(target)
    name = str(target.resolve())
    with _cache_lock:
        held = _cache.get(name)
        if held is not None and held[0] == signature:
            cache_stats["hits"] += 1
            return deepcopy(held[1]), ""
    profile, problem = load_full(target)
    cache_stats["parses"] += 1
    if not problem:
        try:
            after = _signature(target)
        except OSError:
            return profile, problem
        if after == signature:  # the file did not change while it was being read
            with _cache_lock:
                if len(_cache) >= _CACHE_LIMIT:
                    _cache.pop(next(iter(_cache)))
                _cache[name] = (signature, deepcopy(profile))
    return profile, problem


def clear_cache():
    with _cache_lock:
        _cache.clear()


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
            _backup_older_version(target)
            os.replace(temp, target)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise


def _backup_older_version(target):
    """Before an older profile (schema 1 or 2) is first rewritten as schema 3, keep its bytes once as NAME.json.v<N>.bak; an existing backup is never replaced, and a file that cannot be read as an older
    profile is not copied. A backup that cannot be written stops the save (ProfileError), so the original is never replaced without its copy."""
    try:
        if not target.is_file():
            return
        raw = target.read_bytes()
        version = json.loads(raw.decode("utf-8-sig")).get("schema_version")
    except (OSError, ValueError, AttributeError):
        return
    if isinstance(version, bool) or not isinstance(version, int) or not 1 <= version < SCHEMA_VERSION:
        return
    backup = target.with_name(f"{target.name}.v{version}.bak")
    if backup.exists():
        return
    temp = backup.with_name(f".{backup.name}.{os.getpid()}.tmp")
    try:
        temp.write_bytes(raw)
        os.replace(temp, backup)
    except OSError as error:
        temp.unlink(missing_ok=True)
        raise ProfileError(f"the older profile could not be backed up ({getattr(error, 'strerror', None) or error}); it was left unchanged") from None


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


def mastery(quiz, now=None):
    """[{concept, questions, attempts, knew, missed, status, evidence, graded_attempts, graded_correct, high_confidence_wrong, last_seen}] per concept of a profile's quiz history, by name.
    Mastery needs ASSESSED evidence, answers the system checked itself (see backend/tutor/diagnostic.py); a self-reported "knew" never establishes it.
    status: "needs_practice" when any question was last missed; "mastered" when the uncertainty-aware estimate of backend/mastery_model.py says so (a high probability whose lower end is also high,
    from enough graded answers on at least two different questions; confident wrong answers weigh heavily); p_mastery, mastery_low, mastery_high and mastery_reason explain it; "needs_refresh" when it was mastered at its last graded answer but the forgetting model of backend/mastery_model.py (a probability that falls toward the prior by 10% of the remainder per review interval, a stated heuristic) puts it below REFRESH_P now; p_mastery is then the decayed probability, p_at_last_answer the earlier one, and `refresh_reason` says how far it fell; "self_reported" when the old self-graded rule (two questions, each "knew" with a
    streak of 2) holds but the assessed evidence does not; otherwise "progressing". evidence: "assessed" when the concept has any assessed answer, else "self_reported"."""
    from backend import spaced_review

    moment = now or spaced_review.now()
    by_concept = {}
    for entry in quiz.values():
        by_concept.setdefault(entry["concept"], []).append(entry)
    result = []
    for concept in sorted(by_concept):
        entries, refresh_reason = by_concept[concept], None
        graded = sum(e.get("graded_attempts", 0) for e in entries)
        confident_wrong = sum(e.get("high_confidence_wrong", 0) for e in entries)
        from backend import mastery_model

        estimate = mastery_model.estimate_entries([(e.get("question_id", str(n)), e) for n, e in enumerate(sorted(entries, key=lambda e: (e.get("first_seen", ""), e.get("last_seen", ""))))])
        evidence_at = mastery_model.last_evidence_time(entries)
        if estimate is not None and evidence_at is not None:
            newest = max((e for e in entries if e.get("graded_attempts")), key=lambda e: e.get("last_seen", ""))
            estimate = mastery_model.apply_decay(estimate, (moment - evidence_at).total_seconds() / 86400, float(newest.get("interval_hours", 72.0)) / 24)
        if any(e["last_outcome"] == "missed" for e in entries):
            status = "needs_practice"
        elif estimate is not None and estimate["mastered"]:
            status = "mastered"
        elif estimate is not None and estimate.get("lapsed"):
            status, refresh_reason = "needs_refresh", estimate["reason"]
        elif not graded and len(entries) >= 2 and all(e["streak"] >= 2 for e in entries):
            status = "self_reported"
        else:
            status = "progressing"
        result.append({"concept": concept, "questions": len(entries), "attempts": sum(e["attempts"] for e in entries), "knew": sum(e["knew"] for e in entries),
                       "missed": sum(e["missed"] for e in entries), "status": status, "evidence": "assessed" if graded else "self_reported", "graded_attempts": graded,
                       "graded_correct": sum(e.get("graded_correct", 0) for e in entries), "high_confidence_wrong": confident_wrong, "last_seen": max(e["last_seen"] for e in entries),
                       **({"p_mastery": estimate["p"], "mastery_low": estimate["low"], "mastery_high": estimate["high"], "mastery_reason": estimate["reason"]} if estimate else {}),
                       **({"spaced_blocks": estimate["spaced_blocks"]} if estimate and "spaced_blocks" in estimate else {}),
                       **({"spacing_ready_at": estimate["spacing_ready_at"]} if estimate and "spacing_ready_at" in estimate else {}),
                       **({"p_at_last_answer": estimate["p_at_last_answer"], "retention": estimate["retention"], "days_since_evidence": estimate["days_since_evidence"]} if estimate and "p_at_last_answer" in estimate else {}),
                       **({"refresh_reason": refresh_reason} if refresh_reason else {})})
    return result


def describe_mastery(item):
    """One line about a mastery() item for the command line: status, counts, the estimate with its range (when there is one), why, and how long ago the last graded answer was; every estimate field is optional."""
    line = f"{item['concept']}: {item['status'].replace('_', ' ')} ({item['knew']} knew, {item['missed']} missed over {item['questions']} question(s))"
    if isinstance(item.get("p_mastery"), (int, float)):
        low, high = item.get("mastery_low", item["p_mastery"]), item.get("mastery_high", item["p_mastery"])
        line += f"; estimated mastery {item['p_mastery']:.2f} (range {low:.2f}-{high:.2f}; a heuristic, not a calibrated probability)"
    if isinstance(item.get("days_since_evidence"), (int, float)):
        line += f"; last graded answer {'today' if item['days_since_evidence'] < 1 else format(item['days_since_evidence'], '.0f') + ' day(s) ago'}"
    why = item.get("refresh_reason") or item.get("mastery_reason")
    return line + (f"\n    why: {why}" if why else "")


def mastered(quiz, now=None):
    """{concept: {questions, attempts, knew, last_seen}} for the concepts a profile's quiz history rates mastered (see mastery()): the evidence other papers' plans may offer as "you may
    already know this". A concept whose mastery has lapsed (status "needs_refresh") is not offered. It is only ever offered; nothing is removed from a plan because of it."""
    return {item["concept"]: {"questions": item["questions"], "attempts": item["attempts"], "knew": item["knew"], "last_seen": item["last_seen"]}
            for item in mastery(quiz, now) if item["status"] == "mastered"}


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


RECURRING_CONFUSION = 2  # a pair counts as a recurring confusion from this many wrong answers: one slip is not a misconception


def confusion_pairs(quiz, minimum=RECURRING_CONFUSION):
    """[{concept, confused_with, count, questions}] the concept pairs the learner keeps mixing up: over a profile's quiz entries, the number of wrong answers of `concept` questions that picked the answer of
    `confused_with`, for pairs with at least `minimum` of them, most frequent first. A single wrong answer never changes a mastery estimate; this only reports the pattern."""
    pairs = {}
    for identifier, entry in (quiz or {}).items():
        for other, count in (entry.get("confusions") or {}).items():
            row = pairs.setdefault((entry.get("concept"), other), {"concept": entry.get("concept"), "confused_with": other, "count": 0, "questions": []})
            row["count"] += count
            row["questions"].append(identifier)
    return sorted((row for row in pairs.values() if row["count"] >= minimum), key=lambda row: (-row["count"], row["concept"], row["confused_with"]))
