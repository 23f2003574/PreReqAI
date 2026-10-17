"""Runnable study journey on the sample paper, offline, no server or API keys.

From the repository root:  python examples/prerequisites/study_journey.py

It drives the same HTTP endpoints a client would (in process): analyse the paper, read the
prerequisite tree, mark a concept studied, and watch readiness, the next resources and the plan checklist follow.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402

SAMPLE = ROOT / "examples/prerequisites/sample-paper.pdf"


def show_tree(nodes, depth=1):
    for node in nodes:
        marks = [name for name in ("studied", "satisfied") if node.get(name)]
        print("  " * depth + node["concept"] + (f"  [{', '.join(marks)}]" if marks else ""))
        show_tree(node["prerequisites"], depth + 1)


def main() -> int:
    client = TestClient(app)

    # 1. Analyse the paper, telling PreReqAI you already know Calculus.
    reply = client.post("/api/prerequisites/analyze", data={"known": "Calculus"},
                        files={"paper": (SAMPLE.name, SAMPLE.read_bytes(), "application/pdf")}).json()
    assert reply["status"] == "success", reply
    sid, report = reply["session_id"], reply["report"]
    print("Study plan:", " -> ".join(f"{s['concept']} ({s['estimated_hours']}h)" for s in report["learning_plan"]))
    print("Prerequisite tree for Transformer:")
    show_tree([n for n in report["prerequisite_tree"] if n["concept"] == "Transformer"])

    # 2. Finish the first planned concept; progress, readiness and the tree follow.
    first = report["learning_plan"][0]["concept"]
    progress = client.post(f"/api/prerequisites/sessions/{sid}/studied", params={"concept": first}).json()
    print(f"\nStudied {first}: {progress['readiness']['completed_concepts']}/{progress['readiness']['total_concepts']} concepts ready")

    session = client.get(f"/api/session/{sid}").json()
    print("Next to study:", ", ".join(item["concept"] for item in session["next_resources"]))

    # 3. Keep the plan as a Markdown checklist.
    plan = client.get(f"/api/session/{sid}/plan").text
    print("\nChecklist:\n" + plan)
    return 0


if __name__ == "__main__":
    sys.exit(main())
