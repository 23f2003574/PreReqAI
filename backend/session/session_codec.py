"""The saved-session file format: a versioned JSON envelope.

    {"format": "prereqai-session", "schema_version": 5, "session": <value>}

`<value>` is plain JSON for strings, numbers, booleans, null, lists and string-keyed dicts, and a tagged object for anything else:
    {"__t__": "dc", "c": "backend.models.paper.Paper", "f": {field: value, ...}}   a dataclass of this project (all its attributes)
    {"__t__": "tuple" | "set" | "frozenset", "v": [...]}                           the other containers
    {"__t__": "dict", "items": [[key, value], ...]}                                 a dict with non-string keys (or a "__t__" key)
    {"__t__": "enum", "c": "backend.x.Color", "v": "RED"}                           an enum member of this project
    {"__t__": "float", "v": "nan" | "inf" | "-inf"}                                 the floats JSON cannot hold

Loading never imports or runs anything: a class is accepted only if it is a dataclass (or enum) already defined in a `backend.*` module,
and objects are filled by setting their attributes, so a file can name nothing else. Attributes the file lacks are filled from the model's
defaults by the SessionManager after loading, and attributes the file has that the model no longer has are kept as they are, so an older or
newer file does not lose the learner's data. The version rules, migration from the older pickle files and the atomic writing are the
SessionManager's. Anything malformed, hostile, too deep or of an unsupported version raises SessionFormatError saying why."""
import dataclasses
import enum
import json
import math
import sys

FORMAT = "prereqai-session"
MAX_DEPTH = 100  # real sessions are about 10 deep; a hostile file must not exhaust the stack
_FLOATS = {"nan": math.nan, "inf": math.inf, "-inf": -math.inf}


class SessionFormatError(ValueError):
    """The file is not a usable saved session; the message says why."""


def _qualified(cls):
    return f"{cls.__module__}.{cls.__qualname__}"


def encode(value, _path=(), _depth=0):
    """`value` as JSON-ready data (see the module description); TypeError for a type that cannot be saved, SessionFormatError for a cycle."""
    if _depth > MAX_DEPTH:
        raise SessionFormatError("the session is nested too deeply to save")
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else {"__t__": "float", "v": "nan" if math.isnan(value) else "inf" if value > 0 else "-inf"}
    if isinstance(value, enum.Enum):
        return {"__t__": "enum", "c": _qualified(type(value)), "v": value.name}
    marker = id(value)
    if marker in _path:
        raise SessionFormatError("the session refers to itself, which the format cannot hold")
    path = (*_path, marker)
    if isinstance(value, list):
        return [encode(item, path, _depth + 1) for item in value]
    if isinstance(value, (tuple, set, frozenset)):
        return {"__t__": type(value).__name__, "v": [encode(item, path, _depth + 1) for item in value]}
    if isinstance(value, dict):
        if all(isinstance(key, str) and key != "__t__" for key in value):
            return {key: encode(item, path, _depth + 1) for key, item in value.items()}
        return {"__t__": "dict", "items": [[encode(key, path, _depth + 1), encode(item, path, _depth + 1)] for key, item in value.items()]}
    if dataclasses.is_dataclass(value) and not isinstance(value, type) and hasattr(value, "__dict__"):
        return {"__t__": "dc", "c": _qualified(type(value)), "f": {name: encode(item, path, _depth + 1) for name, item in vars(value).items()}}
    raise TypeError(f"a {type(value).__name__} cannot be saved in a session")


def _project_class(name, kind):
    module, _, qualname = name.rpartition(".")
    if not (module == "backend" or module.startswith("backend.")) or "." in qualname or not qualname:
        raise SessionFormatError(f"the file names {name!r}, which is not a class of this project")
    found = getattr(sys.modules.get(module), qualname, None)  # only modules that are already loaded: nothing is imported for a file
    if not isinstance(found, type) or found.__module__ != module:
        raise SessionFormatError(f"the file names {name!r}, which this version does not know")
    if kind == "dc" and not (dataclasses.is_dataclass(found) and hasattr(found, "__dataclass_fields__")) or kind == "enum" and not issubclass(found, enum.Enum):
        raise SessionFormatError(f"the file names {name!r}, which is not a saved-data class")
    return found


