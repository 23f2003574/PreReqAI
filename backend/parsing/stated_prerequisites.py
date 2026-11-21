"""Prerequisites a paper states itself ("we assume familiarity with linear algebra", "recall that ... softmax").

PreReqAI's prerequisite table is its own association; this finds where the paper says what it needs. A sentence counts when it has a cue and names a known subject or concept:
* explicit cues (assume / presuppose / require knowledge of, familiar with, familiarity, background in, prior knowledge of, expected to know, readers should know) strengthen evidence;
* reminder cues ("recall that", "as a reminder", "it is well known that") only record that the paper leans on the subject; they never raise a grade.
A cue whose sentence names nothing the system knows is kept as an unmatched cue for display and creates no prerequisite. Each finding carries the complete sentence, its page and section.
Subjects come from the prerequisite subject vocabulary (`rule_based_concept_detector`), concepts from the registry; only subjects the prerequisite table itself uses can be added as new prerequisites."""
import re

EXPLICIT = re.compile(r"\b(?:we|authors?)\s+(?:will\s+)?(?:assume|presuppose|require|expect)s?\b|\bassum(?:es|ing)\s+(?:the\s+reader|readers|familiarity|knowledge|that\s+the\s+reader)\b"
                      r"|\b(?:reader|readers)\s+(?:is|are)\s+(?:expected|assumed)\s+to\b|\b(?:reader|readers)\s+(?:should|must|needs?\s+to)\s+(?:be\s+familiar|know|understand|have)\b"
                      r"|\bfamiliar(?:ity)?\s+with\b|\bfamiliarity\s+with\b|\bbackground\s+in\b|\bprior\s+(?:knowledge|exposure)\s+(?:of|to|in)\b|\bpreliminary\s+knowledge\s+of\b"
                      r"|\bbasic\s+(?:knowledge|understanding)\s+of\b|\brequires?\s+(?:an?\s+)?(?:understanding|knowledge)\s+of\b|\bpresuppos\w*\s+(?:knowledge|familiarity|a\s+background|that\s+the\s+reader)\b", re.IGNORECASE)
REMINDER = re.compile(r"\brecall\s+that\b|\bas\s+a\s+reminder\b|\bit\s+is\s+well[- ]known\s+that\b|\bwe\s+recall\b|\brecall\s+the\b", re.IGNORECASE)
MIN_CHARS, MAX_CHARS = 25, 450
_SENTENCES = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\[“\"])")
_BACK_MATTER = re.compile(r"^\s*(?:\d+\.?\s*)?(?:references|bibliography|acknowledg|appendix)", re.IGNORECASE)


def _concept_patterns():
    from backend.concepts.concept_registry import ConceptRegistry

    found = {}
    for concept in ConceptRegistry().all():
        terms = sorted({concept.name.lower(), *(a.lower() for a in concept.aliases if not getattr(concept, "ambiguous", False) or len(a) > 4)}, key=len, reverse=True)
        found[concept.name] = re.compile(r"(?<![a-z0-9])(?:" + "|".join(re.escape(t) for t in terms) + r")s?(?![a-z0-9])")
    return found


def known_subjects():
    """The subjects the prerequisite table itself uses: the only ones a stated prerequisite may add as a new prerequisite."""
    from backend.prerequisites.prerequisite_detector import PrerequisiteDetector

    return {subject for needs in PrerequisiteDetector.PREREQUISITE_RULES.values() for subject in needs}


def find_in_sentence(sentence):
    """{"cue": "explicit"|"reminder"|None, "subjects": [...], "concepts": [...]} for one sentence."""
    from backend.concepts.rule_based_concept_detector import _SUBJECT_PATTERNS, normalise_text

    text = normalise_text(sentence)
    cue = "explicit" if EXPLICIT.search(sentence) else "reminder" if REMINDER.search(sentence) else None
    if cue is None:
        return {"cue": None, "subjects": [], "concepts": []}
    subjects = [s for s, pattern in _SUBJECT_PATTERNS.items() if pattern.search(text)]
    concepts = [name for name, pattern in _concept_patterns().items() if pattern.search(text)]
    named = [*subjects, *concepts]  # "Attention" inside "Self-Attention" is the longer term's mention, not a second prerequisite
    subjects = [n for n in subjects if not any(n != m and n.lower() in m.lower() for m in named)]
    concepts = [n for n in concepts if not any(n != m and n.lower() in m.lower() for m in named)]
    return {"cue": cue, "subjects": subjects, "concepts": concepts}


