import re

from backend.ingestion import RawDocument
from backend.models import Paper, PaperSection

from .layout_headings import body_size, layout_headings


# An optional section number ("2", "3.1.", "IV.", "A.1") in front of a heading.
_NUMBER = r"(?:\d+(?:\.\d+)*\.?|[IVX]+\.|[A-Z](?:\.\d+)+\.?|[A-Z]\.?)[ \t]+"
_KNOWN = (
    rf"(?:{_NUMBER})?(?:Abstract|Introduction|Related Works?|Background|Preliminaries|Problem (?:Statement|Formulation|Setup)|"
    r"Method|Methods|Methodology|Approach|Model(?: Architecture)?|Overview|Experiments|Experimental (?:Setup|Results)|Evaluation|"
    r"Results(?: and Discussion)?|Analysis|Ablations?(?: Study| Studies)?|Discussion|Limitations|Broader Impacts?|Future Work|"
    r"Conclusions?(?: and Future Work)?|Acknowledge?ments?|References|Bibliography|Works Cited|Appendix|Appendices|Supplementary Material|"
    r"Notation|Datasets?|Implementation Details|Training(?: Details| Procedure| Setup)?|Experimental Details|Theoretical Analysis|"
    r"Theory|Proofs?|Ethics Statement|Reproducibility(?: Statement)?|"
    # common venue variants: NeurIPS's "Acknowledgments and Disclosure of Funding", "Conclusion and Discussion", a lettered appendix, ...
    r"(?:Reference|Literature Cited|Acknowledge?ments? and Disclosure of Funding|Conclusions? and Discussions?|Discussions? and Conclusions?|"
    r"Limitations and Future Work|Results and Analysis|Experiments and Results|Broader Impacts? Statement|"
    r"Appendix(?: [A-Z])?|Supplementary Materials?|"
    # more unnumbered headings seen in published papers (found by probing; each is a fixed phrase, so a sentence cannot match)
    r"Introduction and Motivation|Background and Related Work|Related Work and Background|Preliminaries and Notation|Notation and Preliminaries|"
    r"Main Results|Key Results|Qualitative Results|Quantitative Results|Hyperparameters|Evaluation Metrics|Experimental Setup and Results|"
    r"Training Objective|Overview of the Method|Ethical Considerations|Societal Impacts?|Code Availability|Data Availability|"
    r"Author Contributions|Competing Interests|Funding|Limitations and Broader Impacts?|Broader Impacts? and Limitations|"
    # more fixed phrases seen as unnumbered headings (the section-folding warning points at these)
    r"Motivation|Problem (?:Definition|Description)|Baselines?|Contributions|Architecture|Model Training|Case Stud(?:y|ies)|"
    r"Preliminary|Setup|Implementation|Qualitative Analysis|Error Analysis|Hyperparameter Settings|Task Description|"
    r"Problem Setting|Related Literature|Experimental Settings|Future Directions|"
    # academic variants found missing by probing (fixed phrases only)
    r"Experimental Evaluation|Empirical Evaluation|Discussion and Limitations|Limitations and Discussion|Concluding Remarks(?: and Future Work)?|"
    r"Materials and Methods|Methods and Materials|Proposed (?:Method|Approach)|Our Approach|Network Architecture|Evaluation Results))"
)
# A numbered, title-cased line such as "3.2 Scaled Dot-Product Attention": at most 8 words, no digits or sentence punctuation.
_WORD = r"(?:[A-Z][A-Za-z\-]*|of|and|the|for|in|to|with|a|an|on|via|by|from|as)"
_NUMBERED = rf"\d+(?:\.\d+)*\.?[ \t]+[A-Z][A-Za-z\-]*(?:[ \t]+{_WORD}){{0,7}}"

# IEEE-style "II. PROPOSED METHOD": a roman numeral and an all-caps title (all caps keeps an author line like "I. Goodfellow" out of the headings).
_ROMAN_CAPS = r"[IVX]+\.[ \t]+[A-Z]{3,}(?:[ \t]+[A-Z][A-Z\-]*){0,7}"

# IEEE-style title-case "II. Proposed Method": a roman numeral and at least two title-case words (one word would also match an author
# line such as "I. Goodfellow"; "I. Goodfellow and Y. Bengio" fails on the dot after "Y").
_ROMAN_TITLE = rf"[IVX]+\.[ \t]+[A-Z][a-z]+(?:[ \t]+{_WORD}){{1,7}}"

