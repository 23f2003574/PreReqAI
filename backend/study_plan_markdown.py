"""The study plan as a Markdown checklist; shared by `analyze --plan-file` and GET /api/session/{id}/plan."""


def plan_markdown(report):
    done = {item["concept"] for item in report.get("study_progress", []) if item.get("completed")}
    links = {item["concept"]: item for item in report.get("learning_resources", [])}
    lines = [f"# Study plan: {report['paper']['title']}", ""]
    for step in report["learning_plan"]:
        concept = step["concept"]
        line = f"- [{'x' if concept in done else ' '}] {step['step']}. {concept} (~{step['estimated_hours']}h)"
        if concept in links:
            line += f" - [{links[concept]['title']}]({links[concept]['url']})"
        lines.append(line)
    if not report["learning_plan"]:
        lines.append("Nothing left to study: no planned prerequisites.")
    return "\n".join(lines) + "\n"
