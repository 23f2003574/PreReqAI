"""The optional persistent learner profile: the subjects a learner already knows or has studied, kept across papers.

A profile is a small versioned JSON file in the same envelope style as a saved session (see session/session_codec.py):

    {"format": "prereqai-learner-profile", "schema_version": 1, "known": ["Linear Algebra", ...], "studied": ["Probability", ...]}

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
from pathlib import Path

FORMAT = "prereqai-learner-profile"
SCHEMA_VERSION = 1
MAX_BYTES = 1024 * 1024
MAX_SUBJECTS = 2000
MAX_NAME_CHARS = 200
PROFILE_DIR_ENV = "PREREQAI_PROFILE_DIR"
_NAME = re.compile(r"[A-Za-z0-9_-]{1,64}")
_lock = threading.RLock()  # one save at a time inside a server process


class ProfileError(ValueError):
    """The file is not a usable profile; the message says why."""


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
    return known, [name for name in _dedupe(lists[1], vocab) if key(name) not in {key(k) for k in known}]


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


def save(path, known, studied):
    """Write the profile atomically: the previous file stays intact if anything fails (the error is raised, the temporary file removed)."""
    target = Path(path)
    known = _dedupe(known)
    studied = [name for name in _dedupe(studied) if key(name) not in {key(k) for k in known}]
    text = json.dumps({"format": FORMAT, "schema_version": SCHEMA_VERSION, "known": known, "studied": studied}, indent=2) + "\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        with open(temp, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, target)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise


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
        with _lock:
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
        outcome["profile"] = {"path": str(self.path), "known": known, "studied": [n for n in studied if key(n) not in {key(k) for k in known}]}
        return outcome