# A named appendix such as "Appendix A: Proofs" or "Appendix B. Additional Experiments" (the title follows the same title-case rule).
_NAMED_APPENDIX = rf"Appendix(?:[ \t]+(?:[A-Z]|\d+)(?:\.\d+)*)?[ \t]*[:.\-\u2013\u2014][ \t]*[A-Z][A-Za-z\-]*(?:[ \t]+{_WORD}){{0,7}}"

# A lettered appendix section such as "A Proofs" or "B.1 Additional Results" (NeurIPS/ICML style, with no "Appendix" word). Only
# trusted after the References/Appendix heading: elsewhere "A Survey Of Methods" is as likely a wrapped title-case line. No dot
# follows the letter, so a reference author line such as "A. Vaswani" is not a heading.
_LETTERED_APPENDIX = re.compile(rf"^[A-Z](?:\.\d+)*[ \t]+[A-Z][A-Za-z\-]*(?:[ \t]+{_WORD}){{0,7}}[ \t]*$", re.MULTILINE)

_BACK_MATTER_HEADING = re.compile(r"(?i:references|bibliography|works cited|acknowledge?ments?|appendix|appendices|supplementary materials?)\b")

# An unrecognised heading hidden inside a section body: a short title-cased line (the _NUMBERED shape without the number, at least two
# words, no digits or sentence punctuation) that follows a line ending a sentence. A wrapped line never qualifies (the line before it
# does not end a sentence), and a lone capitalised word is too ambiguous to report.
_UNNUMBERED_TITLE = re.compile(rf"^[A-Z][A-Za-z\-]*(?:[ \t]+{_WORD}){{1,7}}$")
_SENTENCE_END = re.compile(r"[.!?]$")
_SKIPPED_TITLES = re.compile(r"(?i:front matter|full paper|references|bibliography|works cited|acknowledge?ments?)\b")

SECTION_PATTERN = re.compile(rf"^(?:(?i:{_KNOWN}):?|{_NUMBERED}|{_ROMAN_CAPS}|{_ROMAN_TITLE}|{_NAMED_APPENDIX})[ \t]*$", re.MULTILINE)

# An abstract whose text starts on the heading's line ("Abstract\u2014We study ...", "Abstract: ...", "Abstract \u2013 ..."). The separator is required, so prose
# that merely starts with the word ("Abstract algebra is ...") is not a heading.
_INLINE_ABSTRACT = re.compile(r"^(?P<title>(?i:abstract))[ \t]*[\u2014\u2013:][ \t]*(?=\S)", re.MULTILINE)


# A bibliography whose heading is missing, split across pages or not recognised ("Cited Literature") was filed under the section before it, and
# its titles ("Graph attention networks") were counted as the paper's own concepts. Without relying on a heading, the tail of a section is
# taken as references only when it is made of many entries that each start like one and carry a year, all the way to the section's end.
_ENTRY_START = re.compile(r"^[ \t]*(?:\[\d{1,3}\][ \t]*\S|\d{1,3}[.)][ \t]+[A-Z]|[A-Z][A-Za-z'\u2019\-]+,[ \t]+(?:[A-Z]\.[ \t]?){1,3})")
_ENTRY_YEAR = re.compile(r"\b(?:19|20)\d{2}[a-z]?\b|arXiv:\d{4}\.\d{4,5}")
MIN_REFERENCES = 5  # fewer entries than this is not evidence of a bibliography
MAX_ENTRY_CHARS = 500  # a longer "entry" is running text that merely starts like one


def _reference_block_start(content):
    """Offset in `content` where a trailing run of reference entries begins, or None. Every entry of the run (a line that starts like a
    reference plus the lines that continue it) must carry a year and be short, the run must reach the end of the text and hold at least
    MIN_REFERENCES entries; any other text after it, or an entry that fails the test, ends the run before it."""
    entries, offset = [], 0
    for line in content.splitlines(keepends=True):
        if _ENTRY_START.match(line):
            entries.append([offset, line])
        elif entries:
            entries[-1][1] += line
        offset += len(line)
    run = 0
    for _, text in reversed(entries):
        if not _ENTRY_YEAR.search(text) or len(text) > MAX_ENTRY_CHARS:
            break
        run += 1
    return entries[len(entries) - run][0] if run >= MIN_REFERENCES else None


