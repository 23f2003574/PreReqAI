"""python -m backend.prereqai_eval [--fixtures FILE] [--json]"""
import argparse
import json
import sys

from .harness import DEFAULT_FIXTURES, AnnotationError, evaluate, render


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m backend.prereqai_eval", description="Score concept and prerequisite detection on labelled fixtures.")
    parser.add_argument("--fixtures", default=str(DEFAULT_FIXTURES), help="annotation file (default: the bundled fixtures)")
    parser.add_argument("--json", action="store_true", help="print the full report as JSON")
    args = parser.parse_args(argv)
    try:
        report = evaluate(args.fixtures)
    except AnnotationError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2) if args.json else render(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
