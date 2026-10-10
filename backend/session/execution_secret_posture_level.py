from enum import Enum


class ExecutionSecretPostureLevel(
    str,
    Enum,
):
    """
    Defines the overall security standing an execution secret can be
    evaluated to hold, ranked from best to worst: SECURE, DEGRADED,
    COMPROMISED.
    """

    SECURE = "secure"

    DEGRADED = "degraded"

    COMPROMISED = "compromised"
