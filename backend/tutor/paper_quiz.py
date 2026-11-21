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
                                  "page_number": passage.get("page_number"), "section": passage.get("section"), "passage_id": passage["passage_id"],
                                  "aliases": list(_aliases(item["concept"])), "kind": "cloze"})
        usable.append(questions)
    ordered = [questions[0] for questions in usable if questions] + [questions[1] for questions in usable if len(questions) > 1]
    return ordered[:MAX_QUESTIONS]


def public(question, number, total):
    """The question as served: without its answer or quotation."""
    return {"question_id": question["question_id"], "concept": question["concept"], "prompt": question["prompt"], "number": number, "of": total,
            "page_number": question["page_number"], "section": question["section"], "kind": "paper" if question.get("kind", "cloze") == "cloze" else question["kind"]}


def _aliases(concept):
    from backend.concepts.concept_registry import ConceptRegistry

    return next((c.aliases for c in ConceptRegistry(custom=True).all() if c.name == concept), ())


MATH_SUBJECTS = ("Linear Algebra", "Calculus", "Probability", "Statistics", "Information Theory", "Optimization")
MAX_CLAIMS, MAX_EQUATIONS, MAX_ORDER = 4, 3, 2
_SENTENCES = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\[\u201c\"])")


def _rank(*parts):
    import hashlib

    return hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()


def _on_page(session, sentence, page_number):
    """Whether `sentence` is a verbatim part of the text of the page it cites (whitespace aside): every comprehension question quotes the paper, never paraphrases it."""
    for page in session.paper.pages:
        if page.page_number == page_number:
            return " ".join(sentence.split()) in " ".join(page.text.split())
    return False


def _claims(session, evidence):
    """True/false questions: a verified sentence as written (true) or with its concept's term replaced by another detected concept (false), alternating down the concept list."""
    names = [item["concept"] for item in evidence]
    made = []
    for position, item in enumerate(evidence):
        for passage in item.get("passages", []):
            sentence, term = " ".join(passage["sentence"].split()), passage.get("matched_term") or ""
            if _cloze(passage) is None or len(term) < 3 or len(made) >= MAX_CLAIMS:
                continue
            truthy = len(made) % 2 == 0
            prompt = sentence
            if not truthy:
                other = next((n for n in names if n != item["concept"] and n.lower() not in sentence.lower()), None)
                pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])", re.IGNORECASE)
                if other is None or len(pattern.findall(sentence)) != 1:
                    continue
                prompt = pattern.sub(other, sentence)
            made.append({"question_id": f"claim~{passage['passage_id']}:1", "concept": item["concept"], "kind": "claim", "prompt": f"True or false (answer true or false): {prompt}",
                         "answer": "true" if truthy else "false", "quotation": passage["sentence"], "page_number": passage.get("page_number"), "section": passage.get("section"),
                         "passage_id": passage["passage_id"], "aliases": []})
            break
    return made


def _equations(session):
    from backend.parsing.math_subtopics import subtopics_of

    made, used = [], set()
    for equation in session.paper.equations:
        for topic, subject, matched, why in subtopics_of(equation.expression):
            if subject in MATH_SUBJECTS and subject not in used and len(made) < MAX_EQUATIONS and equation.page_number:
                used.add(subject)
                others = sorted((x for x in MATH_SUBJECTS if x != subject), key=lambda x: _rank(equation.equation_id, x))[:3]
                options = sorted([subject, *others], key=lambda x: _rank(equation.equation_id, "order", x))
                tag = f"({equation.tag}) " if equation.tag else ""
                made.append({"question_id": f"equation~{equation.equation_id}:1", "concept": subject, "kind": "equation",
                             "prompt": f"Equation {tag}on page {equation.page_number} reads: {' '.join(equation.expression.split())[:200]} Which subject do you need to read it: {', '.join(options)}? (it uses {matched!r})",
                             "answer": subject, "quotation": " ".join(equation.expression.split()), "page_number": equation.page_number, "section": equation.section,
                             "passage_id": f"equation-{equation.equation_id}", "aliases": []})
                break
    return made


