"""The `prerequisites` command of the PreReqAI CLI: `analyze` runs the same
workflow as POST /api/prerequisites/analyze by calling the same platform
method (PreReqAIPlatform.analyze), so the CLI and the API cannot diverge.
The platform is imported when the command runs, keeping other commands fast."""

import argparse
import json
import math
import os
import signal
import sys
import threading
from pathlib import Path

from backend.study_plan_markdown import PLAN_HEADING, known_from_plan, plan_markdown, studied_from_plan
from backend.cli_common import EXIT_CANCELLED, EXIT_FAILURE, EXIT_LIMIT_EXCEEDED, EXIT_OK, EXIT_TIMEOUT, EXIT_USAGE


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
        description="Runs the paper analysis pipeline on a PDF file (or an arXiv link, arXiv:ID or DOI, which is downloaded first) and opens a learning session in this process "
                    "(sessions are in memory and end with the command). Same workflow as POST /api/prerequisites/analyze.",
        epilog="Example: python -m backend.cli prerequisites analyze paper.pdf --json. "
               "Exit codes: 0 success; 1 analysis failed; 2 usage error; 123 a resource limit was reached; 124 an operation timed out; 130 cancelled (Ctrl-C).",
    )
    analyze.add_argument("paper", help="Path to the paper PDF, or an arXiv link / arXiv:ID, or a DOI (downloaded for you)")
    analyze.add_argument("--tree", action="store_true",
                         help="Also print the prerequisite tree: each paper concept expanded into what it needs "
                              "(known/covered and studied concepts are marked)")
    analyze.add_argument("--diagnose", action="store_true", dest="diagnose",
                         help="Also report per-stage durations, completed stages, warnings and run statistics "
                              "(in the --json result as `diagnostics`)")
    analyze.add_argument("--known", action="append", default=[], metavar="CONCEPT",
                         help="A concept you already know; it is left out of the study plan (repeat for several)")
    analyze.add_argument("--studied", action="append", default=[], metavar="CONCEPT",
                         help="A planned concept you have finished studying; it counts toward readiness "
                              "(repeat for several; re-run with more as you progress)")
    analyze.add_argument("--resume", default=None, metavar="PLAN_FILE",
                         help="Mark as studied every concept ticked in a plan saved earlier with --plan-file, "
                              "so progress carries over between runs (add --studied for newly finished concepts)")
    analyze.add_argument("--resources", action="store_true",
                         help="Also list a curated course or article (with link) for each concept still to study")
    analyze.add_argument("--plan-file", default=None, metavar="PATH", dest="plan_file",
                         help="Also save the study plan as a Markdown checklist (studied concepts ticked, with study links) to PATH")
    add_limit_arguments(analyze)
    analyze.add_argument("--json", action="store_true", dest="as_json",
                         help="Print the workflow result envelope (status, stage, warnings, session_id, report, timings) as JSON")
    add_prerequisites_ask_parser(commands)


def _print_tree(nodes, depth):
    """The prerequisite tree as indented lines, marking concepts already known/covered or studied."""
    for node in nodes:
        marks = [mark for mark, on in (("studied", node.get("studied")), ("known or covered", node.get("satisfied"))) if on]
        print("  " * depth + "- " + node["concept"] + (f" ({', '.join(marks)})" if marks else ""))
        _print_tree(node["prerequisites"], depth + 1)


def add_limit_arguments(parser):
    parser.add_argument("--max-seconds", type=_finite_number, default=None, dest="max_seconds",
                        help="Stop the analysis once it has run this long (checked between stages; default: no limit)")
    parser.add_argument("--max-file-mb", type=_finite_number, default=None, dest="max_file_mb",
                        help="Refuse a paper file larger than this many megabytes (default: no limit)")


def _limits_from(args):
    """The AnalysisLimits the --max-seconds / --max-file-mb options ask for; None when neither is given."""
    if args.max_seconds is None and args.max_file_mb is None:
        return None
    from backend.platform import AnalysisLimits

    return AnalysisLimits(
        max_seconds=args.max_seconds,
        max_file_bytes=None if args.max_file_mb is None else _megabytes_to_bytes(args.max_file_mb),
    )


