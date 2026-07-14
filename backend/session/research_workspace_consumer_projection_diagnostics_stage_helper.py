from contextlib import (
    contextmanager,
)


class _NoOpStageHandle:

    def mark_degraded(

        self,

        *,

        reason_code=None,

    ):

        return None


@contextmanager
def _noop_stage():

    yield _NoOpStageHandle()


def stage_or_noop(

    diagnostics,

    name,

    kind,

):
    """
    Returns the collector's real stage
    context manager when diagnostics are
    enabled, or a zero-cost no-op stage
    otherwise, so projectors can always
    use the same `with` block regardless
    of whether diagnostics were requested.
    """

    if diagnostics is None:

        return _noop_stage()

    return (

        diagnostics.stage(

            name=name,

            kind=kind,
        )
    )
