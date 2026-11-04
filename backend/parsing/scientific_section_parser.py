import re

from backend.ingestion import RawDocument
from backend.models import Paper, PaperSection


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
    r"Author Contributions|Competing Interests|Funding|Limitations and Broader Impacts?|Broader Impacts? and Limitations))"
)
# A numbered, title-cased line such as "3.2 Scaled Dot-Product Attention": at most 8 words, no digits or sentence punctuation.
_WORD = r"(?:[A-Z][A-Za-z\-]*|of|and|the|for|in|to|with|a|an|on|via|by|from|as)"
_NUMBERED = rf"\d+(?:\.\d+)*\.?[ \t]+[A-Z][A-Za-z\-]*(?:[ \t]+{_WORD}){{0,7}}"

# IEEE-style "II. PROPOSED METHOD": a roman numeral and an all-caps title (all caps keeps an author line like "I. Goodfellow" out of the headings).
_ROMAN_CAPS = r"[IVX]+\.[ \t]+[A-Z]{3,}(?:[ \t]+[A-Z][A-Z\-]*){0,7}"

# A named appendix such as "Appendix A: Proofs" or "Appendix B. Additional Experiments" (the title follows the same title-case rule).
_NAMED_APPENDIX = rf"Appendix(?:[ \t]+(?:[A-Z]|\d+)(?:\.\d+)*)?[ \t]*[:.\-\u2013\u2014][ \t]*[A-Z][A-Za-z\-]*(?:[ \t]+{_WORD}){{0,7}}"

# A lettered appendix section such as "A Proofs" or "B.1 Additional Results" (NeurIPS/ICML style, with no "Appendix" word). Only
# trusted after the References/Appendix heading: elsewhere "A Survey Of Methods" is as likely a wrapped title-case line. No dot
# follows the letter, so a reference author line such as "A. Vaswani" is not a heading.
_LETTERED_APPENDIX = re.compile(rf"^[A-Z](?:\.\d+)*[ \t]+[A-Z][A-Za-z\-]*(?:[ \t]+{_WORD}){{0,7}}[ \t]*$", re.MULTILINE)

_BACK_MATTER_HEADING = re.compile(r"(?i:references|bibliography|works cited|acknowledge?ments?|appendix|appendices|supplementary materials?)\b")

SECTION_PATTERN = re.compile(rf"^(?:(?i:{_KNOWN}):?|{_NUMBERED}|{_ROMAN_CAPS}|{_NAMED_APPENDIX})[ \t]*$", re.MULTILINE)


class ScientificSectionParser:
    """
    Detects high-level scientific paper sections
    using common research-paper headings.
    """

    def parse(self, document: RawDocument) -> Paper:

        text = document.full_text

        matches = list(SECTION_PATTERN.finditer(text))

        back = next((m.start() for m in matches if _BACK_MATTER_HEADING.match(m.group().strip())), None)

        if back is not None:  # lettered appendix headings, only once the back matter has begun

            matches = sorted(
                [*matches, *(m for m in _LETTERED_APPENDIX.finditer(text) if m.start() > back)],
                key=lambda m: m.start(),
            )

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

                sections.append(PaperSection(title="Front Matter", content=front))

            for index, match in enumerate(matches):

                start = match.end()

                end = (
                    matches[index + 1].start()
                    if index + 1 < len(matches)
                    else len(text)
                )

                sections.append(
                    PaperSection(
                        title=match.group().strip(),
                        content=text[start:end].strip(),
                    )
                )

        return Paper(
            source_path=document.source_path,
            metadata=document.metadata,
            pages=document.pages,
            sections=sections,
        )