def add_prerequisites_ask_parser(commands):
    ask = commands.add_parser(
        "ask",
        help="Analyse a paper PDF and answer a question about it",
        description="Analyses the paper (as `analyze` does) and answers one question from the analysis in the same process. "
                    "Same workflow as POST /api/prerequisites/analyze followed by POST /api/session/{id}/question.",
        epilog="Example: python -m backend.cli prerequisites ask paper.pdf \"Why do I need calculus?\". "
               "No tutoring model is configured in this release: answers are built-in definitions, prerequisite reasons and study-plan figures. "
               "Exit codes: 0 success; 1 analysis or answer failed; 2 usage error.",
    )
    ask.add_argument("paper", help="Path to the paper PDF, or an arXiv link / arXiv:ID, or a DOI (downloaded for you)")
    ask.add_argument("question", help="The question to ask about the paper")
    ask.add_argument("--known", action="append", default=[], metavar="CONCEPT",
                     help="A concept you already know; it is left out of the study plan (repeat for several)")
    ask.add_argument("--studied", action="append", default=[], metavar="CONCEPT",
                     help="A planned concept you have finished studying (repeat for several)")
    ask.add_argument("--resume", default=None, metavar="PLAN_FILE",
                     help="Mark as studied every concept ticked in a plan saved with `analyze --plan-file`")
    add_limit_arguments(ask)
    ask.add_argument("--json", action="store_true", dest="as_json",
                     help="Print session_id, warnings and the answers as JSON")


def _megabytes_to_bytes(megabytes):
    """A positive limit never rounds down to 0 bytes; 0 or below stays invalid."""
    size = int(megabytes * 1024 * 1024)
    return max(1, size) if megabytes > 0 else size


def _plan_file_problem(path):
    """Why `path` cannot be written, found before the analysis runs; None when it looks writable."""
    target = Path(path)
    if target.is_dir():
        return "it is a directory"
    if not target.resolve().parent.is_dir():
        return f"the folder {target.resolve().parent} does not exist"
    if target.is_file() and target.stat().st_size:  # a mistyped path must not destroy the paper (or any other file)
        try:
            with open(target, "rb") as handle:
                head = handle.read(len(PLAN_HEADING) + 3).removeprefix(b"\xef\xbb\xbf")[:len(PLAN_HEADING)]  # an editor may add a BOM
        except OSError:
            return None  # unreadable: saving reports the real error
        if head != PLAN_HEADING.encode():
            return "it is an existing file that is not a saved study plan, and it would be overwritten"
    return None


def _save_plan(path, text):
    """Write the plan beside its target and swap it in, so a failure while saving never truncates the plan on disk:
    `--resume plan.md --plan-file plan.md` reads the same file whose ticked concepts are the learner's saved progress."""
    target = Path(path)
    temp = target.with_name(f".{target.name}.tmp")
    try:
        temp.write_text(text, encoding="utf-8")
        os.replace(temp, target)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise


def _apply_resume(args):
    """Add the concepts ticked in the --resume plan file to args.studied; False (after printing why) when it cannot be read."""
    if not getattr(args, "resume", None):
        return True
    try:
        with open(args.resume, encoding="utf-8-sig") as handle:  # Notepad and others save a plan with a BOM
            text = handle.read()
        if not text.lstrip().startswith(PLAN_HEADING):  # any other file would silently restore no progress at all
            print(f"error: {args.resume} is not a study plan saved with --plan-file (it does not start with '# Study plan:')", file=sys.stderr)
            print("  hint: pass a file written earlier with --plan-file; nothing was analysed", file=sys.stderr)
            return False
        args.studied = list(args.studied) + studied_from_plan(text)
        args.known = list(args.known) + known_from_plan(text)
    except (OSError, UnicodeDecodeError) as exc:
        print(f"error: cannot read the saved plan {args.resume}: {getattr(exc, 'strerror', None) or exc}", file=sys.stderr)
        print("  hint: pass a file written earlier with --plan-file; nothing was analysed", file=sys.stderr)
        return False
    return True


