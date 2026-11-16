"""python -m backend.prereqai_eval [--pdf | --fixtures FILE] [--json]"""
import argparse
import json
import sys

from .harness import DEFAULT_FIXTURES, AnnotationError, evaluate, render


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m backend.prereqai_eval", description="Score concept and prerequisite detection on labelled fixtures.")
    parser.add_argument("--fixtures", default=str(DEFAULT_FIXTURES), help="annotation file (default: the bundled fixtures)")
    parser.add_argument("--pdf", action="store_true", help="evaluate generated synthetic academic PDFs through the full pipeline (needs PyMuPDF)")
    parser.add_argument("--json", action="store_true", help="print the full report as JSON")
    args = parser.parse_args(argv)
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
