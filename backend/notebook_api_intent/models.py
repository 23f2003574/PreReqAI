from dataclasses import dataclass

EXPOSURE_LEVELS = frozenset({"PUBLIC", "INTERNAL", "READ_ONLY", "UNSPECIFIED"})


@dataclass(frozen=True)
class LLMNotebookAPIIntent:
    """The LLM's grounded read of what API behavior a notebook's author intended.

    Every operation's 'function' (when not None) and every entry in
    candidate_functions is one of the notebook's own extracted functions
    (backend.notebook_analysis) -- nothing here is invented. An operation
    the LLM isn't confident about is marked ambiguous=True with
    function=None rather than guessing; validate() re-checks all of this
    against the notebook's current analysis. Extraction never mutates
    notebook source or the compiler; notebook_id is this record's own key.
    """

    notebook_id: str
    operations: list
    candidate_functions: list
    requested_exposure: str
    constraints: list
    confidence: float
