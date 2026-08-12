from threading import (
    Thread,
)

import pytest

from backend.session import (
    ExecutionSecretAccessService,
    ExecutionSecretOperation as Operation,
    ExecutionSecretTokenRotation,
    ExecutionSecretTokenRotationError as Error,
    ExecutionSecretTokenRotationService,
    ExecutionSecretTokenService,
    ExecutionSecretTrustLevel as TrustLevel,
    ExecutionSecretTrustPolicy,
    ExecutionSecretTrustService,
)


def _build():
    trust_service = ExecutionSecretTrustService()
    access_service = ExecutionSecretAccessService()
    token_service = ExecutionSecretTokenService(trust_service, access_service)
    rotation_service = ExecutionSecretTokenRotationService(token_service, access_service)
    return trust_service, access_service, token_service, rotation_service


def _authorize(trust_service, access_service, secret_id="secret-1", principal="component-a", operations=None):
    trust_service.register(
        ExecutionSecretTrustPolicy(
            policy_id=f"trust-{secret_id}-{principal}",
            principal=principal,
            trust_level=TrustLevel.STANDARD,
            allowed_operations=frozenset(),
        )
    )
    access_service.grant(secret_id, principal, operations or {Operation.READ, Operation.ROTATE})


class TestExecutionSecretTokenRotationService:
    def test_rotate_token(self):
        trust_service, access_service, token_service, rotation_service = _build()
        _authorize(trust_service, access_service)

        rotation = rotation_service.rotate("secret-1", "component-a")

        assert isinstance(rotation, ExecutionSecretTokenRotation)
        assert rotation.secret_id == "secret-1"
        assert rotation.previous_token_id is None
        assert rotation.current_token_id
        assert token_service.validate(rotation.current_token_id) is True

    def test_current_token_lookup(self):
        trust_service, access_service, _token_service, rotation_service = _build()
        _authorize(trust_service, access_service)

        first = rotation_service.rotate("secret-1", "component-a")
        assert rotation_service.current("secret-1", "component-a") == first.current_token_id

        second = rotation_service.rotate("secret-1", "component-a")

        assert second.previous_token_id == first.current_token_id
        assert rotation_service.current("secret-1", "component-a") == second.current_token_id

    def test_current_before_any_rotation_is_an_error(self):
        _trust_service, _access_service, _token_service, rotation_service = _build()

        with pytest.raises(Error):
            rotation_service.current("secret-1", "component-a")

    def test_previous_token_revocation(self):
        trust_service, access_service, token_service, rotation_service = _build()
        _authorize(trust_service, access_service)

        first = rotation_service.rotate("secret-1", "component-a")
        second = rotation_service.rotate("secret-1", "component-a")

        # Immediately after rotation the previous token is still
        # untouched, unrelated to the new one.
        assert token_service.validate(first.current_token_id) is True

        revoked_token_id = rotation_service.revoke_previous(second.rotation_id)

        assert revoked_token_id == first.current_token_id
        assert token_service.validate(first.current_token_id) is False
        assert token_service.validate(second.current_token_id) is True

    def test_revoke_previous_rejects_rotation_with_no_previous_token(self):
        trust_service, access_service, _token_service, rotation_service = _build()
        _authorize(trust_service, access_service)
        first = rotation_service.rotate("secret-1", "component-a")

        with pytest.raises(Error):
            rotation_service.revoke_previous(first.rotation_id)

    def test_revoke_previous_rejects_unknown_rotation(self):
        _trust_service, _access_service, _token_service, rotation_service = _build()

        with pytest.raises(Error):
            rotation_service.revoke_previous("unknown-rotation")

    def test_unauthorized_rotation(self):
        trust_service, access_service, _token_service, rotation_service = _build()
        # Authorized to READ, but never granted ROTATE.
        _authorize(trust_service, access_service, operations={Operation.READ})

        with pytest.raises(Error):
            rotation_service.rotate("secret-1", "component-a")

    def test_history_ordering(self):
        trust_service, access_service, _token_service, rotation_service = _build()
        _authorize(trust_service, access_service, principal="component-a")
        _authorize(trust_service, access_service, principal="component-b")

        first = rotation_service.rotate("secret-1", "component-a")
        second = rotation_service.rotate("secret-1", "component-b")
        third = rotation_service.rotate("secret-1", "component-a")

        assert rotation_service.history("secret-1") == [first, second, third]

    def test_rotation_does_not_affect_unrelated_tokens(self):
        trust_service, access_service, token_service, rotation_service = _build()
        _authorize(trust_service, access_service, principal="component-a")
        _authorize(trust_service, access_service, principal="component-b")

        rotation_a = rotation_service.rotate("secret-1", "component-a")
        rotation_b = rotation_service.rotate("secret-1", "component-b")

        rotation_service.rotate("secret-1", "component-a")
        rotation_service.revoke_previous(rotation_service.history("secret-1")[-1].rotation_id)

        # component-b's token is untouched by component-a's rotation.
        assert token_service.validate(rotation_b.current_token_id) is True
        assert rotation_a.current_token_id != rotation_b.current_token_id

    def test_atomic_rotation(self):
        trust_service, access_service, _token_service, rotation_service = _build()
        _authorize(trust_service, access_service)

        thread_count = 16
        threads = [
            Thread(target=rotation_service.rotate, args=("secret-1", "component-a")) for _ in range(thread_count)
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        history = rotation_service.history("secret-1")

        assert len(history) == thread_count
        assert len({rotation.rotation_id for rotation in history}) == thread_count
        assert len({rotation.current_token_id for rotation in history}) == thread_count

        current_by_previous = {
            rotation.previous_token_id: rotation.current_token_id for rotation in history
        }

        # Exactly one rotation started the chain, and following it
        # from None visits every rotation exactly once with no lost
        # or duplicated update, ending at whatever rotate() left as
        # current.
        token_id = None
        visited = []

        for _ in range(thread_count):
            token_id = current_by_previous.pop(token_id)
            visited.append(token_id)

        assert len(visited) == thread_count
        assert not current_by_previous
        assert rotation_service.current("secret-1", "component-a") == token_id

    def test_rejects_invalid_arguments(self):
        trust_service, access_service, _token_service, rotation_service = _build()
        _authorize(trust_service, access_service)

        with pytest.raises(Error):
            rotation_service.rotate("", "component-a")

        with pytest.raises(Error):
            rotation_service.rotate("secret-1", "")

        with pytest.raises(Error):
            rotation_service.current("", "component-a")

        with pytest.raises(Error):
            rotation_service.history("")

        with pytest.raises(Error):
            rotation_service.revoke_previous("")
