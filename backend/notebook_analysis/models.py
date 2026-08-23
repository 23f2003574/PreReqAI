from dataclasses import dataclass
from datetime import datetime


CODE_CELL = "code"
MARKDOWN_CELL = "markdown"
CELL_TYPES = frozenset({CODE_CELL, MARKDOWN_CELL})


@dataclass(frozen=True)
class NotebookCell:
    """One notebook cell, preserved at its original position.

    index is the cell's zero-based position in the source notebook, kept on
    the cell itself so downstream consumers can rely on it even if cells are
    later filtered or grouped by cell_type.
    """

    index: int
    cell_type: str
    source: str


@dataclass
class LLMNotebookAnalysis:
    """Structured understanding of a notebook, produced by the LLM before compilation.

    cells preserves the notebook's original order (Commit #1 rule); imports,
    functions, and dependencies are the LLM's structured findings, validated
    on the way in so a malformed LLM response can never become an analysis.
    """

    analysis_id: str
    notebook_id: str
    cells: list
    imports: list
    functions: list
    dependencies: list
    generated_at: datetime
