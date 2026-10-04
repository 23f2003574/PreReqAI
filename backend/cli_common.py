"""Process exit codes shared by the PreReqAI CLI commands."""

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2
EXIT_CANCELLED = 130  # interrupted (Ctrl-C), the shell convention for SIGINT
EXIT_TIMEOUT = 124  # an operation timed out (the timeout(1) convention)
EXIT_LIMIT_EXCEEDED = 123  # a configured resource limit stopped the run
