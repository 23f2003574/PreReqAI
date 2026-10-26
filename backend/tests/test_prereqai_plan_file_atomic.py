"""A failure while saving --plan-file must not wipe the plan (and the studied progress in it) already on disk."""
import pytest

from backend import cli_prerequisites


def test_failed_write_keeps_the_existing_plan(tmp_path, monkeypatch):
    plan = tmp_path / "plan.md"
    plan.write_text("- [x] Probability\n", encoding="utf-8")

    def boom(self, text, encoding=None):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(cli_prerequisites.Path, "write_text", boom)
    with pytest.raises(OSError):
        cli_prerequisites._save_plan(plan, "new plan")

    assert plan.read_text(encoding="utf-8") == "- [x] Probability\n"
    assert [p.name for p in tmp_path.iterdir()] == ["plan.md"]


def test_successful_save_replaces_the_plan_and_leaves_no_temp_file(tmp_path):
    plan = tmp_path / "plan.md"
    plan.write_text("old", encoding="utf-8")
    cli_prerequisites._save_plan(str(plan), "new")
    assert plan.read_text(encoding="utf-8") == "new"
    assert [p.name for p in tmp_path.iterdir()] == ["plan.md"]

