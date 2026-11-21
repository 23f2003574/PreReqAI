"""The learner's confirmed custom concepts: a small local, versioned JSON file read by concept detection.

`{"format": "prereqai-custom-concepts", "schema_version": 1, "concepts": [{"name", "aliases", "definition", "confirmed_on"}]}` at PREREQAI_CUSTOM_CONCEPTS, or custom_concepts.json in the profile
directory (PREREQAI_PROFILE_DIR); with neither set there is no store and nothing custom is detected. A concept is added only by an explicit request from the learner (the API, the page or the
command line), never from a candidate list. Writes are atomic and exclusive across processes; a file that cannot be used is reported and left unchanged, and detection then uses the registry only.
A custom concept is detected by its name and aliases like any other, and has no prerequisite rules, definition or quiz questions of its own."""
import json
import os
import re
import threading
from pathlib import Path

from backend.filelock import locked

FORMAT, SCHEMA_VERSION = "prereqai-custom-concepts", 1
ENV = "PREREQAI_CUSTOM_CONCEPTS"
MAX_CONCEPTS, MAX_NAME = 500, 80
_NAME = re.compile(r"[A-Za-z][A-Za-z0-9 \-/']{2,79}")
_cache = {}
_guard = threading.Lock()


class CustomConceptError(ValueError):
    pass


def store_path():
    explicit = os.environ.get(ENV, "").strip()
    if explicit:
        return Path(explicit)
    directory = os.environ.get("PREREQAI_PROFILE_DIR", "").strip()
    return Path(directory) / "custom_concepts.json" if directory else None


def _validate(raw):
    try:
        data = json.loads(raw)
    except ValueError as error:
        raise CustomConceptError(f"it is not valid JSON ({error})") from None
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise CustomConceptError(f"it is not a custom concept store (format {FORMAT!r})")
    version = data.get("schema_version")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise CustomConceptError("its schema_version is missing or not a positive integer")
    if version > SCHEMA_VERSION:
        raise CustomConceptError(f"it was saved by a newer PreReqAI (version {version}; this one reads up to {SCHEMA_VERSION})")
    items, concepts = data.get("concepts", []), []
    if not isinstance(items, list) or len(items) > MAX_CONCEPTS:
        raise CustomConceptError(f"'concepts' must be a list of at most {MAX_CONCEPTS}")
    for item in items:
        if not (isinstance(item, dict) and isinstance(item.get("name"), str) and _NAME.fullmatch(item["name"].strip())):
            raise CustomConceptError("a concept has no valid name")
        aliases = item.get("aliases", [])
        if not (isinstance(aliases, list) and all(isinstance(a, str) and _NAME.fullmatch(a.strip()) for a in aliases)):
            raise CustomConceptError(f"the aliases of {item['name']!r} are not valid")
        concepts.append({"name": item["name"].strip(), "aliases": [a.strip() for a in aliases], "definition": str(item.get("definition", ""))[:500], "confirmed_on": str(item.get("confirmed_on", ""))})
    return concepts


def load(path=None):
    """(concepts, problem): the confirmed concepts and "" for a readable or missing store; [] and why otherwise (never raises)."""
    path = path or store_path()
    if path is None or not Path(path).exists():
        return [], ""
    try:
        stamp = (Path(path).stat().st_mtime_ns, Path(path).stat().st_size)
        with _guard:
            if _cache.get(str(path), (None,))[0] == stamp:
                return _cache[str(path)][1], ""
        concepts = _validate(Path(path).read_bytes())
        with _guard:
            _cache[str(path)] = (stamp, concepts)
        return concepts, ""
    except CustomConceptError as error:
        return [], f"the custom concept store {path} was not used and was left unchanged: {error}"
    except OSError as error:
        return [], f"the custom concept store {path} could not be read ({getattr(error, 'strerror', None) or error})"


def _write(path, concepts):
    from datetime import datetime  # noqa: F401

    text = json.dumps({"format": FORMAT, "schema_version": SCHEMA_VERSION, "concepts": concepts}, indent=2) + "\n"
    _validate(text.encode("utf-8"))
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        with open(temp, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise


def _registry_terms():
    from backend.concepts.concept_registry import ConceptRegistry

    return {term.lower() for concept in ConceptRegistry().all() for term in (concept.name, *concept.aliases)}


def add(name, aliases=(), definition="", today=None):
    """Confirm a concept. CustomConceptError when there is no store, the store cannot be used, the name or an alias is not valid, or one of them is already a registry or custom term."""
    path = store_path()
    if path is None:
        raise CustomConceptError(f"there is nowhere to keep it: set {ENV} or PREREQAI_PROFILE_DIR")
    name, aliases = " ".join(str(name).split()), [" ".join(str(a).split()) for a in aliases]
    for term in (name, *aliases):
        if not _NAME.fullmatch(term):
            raise CustomConceptError(f"{term!r} is not a valid concept name (3 to {MAX_NAME} letters, digits, spaces, hyphens)")
    with locked(path):
        concepts, problem = load(path)
        if problem:
            raise CustomConceptError(problem)
        taken = _registry_terms() | {t.lower() for c in concepts for t in (c["name"], *c["aliases"])}
        clash = next((t for t in (name, *aliases) if t.lower() in taken), None)
        if clash:
            raise CustomConceptError(f"{clash!r} is already a concept PreReqAI knows")
        if len(concepts) >= MAX_CONCEPTS:
            raise CustomConceptError(f"the store already holds {MAX_CONCEPTS} concepts")
        from datetime import date

        concepts = [*concepts, {"name": name, "aliases": aliases, "definition": str(definition)[:500], "confirmed_on": (today or date.today()).isoformat()}]
        _write(path, concepts)
    return concepts[-1]


def remove(name):
    """Forget a confirmed concept; True when it existed."""
    path = store_path()
    if path is None:
        return False
    with locked(path):
        concepts, problem = load(path)
        if problem:
            raise CustomConceptError(problem)
        kept = [c for c in concepts if c["name"].lower() != str(name).strip().lower()]
        if len(kept) == len(concepts):
            return False
        _write(path, kept)
    return True