def decode(data, _depth=0):
    if _depth > MAX_DEPTH:
        raise SessionFormatError("the file is nested too deeply")
    if data is None or isinstance(data, (bool, int, float, str)):
        return data
    if isinstance(data, list):
        return [decode(item, _depth + 1) for item in data]
    if not isinstance(data, dict):
        raise SessionFormatError(f"unexpected {type(data).__name__} in the file")
    tag = data.get("__t__")
    if tag is None:
        return {key: decode(item, _depth + 1) for key, item in data.items()}
    if tag in ("tuple", "set", "frozenset"):
        items = data.get("v")
        if not isinstance(items, list):
            raise SessionFormatError(f"a {tag} in the file has no list of items")
        try:
            return {"tuple": tuple, "set": set, "frozenset": frozenset}[tag](decode(item, _depth + 1) for item in items)
        except TypeError as error:
            raise SessionFormatError(f"a {tag} in the file holds an unusable item") from error
    if tag == "dict":
        items = data.get("items")
        if not isinstance(items, list) or not all(isinstance(pair, list) and len(pair) == 2 for pair in items):
            raise SessionFormatError("a dict in the file is malformed")
        try:
            return {decode(key, _depth + 1): decode(item, _depth + 1) for key, item in items}
        except TypeError as error:
            raise SessionFormatError("a dict in the file has an unusable key") from error
    if tag == "float":
        if data.get("v") not in _FLOATS:
            raise SessionFormatError("a number in the file is malformed")
        return _FLOATS[data["v"]]
    if tag == "enum":
        cls = _project_class(str(data.get("c")), "enum")
        try:
            return cls[data.get("v")]
        except (KeyError, TypeError) as error:
            raise SessionFormatError(f"{data.get('c')} has no member {data.get('v')!r}") from error
    if tag == "dc":
        cls = _project_class(str(data.get("c")), "dc")
        fields = data.get("f")
        if not isinstance(fields, dict) or not all(isinstance(name, str) and name.isidentifier() and not name.startswith("__") for name in fields):
            raise SessionFormatError(f"the fields of a {data.get('c')} in the file are malformed")
        item = cls.__new__(cls)  # no __init__: the file's attributes are set as they were saved
        if not hasattr(item, "__dict__"):
            raise SessionFormatError(f"{data.get('c')} cannot be restored")
        for name, value in fields.items():
            item.__dict__[name] = decode(value, _depth + 1)
        return item
    raise SessionFormatError(f"the file has an unknown kind of value {tag!r}")


def dumps(session, version) -> bytes:
    """The session as the bytes of a saved file of `version` (compact and deterministic, so equal sessions give equal files)."""
    envelope = {"format": FORMAT, "schema_version": version, "session": encode(session)}
    return json.dumps(envelope, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")


def _reject_constant(name):
    raise SessionFormatError(f"the file contains {name}, which is not valid JSON")


def loads(raw: bytes):
    """(schema_version, session) from a saved file's bytes. SessionFormatError for anything that is not a usable envelope; the version
    is returned for the caller to judge, and the session is checked to be a LearningSession with sound top-level data."""
    try:
        envelope = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
    except (UnicodeDecodeError, ValueError, RecursionError) as error:
        if isinstance(error, SessionFormatError):
            raise
        raise SessionFormatError(f"the file is not valid JSON ({type(error).__name__})") from error
    if not isinstance(envelope, dict) or envelope.get("format") != FORMAT:
        raise SessionFormatError("the file is not a PreReqAI session")
    version = envelope.get("schema_version")
    if isinstance(version, bool) or not isinstance(version, int):
        raise SessionFormatError("the file has no usable schema_version")
    try:
        session = decode(envelope.get("session"))
    except RecursionError as error:
        raise SessionFormatError("the file is nested too deeply") from error
    return version, validate(session)


def validate(session):
    """The decoded value if it is a LearningSession whose main parts have the right shape, else SessionFormatError."""
    from backend.models import Paper
    from backend.session.learning_session import LearningSession

    if not isinstance(session, LearningSession):
        raise SessionFormatError("the file does not hold a learning session")
    expected = {"session_id": str, "paper_title": str, "report": dict, "conversation_history": list, "status": str}
    for name, kind in expected.items():
        if name in vars(session) and not isinstance(vars(session)[name], kind):
            raise SessionFormatError(f"the session's {name} has the wrong type")
    paper = vars(session).get("paper")
    if paper is not None and not isinstance(paper, Paper):
        raise SessionFormatError("the session's paper has the wrong type")
    return session
