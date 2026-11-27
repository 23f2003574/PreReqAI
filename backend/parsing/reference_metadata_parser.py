import re


YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")

SENTENCE_SPLIT_PATTERN = re.compile(r"\.\s+(?=[A-Z]|arXiv\b)")  # a venue such as "arXiv preprint ..." also starts a new sentence

# A full stop after a lone capital is an author's initial, not a sentence end, when a surname follows ("A. Vaswani, N. Shazeer. Title"):
# the next word is then followed by a comma, "and", a full stop or another initial. A title word ("N. Attention is all you need") is not.
_AUTHOR_INITIAL_BEFORE = re.compile(r"(?:^|[\s,])[A-Z]$")
_SURNAME_AFTER = re.compile(r"\s+(?:[A-Z]\.,?\s*)*[A-Z][\w'\u2019-]+(?:,|\s+and\b|\.|\s+[A-Z]\.)")  # "F. Christiano," after "P." too: several initials in a row
_INITIALS_ONLY = re.compile(r"^(?:[A-Z]\.?\s*)+$")


_LABEL = re.compile(r"^\s*(?:\[\d+\]|\(\d+\)|\d{1,3}[.)])\s*")  # "[12] ", "(3) " or "4. " numbering the entry
_INITIAL = re.compile(r"^[A-Z](?:\.?-?[A-Z])*$")  # "D", "P", "M.-W", "J.K"
_LAST_FIRST = re.compile(r"^[A-Z][\w'’-]+(?:\s[A-Z][\w'’-]+)?(?:,\s*[A-Z]\.|\s[A-Z]{1,3}(?:[,.](?:\s|$)|\s+and\s))")  # "Kingma, D." or the Vancouver "Vaswani A, Shazeer N."
_NEXT_WORD = re.compile(r"\s+(\S+)")
_LINE_BREAK_HYPHEN = re.compile(r"(?<=[A-Za-z])-\s+(?=[A-Za-z])")  # "Hatfield- Dodds", "Mirho- seini": a hyphen left at the end of a wrapped line
# An author-year entry ("Aida Amini, Saadia Gabriel, and Hannaneh Hajishirzi. 2019. MathQA: Towards ... In Proceedings of ...") or an APA one ("Smith, J. (2019). Title. Venue.").
_AUTHOR_YEAR = re.compile(r"^(?P<authors>.+?)[.,]?\s+(?:\((?P<year>(?:19|20)\d{2}[a-z]?)\)[.:]?|(?P<year2>(?:19|20)\d{2}[a-z]?)[.:])\s+(?P<rest>\S.*)$", re.DOTALL)
ARXIV_ID = re.compile(r"arxiv[:\s]*(?:preprint\s+)?(?:arxiv[:\s]*)?(\d{4}\.\d{4,5}|[a-z\-]+(?:\.[A-Za-z]{2})?/\d{7})(?:v\d+)?", re.IGNORECASE)
DOI = re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)")


def _split_sentences(text: str) -> list[str]:
    text = _LINE_BREAK_HYPHEN.sub("-", text)
    segments, start = [], 0
    for match in SENTENCE_SPLIT_PATTERN.finditer(text):
        if _AUTHOR_INITIAL_BEFORE.search(text[start:match.start()]) and _SURNAME_AFTER.match(text, match.start() + 1):
            continue
        segments.append(text[start:match.start()])
        start = match.end()
    segments.append(text[start:])
    return segments


def _sentence_break(text: str) -> bool:
    """Whether `text` holds a full stop that ends a sentence: one after an initial ("Quoc V. Le", "M.-W. Chang") does not."""
    return any(not _INITIAL.match(m.group(1)) for m in re.finditer(r"(\S+)\.\s+(?=[A-Z])", text))


