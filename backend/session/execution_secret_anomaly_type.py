from enum import Enum


class ExecutionSecretAnomalyType(
    str,
    Enum,
):
    """
    Defines the suspicious secret access patterns an execution secret
    anomaly service can detect.
    """

    REVOKED_ACCESS = "revoked_access"

    REPEATED_DENIAL = "repeated_denial"

    EXPIRED_LEASE_ACCESS = "expired_lease_access"
