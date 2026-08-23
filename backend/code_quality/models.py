from dataclasses import dataclass


BUG = "BUG"
RISK = "RISK"
SMELL = "SMELL"
DEAD_CODE = "DEAD_CODE"
CATEGORIES = frozenset({BUG, RISK, SMELL, DEAD_CODE})

INFO = "INFO"
WARNING = "WARNING"
ERROR = "ERROR"
SEVERITIES = frozenset({INFO, WARNING, ERROR})


@dataclass(frozen=True)
class LLMCodeFinding:
    """One code-quality finding about a notebook cell.

    cell_id is "cell:<index>", the same convention Commit #2 uses for
    dependency-graph node ids, so a finding's evidence location is always
    traceable back to one exact cell in the Commit #1 analysis.
    """

    finding_id: str
    notebook_id: str
    cell_id: str
    category: str
    severity: str
    message: str
    confidence: float
