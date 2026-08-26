from dataclasses import dataclass

REPLACE = "REPLACE"
REMOVE = "REMOVE"
OPERATIONS = frozenset({REPLACE, REMOVE})

READY = "READY"
REJECTED = "REJECTED"
STATUSES = frozenset({READY, REJECTED})


@dataclass(frozen=True)
class LLMCodePatchPlan:
    """A precise, reviewable patch plan for one validated Commit #2 LLMCodeFixSuggestion.

    operations is a non-empty list of {"op", "location", "value"} dicts --
    op is REPLACE or REMOVE (value is None for REMOVE), reusing the same
    RFC 6902-style op/location/value shape rather than a new one. target
    (and every operation's own location) is always exactly the suggestion's
    own already-grounded target -- the same real generated-output location
    Commit #1/#2 already validated -- so a patch plan can never touch
    anything the suggestion didn't concern. status is READY when every
    operation is well-formed and unambiguous (no two operations target the
    same location), REJECTED when they conflict (see
    LLMCodePatchService.plan()). This plan is never applied -- it is only
    ever a proposal for a later commit.
    """

    plan_id: str
    suggestion_id: str
    target: str
    operations: list
    rationale: str
    status: str