def run_prerequisites_analyze(args, platform=None) -> int:
    if args.plan_file and (problem := _plan_file_problem(args.plan_file)):
        print(f"error: cannot save the study plan to {args.plan_file}: {problem}", file=sys.stderr)
        print("  hint: choose a file path in an existing folder (for example --plan-file plan.md); nothing was analysed", file=sys.stderr)
        return EXIT_USAGE
    if not _apply_resume(args):
        return EXIT_USAGE
    if platform is None:
        try:
            from backend.platform import platform
        except ModuleNotFoundError as exc:  # a dependency from requirements.txt is not installed
            print(f"error: required package '{exc.name}' is not installed", file=sys.stderr)
            print("  hint: run `pip install -r requirements.txt` in this environment", file=sys.stderr)
            return EXIT_FAILURE
    limits = _limits_from(args)
    cancelled = threading.Event()
    try:  # Ctrl-C asks the analysis to stop before its next stage; a second Ctrl-C interrupts immediately
        previous = signal.signal(signal.SIGINT, lambda *_: (cancelled.set(), signal.signal(signal.SIGINT, signal.default_int_handler)))
    except ValueError:  # not the main thread: no handler, cancellation is only available to library callers
        previous = None
    try:
        outcome = platform.analyze(args.paper, diagnostics=args.diagnose, should_cancel=cancelled.is_set, limits=limits,
                                    **({'known': args.known} if args.known else {}),
                                    **({'studied': args.studied} if args.studied else {}))
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
        done = {item["concept"] for item in report.get("study_progress", []) if item.get("completed")}
        if report["learning_plan"]:  # one line: what to study, in order (the summary stays at most 5 lines)
            print("  study plan: " + " -> ".join(
                f"{step['step']}. {step['concept']} ({step['estimated_hours']}h" + (", studied)" if step["concept"] in done else ")")
                for step in report["learning_plan"]))
        elif missing:
            print("  study first: " + ", ".join(missing))
        readiness, study_time = report.get("readiness"), report.get("study_time")  # readiness, difficulty, preparation time
        if readiness and study_time:
                ready = (f"{readiness['completed_concepts']}/{readiness['total_concepts']} concepts ready"
                         if readiness["total_concepts"] else "no concepts left to study")
                print(f"  readiness: {readiness['status']} ({ready}); "
                  f"difficulty: {report['paper_difficulty']['level']}; "
                  f"preparation: ~{study_time['total_hours']}h over {study_time['recommended_days']} days"
                  + (f" ({left}h left)" if done and (left := sum(step["estimated_hours"] for step in report["learning_plan"]
                                                               if step["concept"] not in done)) != study_time["total_hours"] else ""))
        if args.resources:
            order = {step["concept"]: step["step"] for step in report["learning_plan"]}  # list them in study order
            pending = sorted((item for item in report.get("learning_resources", []) if item["concept"] not in done),
                             key=lambda item: order.get(item["concept"], len(order) + 1))
            if pending:
                print("  resources:")
                for item in pending:
                    print(f"    {item['concept']}: {item['title']} ({item['provider']}, ~{item['estimated_hours']}h) {item['url']}")
            elif report.get("learning_resources"):
                print("  resources: none left to study")
            else:
                print("  resources: none available for this paper's concepts")
        if args.tree:
            tree = report.get("prerequisite_tree") or []
            print("  prerequisite tree:" if tree else "  prerequisite tree: no concept of this paper has prerequisites")
            _print_tree(tree, 2)
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
    if args.plan_file and not failed:  # also with --json, where stdout stays the JSON envelope only
        try:
            _save_plan(args.plan_file, plan_markdown(outcome["report"]))
            if not args.as_json:
                print(f"  plan saved: {args.plan_file}")
        except OSError as exc:
            print(f"error: could not save the study plan to {args.plan_file}: {exc.strerror or exc}", file=sys.stderr)
            print("  hint: the analysis succeeded; fix the path or permissions and re-run with the same options", file=sys.stderr)
            return EXIT_FAILURE
    if timed_out:
        return EXIT_TIMEOUT
    if limit_hit:
        return EXIT_LIMIT_EXCEEDED
    return EXIT_CANCELLED if was_cancelled else (EXIT_FAILURE if failed else EXIT_OK)


