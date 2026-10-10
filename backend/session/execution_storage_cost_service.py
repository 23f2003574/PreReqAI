from datetime import (
    datetime,
    timezone,
)

from .execution_storage_integrity_check import (
    STATUS_OK,
)

from .execution_storage_tier import (
    TIER_COLD,
    TIER_HOT,
    TIER_WARM,
)

from .execution_storage_cost_profile import (
    ExecutionStorageCostProfile,
)

from .execution_storage_cost_profile_error import (
    ExecutionStorageCostProfileError,
)

COST_BY_TIER = {
    TIER_HOT: 1.0,
    TIER_WARM: 0.3,
    TIER_COLD: 0.05,
}


class ExecutionStorageCostService:
    """
    Selects storage resources for cost-efficient tier placement
    without violating retention or integrity requirements.

    Composes with:
    - an existing storage tiering service (anything exposing
      `tier(resource_id) -> str`, `evaluate(resource_id) -> str`, and
      `transition(resource_id, tier)`, matching
      ExecutionStorageTieringService), used to read a resource's
      current tier, deterministically recommend one based on access
      patterns, and apply an accepted recommendation
    - an existing storage retention service (anything exposing
      `eligible(resource_id) -> bool`, matching
      ExecutionStorageRetentionService), used to confirm a resource is
      not actively protected before any tier change is considered
    - an existing storage integrity service (anything exposing
      `check(resource_id) -> object with .status`, matching
      ExecutionStorageIntegrityService), used to refuse any tier
      change for a corrupted resource
    - an existing storage volume service (anything exposing
      `for_scope(scope_id) -> tuple of objects with .volume_id`),
      used to enumerate a scope's resources for candidates()

    Behavior:
    - estimate() reports a resource's current estimated storage cost,
      a deterministic function of its current tier
    - recommend() calculates a full cost profile: a corrupted or
      actively-protected (retention-ineligible) resource is always
      recommended to stay at its current tier; otherwise the
      recommended tier is the tiering service's own deterministic,
      access-pattern-based evaluation
    - candidates() reports the resources under a scope whose
      recommended tier currently differs from their current tier
    - apply() re-validates a resource is neither corrupted nor
      actively protected, then applies its freshly recomputed
      recommendation via the tiering service; it refuses to apply
      anything for a resource that fails that revalidation, even if
      the recommendation would coincidentally be a no-op

    Recommendations are always recomputed from current, live state,
    so identical inputs always yield the identical recommendation.

    The service is:
    - Thread-safe: recommend() and estimate() perform no mutation of
      their own; apply() delegates its mutation entirely to the
      composed tiering service
    """

    def __init__(self, tiering_service, retention_service, integrity_service, volume_service):
        self._tiering_service = tiering_service
        self._retention_service = retention_service
        self._integrity_service = integrity_service
        self._volume_service = volume_service

    def estimate(self, resource_id: str) -> float:
        """
        The estimated storage cost of resource_id at its current
        tier.

        Raises:
            ExecutionStorageCostProfileError: If resource_id is None
                or blank, or it is unknown
        """

        self._validate_text(resource_id, "resource ID")

        current_tier = self._safe_call(self._tiering_service.tier, resource_id)

        return COST_BY_TIER[current_tier]

    def recommend(self, resource_id: str) -> ExecutionStorageCostProfile:
        """
        Calculate a fresh cost profile for resource_id, including its
        recommended tier.

        Raises:
            ExecutionStorageCostProfileError: If resource_id is None
                or blank, or it is unknown
        """

        self._validate_text(resource_id, "resource ID")

        current_tier = self._safe_call(self._tiering_service.tier, resource_id)
        estimated_cost = COST_BY_TIER[current_tier]

        if self._is_corrupt(resource_id) or not self._is_eligible(resource_id):
            recommended_tier = current_tier
        else:
            recommended_tier = self._safe_call(self._tiering_service.evaluate, resource_id)

        return ExecutionStorageCostProfile(
            resource_id=resource_id,
            current_tier=current_tier,
            estimated_cost=estimated_cost,
            recommended_tier=recommended_tier,
            calculated_at=datetime.now(timezone.utc),
        )

    def candidates(self, scope_id: str) -> tuple:
        """
        The resources under scope_id whose recommended tier currently
        differs from their current tier.

        Raises:
            ExecutionStorageCostProfileError: If scope_id is None or
                blank
        """

        self._validate_text(scope_id, "scope ID")

        volumes = self._safe_call(self._volume_service.for_scope, scope_id)

        result = []

        for volume in volumes:
            try:
                profile = self.recommend(volume.volume_id)
            except ExecutionStorageCostProfileError:
                continue

            if profile.recommended_tier != profile.current_tier:
                result.append(volume.volume_id)

        return tuple(result)

    def apply(self, resource_id: str) -> ExecutionStorageCostProfile:
        """
        Apply resource_id's freshly recomputed recommendation via the
        tiering service.

        Raises:
            ExecutionStorageCostProfileError: If resource_id is None
                or blank, it is unknown, it is corrupted, or it is
                actively protected (retention-ineligible)
        """

        self._validate_text(resource_id, "resource ID")

        if self._is_corrupt(resource_id):
            raise ExecutionStorageCostProfileError(
                f"Cannot apply a recommendation for resource ID {resource_id!r}: it is "
                f"corrupted."
            )

        if not self._is_eligible(resource_id):
            raise ExecutionStorageCostProfileError(
                f"Cannot apply a recommendation for resource ID {resource_id!r}: it is "
                f"actively protected."
            )

        profile = self.recommend(resource_id)

        if profile.recommended_tier != profile.current_tier:
            self._safe_call(self._tiering_service.transition, resource_id, profile.recommended_tier)

        return profile

    def _is_corrupt(self, resource_id: str) -> bool:
        try:
            check = self._integrity_service.check(resource_id)
        except Exception:
            return False

        return check.status != STATUS_OK

    def _is_eligible(self, resource_id: str) -> bool:
        try:
            return bool(self._retention_service.eligible(resource_id))
        except Exception:
            return False

    @staticmethod
    def _safe_call(fn, *args):
        try:
            return fn(*args)
        except Exception as error:
            raise ExecutionStorageCostProfileError(f"Cannot resolve: {error}") from error

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionStorageCostProfileError(f"Cannot use an empty or blank {field_name}.")
