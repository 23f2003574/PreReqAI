from abc import ABC, abstractmethod
from typing import Optional

from .models import RiskProfileRollout


class RiskProfileRolloutStore(ABC):
    """Persistence operations for risk profile rollout records.

    Mirrors the exact save/get/list_for_-- shape every other stateful
    record store in this repository already uses. There is no delete():
    a rollout, once started, is only ever replaced by a fresh
    dataclasses.replace() result written back via save() under the same
    rollout_id -- its full stage-by-stage history lives in
    provenance/current_stage, never in a second set of records.
    """

    @abstractmethod
    def save(self, rollout: RiskProfileRollout) -> RiskProfileRollout:
        ...

    @abstractmethod
    def get(self, rollout_id: str) -> Optional[RiskProfileRollout]:
        ...

    @abstractmethod
    def list_for_profile_scope(self, profile_id: str, scope_id: str) -> list:
        ...
