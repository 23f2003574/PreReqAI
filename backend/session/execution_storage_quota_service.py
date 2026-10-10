from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from numbers import (
    Real,
)

from uuid import uuid4

from .execution_storage_quota import (
    ExecutionStorageQuota,
)

from .execution_storage_quota_error import (
    ExecutionStorageQuotaError,
)


class ExecutionStorageQuotaService:
    """
    Prevents individual execution scopes from consuming unlimited
    persistent storage.

    Behavior:
    - configure() replaces a scope's quota with a freshly built one
      and resets its recorded usage to zero
    - can_allocate() reports whether size can currently be allocated
      for a scope, without mutating any stored usage; a disabled
      quota always reports True
    - allocate() records size as used against a scope's quota,
      rejecting an amount that would push usage past max_size; a
      disabled quota is never enforced
    - release() reduces a scope's recorded usage by size, but never
      below zero, regardless of whether the quota is enabled
    - usage() reports a scope's current quota record

    Each quota is isolated per scope_id.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._quotas_by_scope = {}
        self._lock = RLock()

    def configure(self, scope_id: str, max_size: float) -> ExecutionStorageQuota:
        """
        Replace scope_id's quota with a fresh one for max_size,
        resetting its used_size to zero.

        Raises:
            ExecutionStorageQuotaError: If scope_id is None or blank,
                or max_size is not a positive number
        """

        self._validate_text(scope_id, "scope ID")

        quota = ExecutionStorageQuota(
            quota_id=str(uuid4()),
            scope_id=scope_id,
            max_size=max_size,
            used_size=0.0,
            enabled=True,
        )

        with self._lock:
            self._quotas_by_scope[scope_id] = quota

        return quota

    def can_allocate(self, scope_id: str, size: float) -> bool:
        """
        Whether size can currently be allocated for scope_id, without
        mutating any stored usage. Always True when the quota is
        disabled.

        Raises:
            ExecutionStorageQuotaError: If scope_id is None or blank,
                size is not a positive number, or no quota is
                configured for scope_id
        """

        self._validate_text(scope_id, "scope ID")
        self._validate_amount(size)

        with self._lock:
            quota = self._resolve(scope_id)

            if not quota.enabled:
                return True

            return quota.used_size + size <= quota.max_size

    def allocate(self, scope_id: str, size: float) -> ExecutionStorageQuota:
        """
        Record size as used against scope_id's quota.

        Raises:
            ExecutionStorageQuotaError: If scope_id is None or blank,
                size is not a positive number, no quota is configured
                for scope_id, or size would exceed the active quota's
                remaining capacity
        """

        self._validate_text(scope_id, "scope ID")
        self._validate_amount(size)

        with self._lock:
            quota = self._resolve(scope_id)

            if quota.enabled and quota.used_size + size > quota.max_size:
                raise ExecutionStorageQuotaError(
                    f"Cannot allocate {size!r} for scope ID {scope_id!r}: it would exceed the "
                    f"active limit of {quota.max_size!r} (already used {quota.used_size!r})."
                )

            updated = replace(quota, used_size=quota.used_size + size)
            self._quotas_by_scope[scope_id] = updated

            return updated

    def release(self, scope_id: str, size: float) -> ExecutionStorageQuota:
        """
        Reduce scope_id's recorded usage by size.

        Raises:
            ExecutionStorageQuotaError: If scope_id is None or blank,
                size is not a positive number, no quota is configured
                for scope_id, or size would make usage negative
        """

        self._validate_text(scope_id, "scope ID")
        self._validate_amount(size)

        with self._lock:
            quota = self._resolve(scope_id)

            if size > quota.used_size:
                raise ExecutionStorageQuotaError(
                    f"Cannot release {size!r} for scope ID {scope_id!r}: it would make usage "
                    f"negative (currently used {quota.used_size!r})."
                )

            updated = replace(quota, used_size=quota.used_size - size)
            self._quotas_by_scope[scope_id] = updated

            return updated

    def usage(self, scope_id: str) -> ExecutionStorageQuota:
        """
        The current quota record for scope_id.

        Raises:
            ExecutionStorageQuotaError: If scope_id is None or blank,
                or no quota is configured for it
        """

        self._validate_text(scope_id, "scope ID")

        with self._lock:
            return self._resolve(scope_id)

    def _resolve(self, scope_id: str) -> ExecutionStorageQuota:
        quota = self._quotas_by_scope.get(scope_id)

        if quota is None:
            raise ExecutionStorageQuotaError(f"No quota is configured for scope ID {scope_id!r}.")

        return quota

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionStorageQuotaError(f"Cannot use an empty or blank {field_name}.")

    @staticmethod
    def _validate_amount(amount) -> None:
        if amount is None or isinstance(amount, bool) or not isinstance(amount, Real) or amount <= 0:
            raise ExecutionStorageQuotaError(f"Cannot use a non-positive amount: {amount!r}.")
