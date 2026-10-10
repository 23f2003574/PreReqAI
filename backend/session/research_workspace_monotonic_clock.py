import time


class ResearchWorkspaceMonotonicClock:
    """
    Thin wrapper over a monotonic time
    source, so diagnostics timing can be
    replaced with a deterministic fake
    in tests.
    """

    def now(self):

        return time.perf_counter()
