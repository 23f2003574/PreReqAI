from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ExecutionSecretAccessService,
    ExecutionSecretAccessToken,
    ExecutionSecretOperation as Operation,
    ExecutionSecretTokenError as Error,
    ExecutionSecretTokenService,
    ExecutionSecretTrustLevel as TrustLevel,
    ExecutionSecretTrustPolicy,
    ExecutionSecretTrustService,
)


def _build(ttl=timedelta(minutes=5)):
    trust_service = ExecutionSecretTrustService()
    access_service = ExecutionSecretAccessService()
    token_service = ExecutionSecretTokenService(trust_service, access_service, ttl=ttl)
    return trust_service, access_service, token_service


def _authorize(trust_service, access_service, principal="component-a", secret_id="secret-1"):
    trust_service.register(
        ExecutionSecretTrustPolicy(
            policy_id=f"trust-{principal}",
            principal=principal,
            trust_level=TrustLevel.STANDARD,
            allowed_operations=frozenset(),
        )
    )
    access_service.grant(secret_id, principal, {Operation.READ})


class TestExecutionSecretTokenService:
    def test_issue_and_validate(self):
        trust_service, access_service, token_service = _build()
        _authorize(trust_service, access_service)

        token = token_service.issue("secret-1", "component-a")

        assert isinstance(token, ExecutionSecretAccessToken)
        assert token.secret_id == "secret-1"
        assert token.principal == "component-a"
        assert token.status == "ACTIVE"
        assert token_service.validate(token.token_id) is True

    def test_validate_unknown_token_is_false(self):
        _trust_service, _access_service, token_service = _build()

        assert token_service.validate("unknown-token") is False

    def test_policy_denial_without_trust(self):
        _trust_service, access_service, token_service = _build()
        access_service.grant("secret-1", "component-a", {Operation.READ})

        with pytest.raises(Error):
            token_service.issue("secret-1", "component-a")

    def test_policy_denial_without_access_grant(self):
        trust_service, _access_service, token_service = _build()
        trust_service.register(
            ExecutionSecretTrustPolicy(
                policy_id="trust-1",
                principal="component-a",
                trust_level=TrustLevel.STANDARD,
                allowed_operations=frozenset(),
            )
        )

        with pytest.raises(Error):
            token_service.issue("secret-1", "component-a")

    def test_expiry(self):
        trust_service, access_service, token_service = _build(ttl=timedelta(seconds=-1))
        _authorize(trust_service, access_service)

        token = token_service.issue("secret-1", "component-a")

        assert token_service.validate(token.token_id) is False
        assert token_service.expired() == [token]

        with pytest.raises(Error):
            token_service.revoke(token.token_id)

    def test_revoke(self):
        trust_service, access_service, token_service = _build()
        _authorize(trust_service, access_service)
        token = token_service.issue("secret-1", "component-a")

        revoked = token_service.revoke(token.token_id)

        assert revoked.status == "REVOKED"
        assert token_service.validate(token.token_id) is False

        with pytest.raises(Error):
            token_service.revoke(token.token_id)

    def test_principal_isolation(self):
        trust_service, access_service, token_service = _build()
        _authorize(trust_service, access_service, principal="component-a")
        _authorize(trust_service, access_service, principal="component-b")

        token_a = token_service.issue("secret-1", "component-a")
        token_b = token_service.issue("secret-1", "component-b")

        assert token_service.active("component-a") == [token_a]
        assert token_service.active("component-b") == [token_b]

    def test_raw_value_exclusion(self):
        with pytest.raises(Error):
            ExecutionSecretAccessToken(
                token_id="vault://api-key",
                secret_id="secret-1",
                principal="component-a",
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            )

    def test_token_id_cannot_equal_secret_id(self):
        with pytest.raises(Error):
            ExecutionSecretAccessToken(
                token_id="secret-1",
                secret_id="secret-1",
                principal="component-a",
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            )

    def test_rejects_invalid_arguments(self):
        trust_service, access_service, token_service = _build()
        _authorize(trust_service, access_service)

        with pytest.raises(Error):
            token_service.issue("", "component-a")

        with pytest.raises(Error):
            token_service.issue("secret-1", "")

        with pytest.raises(Error):
            token_service.validate("")

        with pytest.raises(Error):
            token_service.revoke("")

        with pytest.raises(Error):
            token_service.active("")
