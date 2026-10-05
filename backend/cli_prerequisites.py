"""The `prerequisites` command of the PreReqAI CLI: `analyze` runs the same
workflow as POST /api/prerequisites/analyze by calling the same platform
method (PreReqAIPlatform.analyze), so the CLI and the API cannot diverge.
The platform is imported when the command runs, keeping other commands fast."""

import json
import signal
import sys
import threading

from backend.cli_common import EXIT_CANCELLED, EXIT_FAILURE, EXIT_LIMIT_EXCEEDED, EXIT_OK, EXIT_TIMEOUT


def add_prerequisites_parser(subparsers):
    prerequisites = subparsers.add_parser("prerequisites", help="Prerequisite Explorer: analyse a research paper")
    commands = prerequisites.add_subparsers(dest="prerequisites_command", required=True)
    analyze = commands.add_parser(
        "analyze",
        help="Analyse a paper PDF into concepts, prerequisites and a learning plan",
        description="Runs the paper analysis pipeline on a PDF file and opens a learning session in this process "
                    "(sessions are in memory and end with the command). Same workflow as POST /api/prerequisites/analyze.",
        epilog="Exit codes: 0 success; 1 analysis failed; 2 usage error; 123 a resource limit was reached; 124 an operation timed out; 130 cancelled (Ctrl-C).",
    )
    analyze.add_argument("paper", help="Path to the paper PDF")
    analyze.add_argument("--diagnose", action="store_true", dest="diagnose",
                         help="Also report per-stage durations, completed stages, warnings and run statistics "
                              "(in the --json result as `diagnostics`)")
    analyze.add_argument("--max-seconds", type=float, default=None, dest="max_seconds",
                         help="Stop the analysis once it has run this long (checked between stages; default: no limit)")
    analyze.add_argument("--max-file-mb", type=float, default=None, dest="max_file_mb",
                         help="Refuse a paper file larger than this many megabytes (default: no limit)")
    analyze.add_argument("--json", action="store_true", dest="as_json",
                         help="Print the workflow result envelope (status, stage, warnings, session_id, report, timings) as JSON")


def run_prerequisites_analyze(args, platform=None) -> int:
    if platform is None:
        from backend.platform import platform
    limits = None
    if args.max_seconds is not None or args.max_file_mb is not None:
        from backend.platform import AnalysisLimits

        limits = AnalysisLimits(
            max_seconds=args.max_seconds,
            max_file_bytes=None if args.max_file_mb is None else int(args.max_file_mb * 1024 * 1024),
        )
    cancelled = threading.Event()
    try:  # Ctrl-C asks the analysis to stop before its next stage; a second Ctrl-C interrupts immediately
        previous = signal.signal(signal.SIGINT, lambda *_: (cancelled.set(), signal.signal(signal.SIGINT, signal.default_int_handler)))
    except ValueError:  # not the main thread: no handler, cancellation is only available to library callers
        previous = None
    try:
        outcome = platform.analyze(args.paper, diagnostics=args.diagnose, should_cancel=cancelled.is_set, limits=limits)
    finally:
        if previous is not None:
            signal.signal(signal.SIGINT, previous)
    was_cancelled = outcome["status"] == "cancelled"
    limit_hit = outcome["status"] == "limit_exceeded"
    timed_out = outcome["status"] == "timeout"
    failed = outcome["status"] != "success"
    if args.as_json:
        print(json.dumps(outcome, indent=2))  # already plain JSON, in the order the API returns it (timings in stage order)
    elif timed_out:
        print(f"error: timed out at stage '{outcome['stage']}': {outcome['detail']}", file=sys.stderr)
        print(f"  hint: {outcome['hint']}", file=sys.stderr)
    elif limit_hit:
        print(f"error: limit exceeded: {outcome['detail']}", file=sys.stderr)
        print(f"  hint: {outcome['hint']}", file=sys.stderr)
    elif was_cancelled:
        print("cancelled: analysis stopped before it finished; nothing was kept", file=sys.stderr)
    elif failed:
        print(f"error: analysis failed at stage '{outcome['stage']}': {outcome['detail']}", file=sys.stderr)
        if outcome["hint"]:
            print(f"  hint: {outcome['hint']}", file=sys.stderr)
        if args.diagnose:
            info = outcome["diagnostics"]
            print(f"  diagnostics: {len(info['completed_stages'])} stages completed; failed after "
                  f"{info['failed_after'] or 'the start'}", file=sys.stderr)
    else:
        report = outcome["report"]
        print(f"Analysed '{report['paper']['title']}' (session {outcome['session_id']})")
        print(f"  concepts: {len(report['concepts'])}  prerequisites: {len(report['prerequisites'])}  "
              f"missing: {len(report['missing_prerequisites'])}")
        timings = outcome["timings"]
        if timings:
            slowest, seconds = max(timings.items(), key=lambda item: item[1])
            print(f"  time: {sum(timings.values()):.2f}s (slowest stage: {slowest} {seconds:.2f}s)")
        for warning in outcome["warnings"]:
            print(f"  warning: {warning}")
        if args.diagnose:
            info = outcome["diagnostics"]
            print(f"Diagnostics: {info['status']} at stage {info['stage']}; {len(info['completed_stages'])} stages, "
                  f"{info['total_seconds']:.3f}s total")
            for name, seconds in sorted(info["stage_seconds"].items(), key=lambda item: -item[1])[:5]:
                print(f"  {name}: {seconds:.3f}s")
            print("  statistics: " + ", ".join(f"{key}={value}" for key, value in info["statistics"].items()))
    if timed_out:
        return EXIT_TIMEOUT
    if limit_hit:
        return EXIT_LIMIT_EXCEEDED
    return EXIT_CANCELLED if was_cancelled else (EXIT_FAILURE if failed else EXIT_OK)
