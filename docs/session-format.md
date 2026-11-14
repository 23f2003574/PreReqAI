# Saved session format

With `PREREQAI_SESSION_DIR` set, each session is saved as `<session-id>.session`, a UTF-8 JSON file (`backend/session/session_codec.py`):

```json
{"format": "prereqai-session", "schema_version": 4, "session": {"__t__": "dc", "c": "backend.session.learning_session.LearningSession", "f": {"...": "..."}}}
```

- Plain JSON stands for strings, numbers, booleans, null, lists and string-keyed dicts. Everything else is a tagged object: `dc` (a dataclass of this
  project with all its attributes), `tuple`, `set`, `frozenset`, `dict` (non-string keys), `enum`, `float` (`nan`, `inf`).
- **Versions.** 1-3 were pickle files (1: before versions existed; 2: stamped; 3: quiz attempts). 4 is this JSON envelope, the only format written.
  A change that renames, removes or retypes a field must bump `SCHEMA_VERSION` and add its own migration step; a change that only adds a field with
  a default needs none, because missing fields are filled from the model's defaults on every load.
- **Compatibility.** Attributes a file has that the model no longer knows are kept (and written back); a file of a newer version, or one whose
  fields cannot be restored, is unreadable (HTTP 404 "Session could not be restored"), never half loaded. The reason is logged by `prereqai.session`.
- **Migration.** A version 1-3 pickle is read with the restricted unpickler (only dataclasses of `backend.*`), upgraded, and rewritten as JSON, but only
  after the JSON is read back and shown to reproduce the same session; otherwise the old file is kept untouched.
- **Safety.** Loading never imports or runs anything: a class is accepted only if it is a dataclass or enum already defined in a loaded `backend.*`
  module, objects are filled by setting attributes, nesting is limited, `NaN` constants and unknown tags are refused. A file saved under another
  session id is refused. The directory should still be private.
- **Writing.** Each save is written to its own temporary file, flushed to disk, renamed over the session file and the directory is synced, so an
  interrupted save leaves the previous file whole; saves of one session run one at a time.
