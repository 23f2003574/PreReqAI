from enum import Enum


class ExecutionSecretOperation(
    str,
    Enum,
):
    """
    Defines the operations an execution secret access policy may
    grant a principal against a secret.
    """

    READ = "read"

    ROTATE = "rotate"

    DELETE = "delete"
