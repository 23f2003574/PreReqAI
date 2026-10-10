"""Release acceptance: whatever prerequisite the product can put in a study plan comes with a curated
resource (so it appears in the roadmap), a justification and a study-time estimate."""
import json

import pymupdf

from backend.cli import main
from backend.prerequisites.prerequisite_detector import PrerequisiteDetector
from backend.prerequisites.prerequisite_justification_engine import PrerequisiteJustificationEngine
from backend.prerequisites.prerequisite_learning_planner import PrerequisiteLearningPlanner
from backend.resources.learning_resource_recommender import LearningResourceRecommender

EMITTED = {name for names in PrerequisiteDetector.PREREQUISITE_RULES.values() for name in names}


def test_every_emittable_prerequisite_has_a_resource_justification_and_time():
    assert {"Markov Decision Process", "Graphs"} <= EMITTED
    assert EMITTED - set(LearningResourceRecommender.RESOURCE_LIBRARY) == set()
    assert EMITTED - set(PrerequisiteJustificationEngine.JUSTIFICATIONS) == set()
    assert EMITTED - set(PrerequisiteLearningPlanner.STUDY_TIME) == set()
    assert EMITTED - set(PrerequisiteLearningPlanner.STUDY_ORDER) == set()


def test_a_paper_mixing_every_focus_area_gets_a_roadmap_step_for_each_plan_step(tmp_path, capsys):
    path = tmp_path / "paper.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_textbox(
        pymupdf.Rect(72, 72, 540, 760),
        "Abstract\nA transformer with a graph neural network, a policy gradient agent and a diffusion model.\n",
        fontsize=10)
    doc.save(path)
    assert main(["prerequisites", "analyze", str(path), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)["report"]

    plan = [s["concept"] for s in report["learning_plan"]]
    assert {"Graphs", "Markov Decision Process", "Probability", "Neural Networks"} <= set(plan)
    assert [s["concept"] for s in report["study_roadmap"]] == plan
    assert [r["step"] for r in report["study_roadmap"]] == list(range(1, len(plan) + 1))
    assert {j["concept"] for j in report["prerequisite_justifications"]} >= set(plan)
    assert all("Unknown" not in j["justification"] for j in report["prerequisite_justifications"])