def author_block_end(text: str) -> int | None:
    """Where the author list of an entry without a year in the author position ends (the index just after its full stop), or None. A full stop after an initial ends the list only when the
    entry is written "Surname, I." and the next word is not another initial, "and", "&" or "et"; in "I. Surname" order an initial is always followed by the surname, so the list ends
    at the first full stop after a word that is not an initial ("Toutanova.", "al.")."""
    last_first = bool(_LAST_FIRST.match(text))
    for match in re.finditer(r"(\S+)\.(?=\s+\S)", text):
        word = match.group(1).rstrip(",").split(",")[-1]
        following = _NEXT_WORD.match(text, match.end())
        nxt = following.group(1) if following else ""
        if _INITIAL.match(word):
            if last_first and nxt and nxt.lower().rstrip(",") not in ("and", "&", "et") and not _INITIAL.match(nxt.rstrip(".,")) and not (nxt[:1].islower()):
                return match.end()
            continue
        if word.lower() in ("jr", "sr", "ii", "iii"):
            continue
        return match.end()
    return None


class ReferenceMetadataParser:
    """
    Best-effort heuristic parser that splits a raw
    bibliography line into authors/title/venue/year.

    Bibliography formatting varies widely, so fields
    that can't be confidently split are left empty
    rather than guessed.
    """

    def parse(
        self,
        raw_text: str,
    ) -> dict:

        raw_text = _LABEL.sub("", _LINE_BREAK_HYPHEN.sub("-", " ".join(raw_text.split())))

        styled = _AUTHOR_YEAR.match(raw_text)
        if styled and len(styled.group("authors")) < 400 and not re.search(r"\bIn\b|Proceedings", styled.group("authors")) and not _sentence_break(styled.group("authors")):
            # "Authors. 2019. Title. Venue." : the year closes the author list, the title is the first sentence after it
            rest = [segment.strip() for segment in _split_sentences(styled.group("rest")) if segment.strip()]
            authors_segment, title, venue, year = styled.group("authors"), rest[0] if rest else "", " ".join(rest[1:]), int((styled.group("year") or styled.group("year2"))[:4])
        else:
            end = author_block_end(raw_text)
            if end is not None and len(raw_text[:end]) < 400:
                authors_segment, remainder = raw_text[:end].strip().rstrip("."), [segment.strip() for segment in _split_sentences(raw_text[end:].strip()) if segment.strip()]
                segments = [authors_segment, *remainder]
            else:
                segments = [segment.strip() for segment in _split_sentences(raw_text) if segment.strip()]
                authors_segment = segments[0] if segments else ""
            title = segments[1] if len(segments) > 1 else ""
            venue = " ".join(segments[2:]) if len(segments) > 2 else ""
            year = self._extract_year(raw_text)

        arxiv = ARXIV_ID.search(raw_text)
        doi = DOI.search(raw_text)

        return {

            "authors":
                self._split_authors(authors_segment),

            "title": re.sub(r",?\s*(?:19|20)\d{2}[a-z]?\s*$", "", title.rstrip(" .")).rstrip(" ."),

            "venue": venue,

            "year": year,

            "arxiv_id": arxiv.group(1) if arxiv else None,

            "doi": doi.group(1).rstrip(".,;)") if doi and not doi.group(1).rstrip(".,;)").endswith(("/", "-")) else None,  # one cut off at a line end is not recorded
        }

    def _split_authors(
        self,
        segment: str,
    ) -> list[str]:

        segment = re.sub(r"\bet al\.?", "", segment.replace(" and ", ", "))

        authors = []
        for author in (part.strip() for part in segment.split(",")):
            if not author:
                continue
            if authors and _INITIALS_ONLY.match(author):  # "Vaswani, A." lists the surname and its initials apart
                authors[-1] += f", {author}"
            else:
                authors.append(author)
        return authors

    def _extract_year(
        self,
        raw_text: str,
    ) -> int | None:

        matches = list(
            YEAR_PATTERN.finditer(raw_text)
        )

        if not matches:
            return None

        return int(matches[-1].group())
