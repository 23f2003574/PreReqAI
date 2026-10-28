"""The study plan as a Markdown checklist; shared by `analyze --plan-file` and GET /api/session/{id}/plan."""

import re


PLAN_HEADING = "# Study plan:"  # how every saved plan starts; --plan-file only overwrites files that start with it


def _one_line(text):
    """PDF metadata can hold line breaks; one in a title would start a fake line (even a ticked checklist item)."""
    return " ".join(str(text).split())


def studied_concepts(report):
    """The concepts a report's study_progress marks as studied; the one definition the plan, the CLI summary and the API share."""
    return {item["concept"] for item in report.get("study_progress", []) if item.get("completed")}


def plan_markdown(report):
    done = studied_concepts(report)
    links = {item["concept"]: item for item in report.get("learning_resources", [])}
    reasons = {item["concept"]: item["justification"] for item in report.get("prerequisite_justifications", [])}
    lines = [f"{PLAN_HEADING} {_one_line(report['paper']['title'])}", ""]
    steps = report["learning_plan"]
    if steps:
        left = sum(step["estimated_hours"] for step in steps if step["concept"] not in done)
        ticked = sum(step["concept"] in done for step in steps)
        lines += [f"{ticked} of {len(steps)} studied, about {left}h left.", ""]
    from backend.platform.prereqai_platform import KNOWN_REASON

    known = [item["concept"] for item in report.get("missing_prerequisites", []) if item.get("reason") == KNOWN_REASON]
    if known:  # kept in the file so `--resume` does not put concepts the learner already knows back into the plan
        lines += [f"Already known: {'; '.join(_one_line(name) for name in known)}", ""]
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


_TICKED = re.compile(r"^- \[[xX]\] \d+\. (.+?) \(~\d+h\)", re.MULTILINE)


def is_saved_plan(text):
    """Whether `text` is a plan written by plan_markdown (a leading BOM or blank lines from an editor are ignored). The one
    check behind every resume surface: any other file would restore no progress at all, silently."""
    return text.lstrip("\ufeff \t\r\n").startswith(PLAN_HEADING)


def studied_from_plan(text):
    """The concepts ticked in a checklist written by plan_markdown, so a saved plan can restore progress."""
    return [match.group(1) for match in _TICKED.finditer(text)]


_KNOWN = re.compile(r"^Already known: (.+)$", re.MULTILINE)


def known_from_plan(text):
    """The concepts a plan written by plan_markdown records as already known to the learner."""
    match = _KNOWN.search(text)
    return [name.strip() for name in match.group(1).split(";") if name.strip()] if match else []


def resume_mismatch_warning(plan_text, paper_title):
    """A warning when a resumed plan was saved for another paper than the one analysed now (its studied and known concepts
    still apply, but a wrong file should not go unnoticed); None when the titles match."""
    first = plan_text.lstrip("\ufeff \t\r\n").splitlines()[0] if is_saved_plan(plan_text) else ""
    saved = _one_line(first[len(PLAN_HEADING):]) if first else ""
    if saved and saved.casefold() != _one_line(paper_title).casefold():
        return f"The resumed plan was saved for '{saved}', not '{_one_line(paper_title)}'; its studied and known concepts were applied anyway."
    return None
