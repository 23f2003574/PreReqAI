"""Fill-in-the-blank comprehension questions about THIS paper, made from its own verified sentences.

Each question is one of the paper's evidence passages (backend/evidence.py: a sentence that is an exact quotation of the page it cites) with the concept's term blanked out. The answer is
that term, and revealing it shows the whole sentence with its page and section, so the learner can check it in the paper. Nothing is generated: a question exists only where a quotable
sentence names a detected concept exactly once. The questions are kept apart from the global concept questions (their ids start with "paper~", never "Softmax:1"), but their outcomes
count toward the session's mastery and, with a learner profile, enter spaced review like any other answer."""
import re

MIN_CHARS, MAX_CHARS = 60, 280  # a sentence shorter or longer than this is a fragment or a paragraph, not a question
MIN_OTHER_WORDS = 8  # words that remain once the term is blanked
MAX_QUESTIONS = 12
PREFIX = "paper~"
BLANK = "_____"
_HYPHEN_RESIDUE = re.compile(r"[A-Za-z]- [a-z]")  # "mod- els": a word split at a line end, which the quotation keeps exactly but a question should not show


def question_id(passage_id):
    return f"{PREFIX}{passage_id}:1"


def _cloze(passage):
    """(prompt, answer) for a passage, or None when its sentence makes a poor question."""
    sentence, term = " ".join(passage["sentence"].split()), passage.get("matched_term") or ""
    if not MIN_CHARS <= len(sentence) <= MAX_CHARS or len(term) < 3 or sentence.lower().startswith(("figure", "table", "algorithm")):
        return None
    pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(' '.join(term.split()))}(?![A-Za-z0-9])", re.IGNORECASE)
    if not 1 <= len(pattern.findall(sentence)) <= 3 or _HYPHEN_RESIDUE.search(sentence):  # every copy of the term is blanked, or the answer would stay in the question
        return None
    prompt = pattern.sub(BLANK, sentence)
    if len(prompt.replace(BLANK, "").split()) < MIN_OTHER_WORDS or sum(c.isdigit() for c in sentence) > 0.15 * len(sentence):
        return None
    return prompt, " ".join(term.split())


def build(session):
    """[{question_id, concept, prompt, answer, quotation, page_number, section, passage_id}] for the session's paper: first one question per detected concept (its best-ranked usable
    passage), in the order of the report's concept evidence (most mentioned first); then, while there is room, a second one for the concepts that have another usable passage. At most
    MAX_QUESTIONS; [] when the paper has none."""
    evidence = (getattr(session, "report", None) or {}).get("concept_evidence") or []
    usable, seen = [], set()
    for item in evidence:
        questions = []
        for passage in item.get("passages", []):
            made = _cloze(passage)
            if made is not None and passage["passage_id"] not in seen:  # a sentence that names two concepts is one question, not two
                seen.add(passage["passage_id"])
                questions.append({"question_id": question_id(passage["passage_id"]), "concept": item["concept"], "prompt": made[0], "answer": made[1], "quotation": passage["sentence"],
                                  "page_number": passage.get("page_number"), "section": passage.get("section"), "passage_id": passage["passage_id"]})
        usable.append(questions)
    ordered = [questions[0] for questions in usable if questions] + [questions[1] for questions in usable if len(questions) > 1]
    return ordered[:MAX_QUESTIONS]


def public(question, number, total):
    """The question as served: without its answer or quotation."""
    return {"question_id": question["question_id"], "concept": question["concept"], "prompt": question["prompt"], "number": number, "of": total,
            "page_number": question["page_number"], "section": question["section"], "kind": "paper"}


def find(session, identifier):
    for number, question in enumerate(build(session), start=1):
        if question["question_id"] == str(identifier):
            return number, question
    return None, None


def matches(typed, answer):
    """Whether a typed attempt is the answer: case, spacing and a trailing plural "s" do not matter."""
    def plain(text):
        return re.sub(r"[\s\-]+", " ", str(text)).strip().lower().rstrip("s")

    return bool(str(typed or "").strip()) and plain(typed) == plain(answer)
