"""The `prerequisites` command of the PreReqAI CLI: `analyze` runs the same
workflow as POST /api/prerequisites/analyze by calling the same platform
method (PreReqAIPlatform.analyze), so the CLI and the API cannot diverge.
The platform is imported when the command runs, keeping other commands fast."""

import argparse
import json
import math
import signal
import sys
import threading

from backend.cli_common import EXIT_CANCELLED, EXIT_FAILURE, EXIT_LIMIT_EXCEEDED, EXIT_OK, EXIT_TIMEOUT


def _finite_number(value):
    """argparse type for the limit flags: a finite number. NaN/infinity are a usage
    error naming the flag (never a traceback); a value of 0 or below still reaches
    the analysis as an invalid limit and is reported at its configuration stage."""
    try:
        number = float(value)
    except ValueError:
        number = math.nan
    if not math.isfinite(number):
        raise argparse.ArgumentTypeError(f"{value!r} is not a finite number (omit the flag for no limit)")
    return number


def add_prerequisites_parser(subparsers):
    prerequisites = subparsers.add_parser("prerequisites", help="Prerequisite Explorer: analyse a research paper PDF (start here)")
    commands = prerequisites.add_subparsers(dest="prerequisites_command", required=True, metavar="<subcommand>")
    analyze = commands.add_parser(
        "analyze",
        help="Analyse a paper PDF into concepts, prerequisites and a learning plan",
        description="Runs the paper analysis pipeline on a PDF file and opens a learning session in this process "
                    "(sessions are in memory and end with the command). Same workflow as POST /api/prerequisites/analyze.",
        epilog="Example: python -m backend.cli prerequisites analyze paper.pdf --json. "
               "Exit codes: 0 success; 1 analysis failed; 2 usage error; 123 a resource limit was reached; 124 an operation timed out; 130 cancelled (Ctrl-C).",
    )
    analyze.add_argument("paper", help="Path to the paper PDF")
    analyze.add_argument("--diagnose", action="store_true", dest="diagnose",
                         help="Also report per-stage durations, completed stages, warnings and run statistics "
                              "(in the --json result as `diagnostics`)")
    analyze.add_argument("--max-seconds", type=_finite_number, default=None, dest="max_seconds",
                         help="Stop the analysis once it has run this long (checked between stages; default: no limit)")
    analyze.add_argument("--max-file-mb", type=_finite_number, default=None, dest="max_file_mb",
                         help="Refuse a paper file larger than this many megabytes (default: no limit)")
    analyze.add_argument("--json", action="store_true", dest="as_json",
                         help="Print the workflow result envelope (status, stage, warnings, session_id, report, timings) as JSON")


def _megabytes_to_bytes(megabytes):
    """A positive limit never rounds down to 0 bytes; 0 or below stays invalid."""
    size = int(megabytes * 1024 * 1024)
    return max(1, size) if megabytes > 0 else size


def run_prerequisites_analyze(args, platform=None) -> int:
    if platform is None:
        try:
            from backend.platform import platform
        except ModuleNotFoundError as exc:  # a dependency from requirements.txt is not installed
            print(f"error: required package '{exc.name}' is not installed", file=sys.stderr)
            print("  hint: run `pip install -r requirements.txt` in this environment", file=sys.stderr)
            return EXIT_FAILURE
    limits = None
    if args.max_seconds is not None or args.max_file_mb is not None:
        from backend.platform import AnalysisLimits

        limits = AnalysisLimits(
            max_seconds=args.max_seconds,
            max_file_bytes=None if args.max_file_mb is None else _megabytes_to_bytes(args.max_file_mb),
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
    if not args.as_json and args.diagnose and (timed_out or limit_hit or was_cancelled):
        info = outcome["diagnostics"]
        print(f"  diagnostics: {len(info['completed_stages'])} stages completed; stopped after "
              f"{info['stopped_after'] or 'the start'}", file=sys.stderr)
    if not args.as_json and not failed:
        report = outcome["report"]
        print(f"Analysed '{report['paper']['title']}' (session {outcome['session_id']})")
        # missing_prerequisites lists every prerequisite checked; only unsatisfied ones are missing
        missing = [item["concept"] for item in report["missing_prerequisites"] if not item.get("satisfied")]
        covered = len(report["missing_prerequisites"]) - len(missing)
        print(f"  concepts: {len(report['concepts'])}  prerequisites: {len(report['prerequisites'])}  "
              f"missing: {len(missing)}" + (f" ({covered} covered in the paper)" if covered else ""))
        if report["learning_plan"]:  # one line: what to study, in order (the summary stays at most 5 lines)
            print("  study plan: " + " -> ".join(
                f"{step['step']}. {step['concept']} ({step['estimated_hours']}h)" for step in report["learning_plan"]))
        elif missing:
            print("  study first: " + ", ".join(missing))
        readiness, study_time = report.get("readiness"), report.get("study_time")  # readiness, difficulty, preparation time
        if readiness and study_time:
                print(f"  readiness: {readiness['status']} ({readiness['completed_concepts']}/{readiness['total_concepts']} concepts ready); "
                  f"difficulty: {report['paper_difficulty']['level']}; "
                  f"preparation: ~{study_time['total_hours']}h over {study_time['recommended_days']} days")
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
            # the slowest stages that took measurable time; 0.000s entries are noise (--json keeps every stage)
            slowest = sorted(info["stage_seconds"].items(), key=lambda item: -item[1])
            shown = [(name, seconds) for name, seconds in slowest[:5] if round(seconds, 3) > 0]
            for name, seconds in shown:
                print(f"  {name}: {seconds:.3f}s")
            if len(slowest) > len(shown):
                print(f"  ({len(slowest) - len(shown)} faster stages not shown; --json has every stage's timing)")
            print("  statistics: " + ", ".join(f"{key}={value}" for key, value in info["statistics"].items()))
    if timed_out:
        return EXIT_TIMEOUT
    if limit_hit:
        return EXIT_LIMIT_EXCEEDED
    return EXIT_CANCELLED if was_cancelled else (EXIT_FAILURE if failed else EXIT_OK)