def _ordering(session):
    """Method-step questions: three consecutive sentences of one paragraph, shown shuffled, to be put back in the paper's order."""
    from backend.prerequisites.missing_prerequisite_analyzer import section_role

    made = []
    for paragraph in session.paper.paragraphs:
        if len(made) >= MAX_ORDER or paragraph.page_number is None or section_role(paragraph.section_title or "") != "instructional":
            continue
        sentences = [" ".join(x.split()) for x in _SENTENCES.split(" ".join((paragraph.content or "").split()))]
        for start in range(len(sentences) - 2):
            trio = sentences[start:start + 3]
            if all(40 <= len(x) <= 260 and sum(c.isdigit() for c in x) < 0.1 * len(x) and not _HYPHEN_RESIDUE.search(x) for x in trio) and all(_on_page(session, x, paragraph.page_number) for x in trio):
                order = sorted(range(3), key=lambda i: _rank(paragraph.paragraph_id, start, i))
                if order == [0, 1, 2]:
                    order = [1, 2, 0]
                letters = "ABC"
                shown = "  ".join(f"{letters[k]}. {trio[order[k]]}" for k in range(3))
                answer = " ".join(letters[order.index(i)] for i in range(3))  # which shown letter holds the first, second and third sentence
                made.append({"question_id": f"order~{paragraph.paragraph_id}-{start}:1", "concept": paragraph.section_title or "method", "kind": "order",
                             "prompt": f"Put these three sentences from section {paragraph.section_title} in the order the paper gives them. Answer with the letters, for example B A C. {shown}",
                             "answer": answer, "quotation": " ".join(trio), "page_number": paragraph.page_number, "section": paragraph.section_title, "passage_id": f"order-{paragraph.paragraph_id}-{start}",
                             "aliases": []})
                break
    return made


def build_comprehension(session):
    """Questions that test understanding beyond recall, each answerable from a verbatim quotation (or the printed equation) with its page and section: true/false claims, equation-to-subject
    questions and method-step ordering. [] kinds the paper cannot support are simply absent; ids start with claim~, equation~ or order~."""
    evidence = (getattr(session, "report", None) or {}).get("concept_evidence") or []
    return [*_claims(session, evidence), *_equations(session), *_ordering(session)]


def find(session, identifier):
    for number, question in enumerate([*build(session), *build_comprehension(session)], start=1):
        if question["question_id"] == str(identifier):
            return number, question
    return None, None


def _letters(text):
    return " ".join(re.findall(r"[a-c]", str(text).lower())) if re.fullmatch(r"[\sA-Ca-c,;>\-]*", str(text)) else ""


def check(question, typed):
    """Whether a typed attempt is the answer to this question, by its kind: true/false (true, t, yes), the three letters in order, a subject name, or the term (or one of its aliases)."""
    typed = str(typed or "").strip()
    if not typed:
        return False
    kind = question.get("kind", "cloze")
    if kind == "claim":
        return {"true": "true", "t": "true", "yes": "true", "false": "false", "f": "false", "no": "false"}.get(typed.lower()) == question["answer"]
    if kind == "order":
        return _letters(typed) == question["answer"].lower()
    if kind == "equation":
        return " ".join(typed.lower().split()) == question["answer"].lower()
    return matches(typed, question["answer"], question.get("aliases", ()))


def matches(typed, answer, aliases=()):
    """Whether a typed attempt is the answer or one of its registry aliases: case, spacing, hyphens and a plural ("model" and "models") do not matter. A plural counts only when the shorter
    word has at least four letters, so "bias" is never "bia" (the old trailing-"s" stripping made them equal)."""
    def plain(text):
        return re.sub(r"[\s\-]+", " ", str(text)).strip().lower()

    def same(a, b):
        if a == b:
            return True
        short, long = sorted((a, b), key=len)
        return len(short) >= 4 and long in (short + "s", short + "es")

    attempt = plain(typed)
    return bool(attempt) and any(same(attempt, plain(candidate)) for candidate in (answer, *aliases))
