"""Process exit codes shared by the PreReqAI CLI commands."""

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2
EXIT_CANCELLED = 130  # interrupted (Ctrl-C), the shell convention for SIGINT
EXIT_LIMIT_EXCEEDED = 124  # a resource limit stopped the run (the timeout(1) convention)
