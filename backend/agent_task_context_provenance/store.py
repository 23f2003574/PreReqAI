from abc import ABC, abstractmethod

from .models import ContextProvenanceRecord


class ProvenanceRecordStore(ABC):
    """Persistence for immutable ContextProvenanceRecord history.

    Deliberately append-only: save() adds a new record, and there is no
    update()/delete() at all -- immutability (Rule: "immutable provenance
    records once written") is enforced structurally by this interface
    simply not offering a way to change or remove one, not merely
    documented.
    """

    @abstractmethod
    def save(self, record: ContextProvenanceRecord) -> ContextProvenanceRecord:
        ...

    @abstractmethod
    def list_for_task(self, task_id: str) -> list:
        ...
