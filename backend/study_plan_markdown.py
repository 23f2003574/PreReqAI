"""The study plan as a Markdown checklist; shared by `analyze --plan-file` and GET /api/session/{id}/plan."""


def _one_line(text):
    """PDF metadata can hold line breaks; one in a title would start a fake line (even a ticked checklist item)."""
    return " ".join(str(text).split())


def plan_markdown(report):
    done = {item["concept"] for item in report.get("study_progress", []) if item.get("completed")}
    links = {item["concept"]: item for item in report.get("learning_resources", [])}
    reasons = {item["concept"]: item["justification"] for item in report.get("prerequisite_justifications", [])}
    lines = [f"# Study plan: {_one_line(report['paper']['title'])}", ""]
    steps = report["learning_plan"]
    if steps:
        left = sum(step["estimated_hours"] for step in steps if step["concept"] not in done)
        ticked = sum(step["concept"] in done for step in steps)
        lines += [f"{ticked} of {len(steps)} studied, about {left}h left.", ""]
    for step in steps:
        concept = step["concept"]
        line = f"- [{'x' if concept in done else ' '}] {step['step']}. {_one_line(concept)} (~{step['estimated_hours']}h)"
        if concept in links:
            line += f" - [{_one_line(links[concept]['title'])}]({links[concept]['url']})"
        lines.append(line)
        if reasons.get(concept):  # why this paper needs it, so the checklist is not just a list of course names
            lines.append(f"  - Why: {_one_line(reasons[concept])}")
    if not report["learning_plan"]:
        lines.append("Nothing left to study: no planned prerequisites.")
    return "\n".join(lines) + "\n"
