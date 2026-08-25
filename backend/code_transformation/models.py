from dataclasses import dataclass
from datetime import datetime


REFACTOR = "REFACTOR"
FIX = "FIX"
OPTIMIZE = "OPTIMIZE"
ADAPT = "ADAPT"
TRANSFORMATION_TYPES = frozenset({REFACTOR, FIX, OPTIMIZE, ADAPT})


@dataclass(frozen=True)
class LLMCodeTransformationPlan:
    """A reviewable, deterministic plan for transforming one or more notebook cells.

    changes is a tuple of {"cell_index", "description", "proposed_source"}
    dicts, one per affected cell -- every cell_index is guaranteed (by
    LLMCodeTransformationService) to be one of target_cells, and target_cells
    is guaranteed to reference cells that existed in the notebook analysis
    at plan-build time. This plan never mutates notebook source itself; it
    is only ever a proposal for a human, review step, or later commit to
    apply.
    """

    plan_id: str
    notebook_id: str
    target_cells: tuple
    transformation_type: str
    changes: tuple
    rationale: str
    confidence: float
    generated_at: datetime
