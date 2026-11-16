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
    parser.add_argument("--manifest", default=None, help="benchmark manifest (default: the bundled one)")
    parser.add_argument("--approve", metavar="ANNOTATION", default=None, help="record a person's approval of a benchmark annotation (needs --reviewer)")
    parser.add_argument("--reviewer", default=None, help="the name of the person approving the annotation")
    parser.add_argument("--json", action="store_true", help="print the full report as JSON")
    args = parser.parse_args(argv)
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
