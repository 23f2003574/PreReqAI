# Learner profile format (version 2)

A learner profile is one JSON file, `<name>.json`, in `PREREQAI_PROFILE_DIR` (or any path given to the CLI). It is also the document the profile export
(`GET /api/profiles/{name}/export`, `prerequisites profile FILE --json`) writes and the import (`POST /api/profiles/{name}/import`) reads.

```json
{
  "format": "prereqai-learner-profile",
  "schema_version": 2,
  "known": ["Linear Algebra"],
  "studied": ["Probability"],
  "quiz": {
    "Softmax:1": {"concept": "Softmax", "attempts": 3, "knew": 2, "missed": 1, "streak": 1, "last_outcome": "knew",
                  "first_seen": "2026-11-20T10:00:00Z", "last_seen": "2026-11-22T10:00:00Z", "interval_hours": 72.0, "due": "2026-11-25T10:00:00Z"}
  }
}
```

* `known` and `studied` are concept names in PreReqAI's spelling; a concept is one or the other (known wins). Names PreReqAI does not know are never added by a request.
* `quiz` is the answer history per question (`<concept>:<number>`), with the next review time (see `backend/spaced_review.py`). Version 1 files have no `quiz` and are read as a version 2 profile with none; they become version 2 the next time they are saved.
* A file is rejected, and never overwritten, when it is not valid JSON, has another `format`, a newer `schema_version`, a malformed entry, more than 2000 names or 5000 questions, or is larger than 1 MiB.

## Managing a profile

| | API (needs `PREREQAI_PROFILE_DIR`) | CLI | Page |
|---|---|---|---|
| list | `GET /api/profiles` | | |
| show | `GET /api/profiles/{name}` | `prerequisites profile FILE` | Learner profile section |
| mark known / studied | `PATCH /api/profiles/{name}` `{"add_known": [...], "add_studied": [...]}` | `--known`, `--studied` | Mark known / Mark studied |
| forget concepts | `PATCH` `{"forget": [...]}` | `--forget` | Forget |
| delete quiz history | `PATCH` `{"forget_quiz": [...]}` | `--forget-quiz` | |
| export | `GET /api/profiles/{name}/export` | `--json` | Export link |
| import | `POST /api/profiles/{name}/import` (`?replace=true` to overwrite) | | |
| delete | `DELETE /api/profiles/{name}?confirm=true` | | |

Changes are written atomically (a temporary file, read back and checked, then moved into place), so an interrupted or faulty write keeps the previous profile. Quiz mastery
is never touched except by `forget_quiz` or `replace`. A forgotten concept no longer shapes later plans, because plans read only `known` and `studied`.
