from dataclasses import dataclass


IMPORT = "IMPORT"
FUNCTION = "FUNCTION"
DATA = "DATA"
MODEL = "MODEL"
DEPENDENCY_TYPES = frozenset({IMPORT, FUNCTION, DATA, MODEL})


@dataclass(frozen=True)
class LLMNotebookDependency:
    """One directed edge in a notebook's dependency graph.

    source -> target reads as "target depends on source": source must be
    available (imported, defined, produced) before target can run. Both
    source and target are node ids qualified with notebook_id (see
    LLMNotebookDependencyService._qualify) so they stay globally unique
    across notebooks even though upstream()/downstream() take a bare node_id.
    """

    dependency_id: str
    notebook_id: str
    source: str
    target: str
    dependency_type: str
    confidence: float
