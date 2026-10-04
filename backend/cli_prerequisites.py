"""The `prerequisites` command of the PreReqAI CLI: `analyze` runs the same
workflow as POST /api/prerequisites/analyze by calling the same platform
method (PreReqAIPlatform.analyze), so the CLI and the API cannot diverge.
The platform is imported when the command runs, keeping other commands fast."""

import json
import sys

from backend.cli_common import EXIT_FAILURE, EXIT_OK


def add_prerequisites_parser(subparsers):
    prerequisites = subparsers.add_parser("prerequisites", help="Prerequisite Explorer: analyse a research paper")
    commands = prerequisites.add_subparsers(dest="prerequisites_command", required=True)
    analyze = commands.add_parser(
        "analyze",
        help="Analyse a paper PDF into concepts, prerequisites and a learning plan",
        description="Runs the paper analysis pipeline on a PDF file and opens a learning session in this process "
                    "(sessions are in memory and end with the command). Same workflow as POST /api/prerequisites/analyze.",
        epilog="Exit codes: 0 success; 1 analysis failed; 2 usage error.",
    )
    analyze.add_argument("paper", help="Path to the paper PDF")
    analyze.add_argument("--diagnose", action="store_true", dest="diagnose",
                         help="Also report per-stage durations, completed stages, warnings and run statistics "
                              "(in the --json result as `diagnostics`)")
    analyze.add_argument("--json", action="store_true", dest="as_json",
                         help="Print the workflow result envelope (status, stage, warnings, session_id, report, timings) as JSON")


def run_prerequisites_analyze(args, platform=None) -> int:
    if platform is None:
        from backend.platform import platform
    outcome = platform.analyze(args.paper, diagnostics=args.diagnose)
    failed = outcome["status"] != "success"
    if args.as_json:
        print(json.dumps(outcome, indent=2, sort_keys=True, default=str))
    elif failed:
        print(f"error: analysis failed at stage '{outcome['stage']}': {outcome['detail']}", file=sys.stderr)
        if outcome.get("hint"):
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
        timings = outcome.get("timings") or {}
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
    return EXIT_FAILURE if failed else EXIT_OK