def split_reference_blocks(sections):
    """The sections with every unlabelled trailing bibliography moved into its own "References" section, which the concept detector then
    leaves out like any labelled one. Sections already titled as back matter, and everything before the bibliography, are unchanged."""
    result = []
    for section in sections:
        start = None if _BACK_MATTER_HEADING.match(section.title.strip()) else _reference_block_start(section.content)
        if start is None:
            result.append(section)
            continue
        if section.content[:start].strip():
            result.append(PaperSection(title=section.title, content=section.content[:start].strip(), page_number=section.page_number, heading_source=section.heading_source))
        result.append(PaperSection(title="References", content=section.content[start:].strip(), page_number=section.page_number))
    return result


class _LayoutHeading:
    """A heading found by its typography, shaped like the regex match the parser uses for a heading found by its wording."""

    def __init__(self, start, end, title):
        self._start, self._end, self.title = start, end, title

    def start(self):
        return self._start

    def end(self):
        return self._end

    def group(self):
        return self.title

    def groupdict(self):
        return {"title": self.title}


MIN_TYPOGRAPHIC_HEADINGS = 3
_APPENDIX_TITLE = re.compile(r"^(?:[A-Z](?:\.\d+)*[ \t]+\S|Appendix\b)")
# Single words that start many table headers and captions ("Model", "Dataset", "Results"): as a heading they must also be set like one when the paper's typography says what headings look like.
_GENERIC_HEADINGS = frozenset("model models dataset datasets approach results setup method methods training evaluation analysis architecture implementation baseline baselines "
                              "overview theory notation contributions motivation preliminary funding".split())
_NAME_LIST_ITEM = re.compile(r"^\d{1,3}\.[ \t]+[A-Z][\w'\u2019\-]+(?:[ \t]+[A-Z][\w'\u2019\-.]*){0,3}$")


def _layout_matches(document, text, matches, back):
    """(extra headings, text matches they replace): typographic headings the wording rules missed or only partly saw ("G Appendix: Full Prompts" where the wording rules took
    "Appendix: Full Prompts"), located in the document text. Not before the first recognised heading (title, authors), not in the back matter (except a lettered appendix), and each
    line of the text at most once."""
    found = layout_headings(document.pages)
    if not found:
        return [], set()
    starts, position = {}, 0
    for page in document.pages:
        starts[page.page_number] = (position, position + len(page.text))
        position += len(page.text) + 1
    taken = [(m.start(), m.end()) for m in matches]
    first = matches[0].start() if matches else None
    top_page1 = max((size for number, _, size, _ in found if number == document.pages[0].page_number), default=None)
    result, used, replaced = [], set(), set()
    for number, title, size, bold in found:
        if number not in starts:
            continue
        low, high = starts[number]
        pattern = re.compile(r"^[ \t]*" + r"\s+".join(map(re.escape, title.split())) + r"[ \t]*$", re.MULTILINE)
        match = next((m for m in pattern.finditer(text, low, high) if m.start() not in used), None)
        if match is None:
            continue
        if first is None and number == document.pages[0].page_number and size == top_page1:
            continue  # the paper's title
        if (first is not None and match.start() < first) or (back is not None and match.start() > back and not _APPENDIX_TITLE.match(title)):
            continue
        overlapping = [(a, b) for a, b in taken if a <= match.start() < b or match.start() <= a < match.end()]
        if overlapping:
            if all(match.start() < a and b <= match.end() for a, b in overlapping):
                replaced.update(a for a, _ in overlapping)  # the heading's own line says more than the wording rules took of it
            else:
                continue
        used.add(match.start())
        result.append(_LayoutHeading(match.start(), match.end(), title))
    return result, replaced


def _drop_name_lists(text, matches):
    """A numbered list of names ("1. Gordon Chi", "2. Virginia Adams": contributors, annotators) is not a run of sections: three or more numbered name lines in a row with no text
    between them are dropped."""
    drop, run = set(), []
    for index, match in enumerate(matches):
        item = bool(_NAME_LIST_ITEM.match(match.group().strip()))
        nxt = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        gap = len(text[match.end():nxt].strip())
        if item and (not run or gap < 60 or run):
            run.append(index)
            if gap >= 60:  # the last name of the list is followed by text
                (drop.update(run) if len(run) >= 3 else None)
                run = []
            continue
        (drop.update(run) if len(run) >= 3 else None)
        run = []
    (drop.update(run) if len(run) >= 3 else None)
    return [match for index, match in enumerate(matches) if index not in drop]


