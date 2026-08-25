from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class LLMNotebookSummary:
    """A structured, LLM-backed semantic summary of an existing, already-parsed notebook.

    Grounded entirely in the notebook's own backend.notebook_analysis
    record: every key_components entry names a real extracted function,
    and every dependency is drawn from the analysis's own
    imports/dependencies -- nothing here is invented. Producing a summary
    never modifies notebook source or the compiler; notebook_id is this
    record's own key, so the latest summary for a notebook replaces the
    previous one.
    """

    notebook_id: str
    purpose: str
    key_components: list
    inputs: list
    outputs: list
    dependencies: list
    generated_at: datetime
