from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class LLMTransformationDiff:
    """An explicit, reviewable source diff generated from a validated LLMCodeTransformationPlan.

    changes is a tuple with exactly one entry per plan.changes entry --
    {"cell_index", "description", "original_source", "proposed_source",
    "unified_diff", "additions", "deletions"} -- so every diff maps back to
    the planned change it came from. additions/deletions are the totals
    across all changes. Generating this record never mutates the plan, the
    notebook analysis, or the notebook source itself; it is only ever a
    proposal for later review or application.
    """

    diff_id: str
    plan_id: str
    changes: tuple
    additions: int
    deletions: int
    generated_at: datetime
