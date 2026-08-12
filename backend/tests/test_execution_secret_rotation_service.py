from datetime import (
    datetime,
    timedelta,
    timezone,
)

from threading import (
    Thread,
)

import pytest

from backend.session import (
    ExecutionSecret,
    ExecutionSecretRotation,
    ExecutionSecretRotationError as Error,
    ExecutionSecretRotationService,
    ExecutionSecretService,
)


def _build():
    secret_service = ExecutionSecretService()
    rotation_service = ExecutionSecretRotationService(secret_service)
    return secret_service, rotation_service


def _register(secret_service, secret_id, session_id="session-1", name="api-key", expires_at=None):
    return secret_service.register(
        session_id,
        ExecutionSecret(
            secret_id=secret_id,
            session_id=session_id,
            name=name,
            value_ref="vault://initial",
            expires_at=expires_at,
        ),
    )


class TestExecutionSecretRotationService:
    def test_rotate_secret(self):
        secret_service, rotation_service = _build()
        _register(secret_service, "secret-1")

        rotation = rotation_service.rotate("secret-1")

        assert isinstance(rotation, ExecutionSecretRotation)
        assert rotation.secret_id == "secret-1"
        assert rotation.previous_ref is None
        assert rotation.current_ref

    def test_current_reference(self):
        secret_service, rotation_service = _build()
        _register(secret_service, "secret-1")

        rotation = rotation_service.rotate("secret-1")

        assert rotation_service.current("secret-1") == rotation.current_ref

        second = rotation_service.rotate("secret-1")

        assert second.previous_ref == rotation.current_ref
        assert rotation_service.current("secret-1") == second.current_ref

    def test_current_before_any_rotation_is_an_error(self):
        _secret_service, rotation_service = _build()

        with pytest.raises(Error):
            rotation_service.current("secret-1")

    def test_history_ordering(self):
        secret_service, rotation_service = _build()
        _register(secret_service, "secret-1")

        first = rotation_service.rotate("secret-1")
        second = rotation_service.rotate("secret-1")
        third = rotation_service.rotate("secret-1")

        assert rotation_service.history("secret-1") == [first, second, third]

    def test_history_is_isolated_per_secret(self):
        secret_service, rotation_service = _build()
        _register(secret_service, "secret-1")
        _register(secret_service, "secret-2", name="other-key")

        rotation_service.rotate("secret-1")
        rotation_service.rotate("secret-2")

        assert len(rotation_service.history("secret-1")) == 1
        assert len(rotation_service.history("secret-2")) == 1

    def test_rollback(self):
        secret_service, rotation_service = _build()
        _register(secret_service, "secret-1")

        first = rotation_service.rotate("secret-1")
        second = rotation_service.rotate("secret-1")

        rollback = rotation_service.rollback(second.rotation_id)

        assert rollback.previous_ref == second.current_ref
        assert rollback.current_ref == first.current_ref
        assert rotation_service.current("secret-1") == first.current_ref
        assert rotation_service.history("secret-1") == [first, second, rollback]

    def test_rollback_rejects_rotation_with_no_previous_ref(self):
        secret_service, rotation_service = _build()
        _register(secret_service, "secret-1")

        first = rotation_service.rotate("secret-1")

        with pytest.raises(Error):
            rotation_service.rollback(first.rotation_id)

    def test_rollback_rejects_unknown_rotation(self):
        _secret_service, rotation_service = _build()

        with pytest.raises(Error):
            rotation_service.rollback("unknown-rotation")

    def test_expired_secret_rejection(self):
        secret_service, rotation_service = _build()
        _register(
            secret_service,
            "secret-1",
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )

        with pytest.raises(Error):
            rotation_service.rotate("secret-1")

    def test_atomic_rotation(self):
        secret_service, rotation_service = _build()
        _register(secret_service, "secret-1")

        thread_count = 16
        threads = [
            Thread(target=rotation_service.rotate, args=("secret-1",)) for _ in range(thread_count)
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        history = rotation_service.history("secret-1")

        assert len(history) == thread_count
        assert len({rotation.rotation_id for rotation in history}) == thread_count
        assert len({rotation.current_ref for rotation in history}) == thread_count

        current_ref_by_previous_ref = {
            rotation.previous_ref: rotation.current_ref for rotation in history
        }

        # Exactly one rotation started the chain, and every other
        # rotation's previous_ref is some other rotation's current_ref,
        # so following the chain from None visits every rotation
        # exactly once with no lost or duplicated update, ending at
        # whatever rotate() left as current.
        ref = None
        visited = []

        for _ in range(thread_count):
            ref = current_ref_by_previous_ref.pop(ref)
            visited.append(ref)

        assert len(visited) == thread_count
        assert not current_ref_by_previous_ref
        assert rotation_service.current("secret-1") == ref