def _typographically_supported(document, match):
    """A generic one-word heading found by wording is kept only when the line is set like a heading (bold or larger than the body text) on a page with typography; without typography
    on the page, or in a paper whose headings carry none, the wording is all there is."""
    title = re.sub(r"^[\dIVXA-Z.]+\s+", "", match.group().strip()).strip(" :").lower()
    if title not in _GENERIC_HEADINGS:
        return True
    body, offset = body_size(document.pages), 0
    for page in document.pages:
        if match.start() < offset + len(page.text) + 1:
            lines = [line for line in (page.layout or []) if re.sub(r"^[\dIVXA-Z.]+\s+", "", line["text"]).strip(" :").lower() == title]
            return not page.layout or body is None or not lines or any(line["bold"] or line["size"] >= body * 1.1 for line in lines)
        offset += len(page.text) + 1
    return True


def _page_of(document, offset):
    position = 0
    for page in document.pages:
        position += len(page.text) + 1
        if offset < position:
            return page.page_number
    return document.pages[-1].page_number if document.pages else None


class ScientificSectionParser:
    """
    Detects high-level scientific paper sections
    using common research-paper headings.
    """

    def parse(self, document: RawDocument) -> Paper:

        text = document.full_text

        matches = sorted([*SECTION_PATTERN.finditer(text), *_INLINE_ABSTRACT.finditer(text)], key=lambda m: m.start())

        back = next((m.start() for m in matches if _BACK_MATTER_HEADING.match(m.group().strip())), None)

        if back is not None:  # lettered appendix headings, only once the back matter has begun

            matches = sorted(
                [*matches, *(m for m in _LETTERED_APPENDIX.finditer(text) if m.start() > back)],
                key=lambda m: m.start(),
            )

        extra, replaced = _layout_matches(document, text, matches, back) if document.pages else ([], set())
        layout_starts = {m.start() for m in extra}
        matches = sorted([*(m for m in matches if m.start() not in replaced), *extra], key=lambda m: m.start())
        if document.pages and len(layout_headings(document.pages)) >= MIN_TYPOGRAPHIC_HEADINGS:  # typography tells headings from text only where the paper's headings have any
            matches = [m for m in matches if m.start() in layout_starts or _typographically_supported(document, m)]
        matches = _drop_name_lists(text, matches)

        if not matches:
            sections = [
                PaperSection(
                    title="Full Paper",
                    content=text.strip(),
                )
            ]
        else:
            sections = []

            front = text[:matches[0].start()].strip()

            if front:  # title and abstract text before the first recognised heading

                sections.append(PaperSection(title="Front Matter", content=front, page_number=_page_of(document, 0)))

            for index, match in enumerate(matches):

                start = match.end()

                end = (
                    matches[index + 1].start()
                    if index + 1 < len(matches)
                    else len(text)
                )

                sections.append(
                    PaperSection(
                        title=match.groupdict().get("title") or match.group().strip(),
                        content=text[start:end].strip(),
                        page_number=_page_of(document, match.start()),
                        heading_source="layout" if match.start() in layout_starts else "text",
                    )
                )

        for page in document.pages:
            page.layout = []  # typography is only needed to find headings; it is not kept in the paper or its saved session

        return Paper(
            source_path=document.source_path,
            metadata=document.metadata,
            pages=document.pages,
            sections=split_reference_blocks(sections),
        )


def absorbed_heading_candidates(paper: Paper) -> list:
    """Lines inside a recognised section's body that look like a heading the parser did not recognise (so the text after them
    was filed under the previous section). Report-only: sections are never changed. Front matter and bibliography are not
    inspected (author names and reference titles have the same shape)."""

    found = []

    for section in paper.sections:

        if _SKIPPED_TITLES.match(section.title):
            continue

        lines = [line.strip() for line in section.content.splitlines()]

        for before, line in zip(lines, lines[1:]):

            if line and _UNNUMBERED_TITLE.match(line) and _SENTENCE_END.search(before):
                found.append((section.title, line))

    return found
