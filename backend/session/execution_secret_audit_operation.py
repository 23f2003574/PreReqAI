from enum import Enum


class ExecutionSecretAuditOperation(
    str,
    Enum,
):
    """
    Defines the categories of security-sensitive secret operation an
    execution secret audit event may record.
    """

    ACCESS = "access"

    ROTATION = "rotation"

    LEASE = "lease"

    REVOCATION = "revocation"