def extract(paper):
    """({findings}, [unmatched cue sentences]) from the paper's body paragraphs. A finding: {subject, kind: "subject"|"concept", cue, sentence, page_number, section, passage_id}."""
    findings, unmatched, seen = [], [], set()
    for paragraph in getattr(paper, "paragraphs", []):
        if _BACK_MATTER.match(paragraph.section_title or ""):
            continue
        for position, sentence in enumerate(_SENTENCES.split(" ".join((paragraph.content or "").split()))):
            if not MIN_CHARS <= len(sentence) <= MAX_CHARS:
                continue
            hit = find_in_sentence(sentence)
            if hit["cue"] is None:
                continue
            names = [(s, "subject") for s in hit["subjects"]] + [(c, "concept") for c in hit["concepts"] if c not in hit["subjects"]]
            if not names:
                unmatched.append({"sentence": sentence, "page_number": paragraph.page_number, "section": paragraph.section_title, "cue": hit["cue"]})
                continue
            for name, kind in names:
                if (name, sentence) in seen:
                    continue
                seen.add((name, sentence))
                findings.append({"subject": name, "kind": kind, "cue": hit["cue"], "sentence": sentence, "page_number": paragraph.page_number, "section": paragraph.section_title,
                                 "passage_id": f"stated-{paragraph.paragraph_id}-{position}"})
    return findings, unmatched


_UP = {"weak": "moderate", "moderate": "strong", "strong": "strong", "": "moderate"}


def apply(paper):
    """Record on each matching prerequisite that the paper states it (explicit cues raise the grade one step; reminders add provenance only), and add a paper-stated prerequisite for a
    known subject the rules did not reach. Findings that match no prerequisite and no addable subject are kept in `paper.stated_prerequisites` only. Returns the paper."""
    from backend.models import Prerequisite

    findings, unmatched = extract(paper)
    paper.stated_prerequisites, paper.unmatched_prerequisite_cues = findings, unmatched
    by_name = {p.concept: p for p in paper.prerequisites}
    addable = known_subjects()
    for finding in findings:
        target = finding["subject"]
        entry = by_name.get(target)
        quote = {"passage_id": finding["passage_id"], "sentence": finding["sentence"], "page_number": finding["page_number"], "section": finding["section"], "cue": finding["cue"]}
        if entry is None:
            if finding["cue"] != "explicit" or target not in addable:
                continue  # a reminder, or a concept/subject the prerequisite table does not use, creates no edge
            entry = Prerequisite(concept=target, reason=f"The paper states that it needs {target}", confidence=0.0, importance="supporting",
                                 importance_reason="Stated by the paper itself; no concept of the paper depends on it in PreReqAI's table.", evidence_strength="moderate",
                                 strength_reasons=[f"the paper states it (page {finding['page_number']})"], provenance="stated")
            paper.prerequisites.append(entry)
            by_name[target] = entry
        already_explicit = any(q["cue"] == "explicit" for q in entry.stated_by_paper)
        if quote not in entry.stated_by_paper:
            entry.stated_by_paper.append(quote)
        if finding["cue"] == "explicit" and not already_explicit and entry.provenance != "stated":
            raised = _UP.get(entry.evidence_strength, "moderate")
            entry.strength_reasons.append(f"the paper states it is needed (page {finding['page_number']}): one grade up" if raised != entry.evidence_strength else "the paper states it is needed")
            entry.evidence_strength = raised
            entry.provenance = "inferred+stated"
        elif entry.provenance == "inferred":
            entry.provenance = "inferred+stated"
        if entry.provenance in ("stated", "inferred+stated"):
            entry.evidence_note = ("The paper itself states this prerequisite (see its quoted sentences). " + (entry.evidence_note or "")).strip()
    return paper


def evaluate(cases):
    """{"precision", "recall", "tp", "fp", "fn", "cases"} over [{"sentence", "expected": [names]}]: expected names are the subjects/concepts a correct reader finds stated (empty
    for a sentence with no stated prerequisite). Measured on the names found by `find_in_sentence` when the cue is explicit."""
    tp = fp = fn = 0
    for case in cases:
        hit = find_in_sentence(case["sentence"])
        got = set(hit["subjects"] + hit["concepts"]) if hit["cue"] == "explicit" else set()
        want = set(case["expected"])
        tp, fp, fn = tp + len(got & want), fp + len(got - want), fn + len(want - got)
    return {"precision": tp / (tp + fp) if tp + fp else 1.0, "recall": tp / (tp + fn) if tp + fn else 1.0, "tp": tp, "fp": fp, "fn": fn, "cases": len(cases)}
