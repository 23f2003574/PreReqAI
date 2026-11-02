"""The `api-generation` argument parser, kept apart from backend/cli_api_generation.py so that building the CLI's parser (every
command does) does not import the generator, the drafts and the LLM package (about 0.2s of start-up)."""

import argparse


def add_api_generation_parser(subparsers):
    api_generation = subparsers.add_parser(
        "api-generation",
        help="Generate a FastAPI project from a validated API documentation draft, and check generated projects",
        epilog="Worked example: examples/api-generation/ (walkthrough: docs/api-generation-walkthrough.md)",
    )
    api_generation_subparsers = api_generation.add_subparsers(dest="api_generation_command", required=True)
    generate = api_generation_subparsers.add_parser(
        "generate",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help="Generate, validate and write a FastAPI project from a validated API documentation draft",
        description=(
            "Turns one validated API documentation draft into a runnable FastAPI project (app package, OpenAPI\n"
            "document, requirements.txt, Dockerfile, README and project metadata). The draft is a JSON file with the\n"
            "fields of LLMAPIDocumentationDraft (draft_id, endpoint, summary, description, parameters, responses,\n"
            "examples, status); its status must be VALIDATED. Stages: configuration, preflight, input, generation,\n"
            "validation, write. The project is validated before anything is written."
        ),
        epilog=(
            "Example:\n"
            "  python -m backend.cli api-generation generate --draft examples/api-generation/draft.json \\\n"
            "      --output-dir ./loan-quote-api --dry-run      # preview; drop --dry-run to write\n"
            "\n"
            "Exit codes: 0 success; 2 usage error; 3 invalid input, configuration or output target;\n"
            "4 generation, validation or write failed; 5 unexpected internal error."
        ),
    )
    generate.add_argument("--draft", required=True, help="Path to the draft JSON file")
    generate.add_argument("--output-dir", required=True, help="Directory to write the generated project into")
    generate.add_argument("--base-image", default=None, help="Dockerfile base image (default: python:3.11-slim); overrides --config")
    generate.add_argument(
        "--dry-run", action="store_true", dest="dry_run",
        help="Run every stage and report what would be generated, without writing anything",
    )
    generate.add_argument("--port", type=int, default=None, help="Dockerfile default listen port (default: 8000); overrides --config")
    generate.add_argument(
        "--config", default=None,
        help="A prereqai-config.json (e.g. from an earlier generated project) holding base_image, port and "
             "project_name; explicit flags override its values",
    )
    generate.add_argument(
        "--project-name", default=None, dest="project_name",
        help="Project name (letters, digits, '-', '_'); the app is generated in the package it normalizes to, "
             "e.g. loan-quote -> loan_quote/main.py (default: the draft's summary, package app)",
    )
    generate.add_argument(
        "--json", action="store_true", dest="as_json",
        help="Print one JSON summary on stdout, for success and failure alike: status, source, stages_completed, "
             "validation, warnings, dry_run and either the result (draft_id, endpoint, output_dir, files, openapi_path, "
             "artifact_types) or failed_stage and error",
    )
    generate.add_argument(
        "-q", "--quiet", action="store_true", dest="quiet",
        help="Do not print stage progress lines (progress is also off with --json)",
    )


    check = api_generation_subparsers.add_parser(
        "check",
        help="Check that a generated API project on disk is healthy (read-only; nothing is launched)",
        description="Validates a generated project directory (files, metadata, manifest, importable app, OpenAPI, "
                    "dependencies, README) and reports its compatibility with this generator version.",
        epilog="Exit codes: 0 healthy; 1 invalid or incompatible; 2 usage error.",
    )
    check.add_argument("project_dir", help="The generated project directory")
    check.add_argument("--json", action="store_true", dest="as_json", help="Print the health result as JSON")
