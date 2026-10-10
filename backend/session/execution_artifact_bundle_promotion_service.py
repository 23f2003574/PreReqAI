from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from .artifact_bundle_promotion import (
    ArtifactBundlePromotion,
)

from .execution_artifact_bundle_promotion_error import (
    ExecutionArtifactBundlePromotionError,
)


class ExecutionArtifactBundlePromotionService:
    """
    Promotes complete, verified execution artifact bundles atomically
    between lifecycle environments, using an existing execution
    artifact bundle service to confirm a bundle is ready, a version
    resolver to identify each version's owning artifact, and an
    existing execution artifact promotion service to record each
    version's own promotion.

    The service's responsibility is bundle-level promotion
    bookkeeping and atomicity only. It does not verify checksums or
    move artifact contents itself.

    Behavior:
    - A bundle may only be promoted once it is complete and every
      version in it is verified
    - promote() is all-or-nothing: it first confirms every version in
      the bundle can be promoted to target before promoting any of
      them, so a single version that cannot be promoted (e.g. it is
      already in target) leaves every other version untouched
    - A bundle may not be promoted into an environment it is already
      in
    - rollback() marks a promotion ROLLED_BACK; the bundle is no
      longer considered current in that promotion's target
      environment afterward

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_artifact_bundle_service, execution_artifact_promotion_service, version_resolver):
        """
        Args:
            execution_artifact_bundle_service: The service used to
                look up a bundle and confirm it is complete and
                verified before it is promoted. Any object exposing
                `get(bundle_id)` and `verify(bundle_id)` (returning an
                object with a boolean `.complete`), each raising if
                the bundle is unknown, is accepted
            execution_artifact_promotion_service: The service used to
                record each version's own promotion. Any object
                exposing `promote(version_id, target, artifact_id)`
                and `history(version_id)` is accepted
            version_resolver: The resolver used to identify the
                artifact a version belongs to. Any object exposing
                `resolve(version_id)`, returning an object with an
                `.artifact_id`, and raising if the version is
                unknown, is accepted
        """

        self._execution_artifact_bundle_service = execution_artifact_bundle_service
        self._execution_artifact_promotion_service = execution_artifact_promotion_service
        self._version_resolver = version_resolver
        self._promotions_by_id = {}
        self._promotion_ids_by_bundle = {}
        self._current_promotion_id_by_bundle_environment = {}
        self._lock = RLock()

    def promote(self, bundle_id: str, target: str) -> ArtifactBundlePromotion:
        """
        Promote a complete, verified bundle into a target environment,
        atomically promoting every version it groups.

        Raises:
            ExecutionArtifactBundlePromotionError: If bundle_id or
                target is None or blank, the bundle is unknown,
                incomplete, or unverified, target equals the bundle's
                current environment, or any version in the bundle
                cannot be promoted to target
        """

        self._validate_id(bundle_id, "bundle ID")
        self._validate_id(target, "target")

        with self._lock:
            bundle = self._get_bundle(bundle_id)
            self._ensure_bundle_verified(bundle_id)

            history = self._promotion_ids_by_bundle.get(bundle_id, [])
            source = self._promotions_by_id[history[-1]].target if history else None

            if source == target:
                raise ExecutionArtifactBundlePromotionError(
                    f"Cannot promote bundle ID {bundle_id!r} to environment {target!r}: it is already there."
                )

            plan = self._plan_atomic_promotion(bundle.version_ids, target)

            for version_id, artifact_id in plan:
                self._execution_artifact_promotion_service.promote(version_id, target, artifact_id)

            promotion = ArtifactBundlePromotion(bundle_id=bundle_id, target=target, source=source)

            self._promotions_by_id[promotion.promotion_id] = promotion
            self._promotion_ids_by_bundle.setdefault(bundle_id, []).append(promotion.promotion_id)
            self._current_promotion_id_by_bundle_environment[(bundle_id, target)] = promotion.promotion_id

            return promotion

    def rollback(self, promotion_id: str) -> ArtifactBundlePromotion:
        """
        Roll back a bundle promotion. The bundle is no longer
        considered current in that promotion's target environment
        afterward.

        Raises:
            ExecutionArtifactBundlePromotionError: If promotion_id is
                None or blank, no promotion is registered under it, or
                it has already been rolled back
        """

        self._validate_id(promotion_id, "promotion ID")

        with self._lock:
            promotion = self._promotions_by_id.get(promotion_id)

            if promotion is None:
                raise ExecutionArtifactBundlePromotionError(
                    f"No promotion is known under promotion ID {promotion_id!r}."
                )

            if promotion.status != "PROMOTED":
                raise ExecutionArtifactBundlePromotionError(
                    f"Cannot roll back promotion ID {promotion_id!r}: it is {promotion.status}, not PROMOTED."
                )

            rolled_back = replace(promotion, status="ROLLED_BACK")
            self._promotions_by_id[promotion_id] = rolled_back

            key = (promotion.bundle_id, promotion.target)

            if self._current_promotion_id_by_bundle_environment.get(key) == promotion_id:
                del self._current_promotion_id_by_bundle_environment[key]

            return rolled_back

    def current(self, bundle_id: str, environment: str) -> ArtifactBundlePromotion:
        """
        Look up the active promotion of a bundle into an environment.

        Raises:
            ExecutionArtifactBundlePromotionError: If bundle_id or
                environment is None or blank, or the bundle has no
                active promotion into it
        """

        self._validate_id(bundle_id, "bundle ID")
        self._validate_id(environment, "environment")

        with self._lock:
            promotion_id = self._current_promotion_id_by_bundle_environment.get((bundle_id, environment))

            if promotion_id is None:
                raise ExecutionArtifactBundlePromotionError(
                    f"Bundle ID {bundle_id!r} has no active promotion into environment {environment!r}."
                )

            return self._promotions_by_id[promotion_id]

    def history(self, bundle_id: str) -> list:
        """
        List every promotion of a bundle, oldest first, reflecting
        each promotion's current status.

        Raises:
            ExecutionArtifactBundlePromotionError: If bundle_id is
                None or blank
        """

        self._validate_id(bundle_id, "bundle ID")

        with self._lock:
            return [
                self._promotions_by_id[promotion_id]
                for promotion_id in self._promotion_ids_by_bundle.get(bundle_id, [])
            ]

    def _plan_atomic_promotion(self, version_ids, target: str) -> list:
        plan = []

        for version_id in version_ids:
            try:
                version = self._version_resolver.resolve(version_id)
            except Exception as error:
                raise ExecutionArtifactBundlePromotionError(
                    f"No version is known under version ID {version_id!r}."
                ) from error

            existing_targets = {
                entry.target for entry in self._execution_artifact_promotion_service.history(version_id)
            }

            if target in existing_targets:
                raise ExecutionArtifactBundlePromotionError(
                    f"Cannot promote bundle atomically: version ID {version_id!r} has already been "
                    f"promoted to environment {target!r}."
                )

            plan.append((version_id, version.artifact_id))

        return plan

    def _get_bundle(self, bundle_id: str):
        try:
            return self._execution_artifact_bundle_service.get(bundle_id)
        except Exception as error:
            raise ExecutionArtifactBundlePromotionError(
                f"No bundle is known under bundle ID {bundle_id!r}."
            ) from error

    def _ensure_bundle_verified(self, bundle_id: str) -> None:
        result = self._execution_artifact_bundle_service.verify(bundle_id)

        if not result.complete:
            raise ExecutionArtifactBundlePromotionError(
                f"Cannot promote bundle ID {bundle_id!r}: it is not complete and verified."
            )

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactBundlePromotionError(f"Cannot use an empty or blank {field_name}.")
