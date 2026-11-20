"""python -m backend.prereqai_eval [--pdf | --benchmark [--manifest FILE] | --approve FILE --reviewer NAME | --fixtures FILE] [--json]"""
import argparse
import json
import sys

from .harness import DEFAULT_FIXTURES, AnnotationError, evaluate, render


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m backend.prereqai_eval", description="Score concept and prerequisite detection on labelled fixtures.")
    parser.add_argument("--fixtures", default=str(DEFAULT_FIXTURES), help="annotation file (default: the bundled fixtures)")
    parser.add_argument("--pdf", action="store_true", help="evaluate generated synthetic academic PDFs through the full pipeline (needs PyMuPDF)")
    parser.add_argument("--benchmark", action="store_true", help="evaluate the real-paper benchmark (reviewed annotations only; needs PyMuPDF; reported apart from --pdf)")
    parser.add_argument("--performance", action="store_true", help="time the pipeline stage by stage on a generated PDF (see --pages); machine-dependent, for comparing changes")
    parser.add_argument("--pages", type=int, default=120, help="pages of the --performance PDF (at least 100; default 120)")
    parser.add_argument("--manifest", default=None, help="benchmark manifest (default: the bundled one)")
    parser.add_argument("--approve", metavar="ANNOTATION", default=None, help="record a person's approval of a benchmark annotation (needs --reviewer)")
    parser.add_argument("--reviewer", default=None, help="the name of the person approving the annotation")
    parser.add_argument("--status", action="store_true", help="list, for every benchmark paper, everything still missing before it can be scored")
    parser.add_argument("--register", metavar="PDF", default=None, help="add a PDF you have the right to redistribute to the benchmark (needs --id, --licence, --licence-evidence, --licence-checked-by)")
    parser.add_argument("--id", default=None, help="the paper's benchmark id (with --register)")
    parser.add_argument("--licence", default=None, help="the SPDX licence of the paper, such as CC-BY-4.0 (with --register)")
    parser.add_argument("--licence-evidence", default=None, help="the link where the licence is stated (with --register)")
    parser.add_argument("--licence-checked-by", default=None, help="the name of the person who read that licence (with --register)")
    for flag in ("title", "source-url", "venue", "year"):
        parser.add_argument(f"--{flag}", default=None, help=f"the paper's {flag.replace('-', ' ')}, for an id the manifest does not list yet (with --register)")
    parser.add_argument("--author", action="append", default=[], help="an author, repeatable (with --register, for a new id)")
    parser.add_argument("--json", action="store_true", help="print the full report as JSON")
    args = parser.parse_args(argv)
    if args.performance:
        from . import performance

        if args.pages < 100:
            print("error: --pages must be at least 100", file=sys.stderr)
            return 2
        report = performance.run_benchmark(args.pages)
        print(json.dumps(report, indent=2) if args.json else performance.render_performance(report))
        return 0
    if args.status or args.register:
        from . import benchmark

        manifest = args.manifest or benchmark.DEFAULT_MANIFEST
        try:
            if args.register:
                entry = benchmark.register_paper(manifest, args.register, args.id, args.licence, args.licence_evidence, args.licence_checked_by,
                                                 {"title": args.title, "authors": args.author, "source_url": args.source_url, "venue": args.venue, "year": args.year})
                print(f"{entry['id']}: PDF and licence recorded (sha256 {entry['pdf']['sha256'][:12]}...). Its annotation is pending_review: annotate it from the paper, then a person runs --approve.")
                return 0
            rows = benchmark.status(manifest)
        except benchmark.BenchmarkError as error:
            print("error: " + "\n       ".join(error.problems), file=sys.stderr)
            return 2
        print(json.dumps(rows, indent=2) if args.json else benchmark.render_status(rows))
        return 0
    if args.approve or args.benchmark:
        from . import benchmark

        try:
            if args.approve:
                benchmark.approve(args.approve, args.reviewer)
                print(f"{args.approve}: approved by {args.reviewer.strip()}")
                return 0
            report = benchmark.evaluate_benchmark(args.manifest or benchmark.DEFAULT_MANIFEST)
        except benchmark.BenchmarkError as error:
            print("error: " + "\n       ".join(error.problems), file=sys.stderr)
            return 2
        except benchmark.check_dependencies.__globals__["PdfDependencyError"] as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        print(json.dumps(report, indent=2) if args.json else benchmark.render_benchmark(report))
        return 0
    if args.pdf:
        from .pdf_eval import PdfDependencyError, evaluate_pdf, render_pdf

        if args.fixtures != str(DEFAULT_FIXTURES):
            print("error: --pdf evaluates the bundled PDF fixtures; it cannot be combined with --fixtures", file=sys.stderr)
            return 2
        try:
            report = evaluate_pdf()
        except PdfDependencyError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        print(json.dumps(report, indent=2) if args.json else render_pdf(report))
        return 0
    try:
        report = evaluate(args.fixtures)
    except AnnotationError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2) if args.json else render(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