def run_prerequisites_ask(args, platform=None) -> int:
    """Analyse the paper, then answer the question from that session; the same two calls the HTTP API makes."""
    import dataclasses

    if not args.question.strip():
        print("error: the question must not be empty", file=sys.stderr)
        return EXIT_USAGE
    from backend.api.session_routes import MAX_QUESTION_CHARS

    if len(args.question) > MAX_QUESTION_CHARS:
        print(f"error: the question is too long ({len(args.question)} characters; the limit is {MAX_QUESTION_CHARS})", file=sys.stderr)
        return EXIT_USAGE
    if not _apply_resume(args):
        return EXIT_USAGE
    if platform is None:
        try:
            from backend.platform import platform
        except ModuleNotFoundError as exc:
            print(f"error: required package '{exc.name}' is not installed", file=sys.stderr)
            print("  hint: run `pip install -r requirements.txt` in this environment", file=sys.stderr)
            return EXIT_FAILURE
    outcome = platform.analyze(args.paper, limits=_limits_from(args), known=args.known, studied=args.studied)
    if outcome["status"] in ("limit_exceeded", "timeout"):  # same wording and exit codes as `analyze`
        print(f"error: {'limit exceeded' if outcome['status'] == 'limit_exceeded' else 'timed out'}: {outcome['detail']}", file=sys.stderr)
        print(f"  hint: {outcome['hint']}", file=sys.stderr)
        return EXIT_LIMIT_EXCEEDED if outcome["status"] == "limit_exceeded" else EXIT_TIMEOUT
    if outcome["status"] != "success":
        print(f"error: analysis failed at stage '{outcome['stage']}': {outcome['detail']}", file=sys.stderr)
        if outcome.get("hint"):
            print(f"  hint: {outcome['hint']}", file=sys.stderr)
        return EXIT_FAILURE
    from backend.session import TutorMode, session_manager

    session = session_manager.get(outcome["session_id"])
    try:
        result = platform.learning.answer(session=session, paper=session.paper, question=args.question,
                                          mode=TutorMode.INTUITION, topic=None)
    except Exception as exc:  # same envelope idea as the API: one readable line, never a traceback
        print(f"error: failed to answer the question: {exc}", file=sys.stderr)
        return EXIT_FAILURE
    responses = [dataclasses.asdict(r) for r in result.get("responses") or []]
    if not responses:  # exit 0 with nothing printed would look like an answer that was simply empty
        print("error: no answer was produced for the question", file=sys.stderr)
        print("  hint: rephrase the question, or name a concept from the study plan (see `analyze`)", file=sys.stderr)
        return EXIT_FAILURE
    placeholder = any("tutoring model has not yet been configured" in r["answer"] for r in responses)
    warning = ("No tutoring model is configured in this release: the answer is a placeholder."
               if placeholder else
               "No tutoring model is configured in this release: answers are built-in definitions, prerequisite reasons and study-plan figures, not generated explanations.")
    warnings = [*(outcome.get("warnings") or []), warning]  # e.g. a --known name that is not in the plan
    if args.as_json:
        print(json.dumps({"status": "success", "session_id": outcome["session_id"], "question": args.question,
                          "responses": responses, "warnings": warnings}, indent=2))
        return EXIT_OK
    for response in responses:
        print(response["answer"])
    if responses and responses[0]["supporting_concepts"]:
        print("  concepts: " + ", ".join(responses[0]["supporting_concepts"]))
    for line in warnings:
        print(f"  warning: {line}")
    return EXIT_OK
