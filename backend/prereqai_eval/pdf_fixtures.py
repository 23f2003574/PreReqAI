"""Synthetic academic PDFs for the end-to-end evaluation, generated deterministically with PyMuPDF.

Each fixture is a layout (one or two columns), a list of blocks and the annotations written from what the text was designed to show:
`sections` (the headings a reader sees and the role each plays in the coverage policy), `concepts` (registry concepts the text discusses)
and `covered` (prerequisite subjects the text *teaches* in a Background or Method-like section, so coverage must report them covered).
The annotations are never adjusted to a run's output. These are texts written for this repository, not published papers: a result on them
is evidence about the pipeline's logic, not about real papers."""
import textwrap

PAGE = (595, 330)  # small pages, so a short text still spans the 3+ pages a running header needs to be recognised as one
TOP, BOTTOM, LINE = 80, 285, 12

FILLER = ("We describe the setting in plain terms and note the choices made along the way. The remaining paragraphs give the details "
          "that a reader needs in order to follow the argument and repeat the study.")

# Block kinds: ("title", text), ("h", heading), ("p", paragraph), ("full", paragraph spanning both columns of a two-column page)
FIXTURES = [
    {
        "id": "numbered-1col", "title": "Numbered headings, one column", "columns": 1, "header": "A Study of Sequence Models",
        "blocks": [
            ("title", "A Study of Sequence Models"),
            ("h", "Abstract"), ("p", "We study sequence modelling. " + FILLER),
            ("h", "1 Introduction"), ("p", "We study a Transformer model built on self-attention for sequence tasks. " + FILLER),
            ("h", "2 Background"),
            ("p", "Linear algebra underlies the model. Matrix multiplication maps vectors, the eigenvalues describe a matrix and vector spaces give "
                  "the setting. We use linear algebra throughout. " + FILLER),
            ("h", "3 Method"),
            ("p", "The Transformer applies self-attention and a softmax over scores. Self-attention lets each token attend to the others, and the "
                  "softmax normalises the scores. " + FILLER),
            ("h", "4 Experiments on CIFAR-10"),
            ("p", "We report accuracy. The evaluation uses random variables for noise, a conditional probability model and Bayes rule. " + FILLER),
            ("h", "5 Conclusion"), ("p", "The model works well. " + FILLER),
            ("h", "References"),
            *[("p", f"[{i}] A. Author and B. Writer. A paper about sequence models. Journal of Examples, 20{10 + i}.") for i in range(1, 7)],
        ],
        "sections": [("Abstract", "other"), ("Introduction", "other"), ("Background", "instructional"), ("Method", "instructional"),
                     ("Experiments on CIFAR-10", "other"), ("Conclusion", "other"), ("References", "related")],
        "concepts": ["Transformer", "Self-Attention", "Softmax"],
        "covered": ["Linear Algebra", "Attention"],  # Probability appears only in the Experiments section: mentioned, never covered
    },
    {
        "id": "unnumbered-1col", "title": "Unnumbered headings, one column", "columns": 1, "header": "Learning by Gradients",
        "blocks": [
            ("title", "Learning by Gradients"),
            ("h", "Abstract"), ("p", "We train networks with gradients. " + FILLER),
            ("h", "Introduction"), ("p", "Training uses backpropagation and gradient descent with a cross-entropy loss. " + FILLER),
            ("h", "Preliminaries"),
            ("p", "We use random variables, joint distributions and Bayes theorem. A random variable has a distribution and Bayes theorem "
                  "relates conditional probability to the joint distribution. " + FILLER),
            ("h", "Method"),
            ("p", "Backpropagation applies the chain rule to partial derivatives, and the Jacobian collects them. The chain rule and the "
                  "Jacobian give the gradient used by gradient descent. " + FILLER),
            ("h", "Results"), ("p", "A matrix product dominates the cost of each step. " + FILLER),
            ("h", "Discussion"), ("p", "The method is simple. " + FILLER),
            ("h", "References"),
            *[("p", f"[{i}] C. Author and D. Writer. A paper about learning. Journal of Examples, 20{10 + i}.") for i in range(1, 7)],
        ],
        "sections": [("Abstract", "other"), ("Introduction", "other"), ("Preliminaries", "instructional"), ("Method", "instructional"),
                     ("Results", "other"), ("Discussion", "other"), ("References", "related")],
        "concepts": ["Backpropagation", "Gradient Descent", "Cross-Entropy Loss"],
        "covered": ["Probability", "Calculus"],  # Linear Algebra gets one mention, in Results: mentioned, never covered
    },
    {
        "id": "ieee-2col", "title": "Roman-numbered headings, two columns", "columns": 2, "header": "Graph Learning Notes",
        "blocks": [
            ("title", "Graph Learning Notes"),
            ("full", "ABSTRACT We study a Graph Neural Network with message passing. " + FILLER),
            ("h", "I. INTRODUCTION"), ("p", "A Graph Neural Network uses message passing between neighbouring nodes. " + FILLER + " " + FILLER),
            ("h", "II. BACKGROUND"),
            ("p", "Graph theory describes the data. Directed graphs and weighted graphs are stored as an adjacency matrix, and shortest paths follow "
                  "from the adjacency matrix. " + FILLER + " " + FILLER),
            ("h", "III. PROPOSED METHOD"),
            ("p", "Each layer of the Graph Neural Network sends a message along every edge, and message passing repeats for several layers. "
                  + FILLER + " " + FILLER),
            ("h", "IV. EXPERIMENTS"),
            ("p", "We use a random variable for the noise, a conditional probability table and Bayes rule when scoring. " + FILLER + " " + FILLER),
            ("h", "V. CONCLUSION"), ("p", "The approach works. " + FILLER + " " + FILLER),
            ("h", "REFERENCES"),
            *[("p", f"[{i}] E. Author and F. Writer. A paper about graphs. Journal of Examples, 20{10 + i}.") for i in range(1, 7)],
        ],
        "sections": [("Introduction", "other"), ("Background", "instructional"), ("Proposed Method", "instructional"), ("Experiments", "other"),
                     ("Conclusion", "other"), ("References", "related")],
        "concepts": ["Graph Neural Network", "Message Passing"],
        "covered": ["Graphs"],  # Probability appears only in Experiments
    },
]


def _lines(text, width):
    return textwrap.wrap(text, width=width, break_long_words=False) or [""]


def build_pdf(fixture, path):
    """Write one fixture as a PDF at `path`: running header and page number on every page, text laid out in one or two columns."""
    import pymupdf  # imported here so the module can be read without PyMuPDF; the caller reports a missing library

    document, width, height = pymupdf.open(), *PAGE
    columns, cursor = fixture["columns"], {"page": None, "column": 0, "y": TOP}
    left = [50] if columns == 1 else [50, 315]
    chars = 92 if columns == 1 else 40

    def new_page():
        page = document.new_page(width=width, height=height)
        page.insert_text((50, 30), fixture["header"], fontsize=9, fontname="helv")
        page.insert_text((width / 2 - 20, height - 20), f"Page {document.page_count}", fontsize=9, fontname="helv")
        cursor.update(page=page, column=0, y=TOP)

    def put(text, bold=False, full=False):
        for line in _lines(text, 92 if full else chars):
            if cursor["y"] > BOTTOM:
                if full or cursor["column"] + 1 >= len(left):
                    new_page()
                else:
                    cursor.update(column=cursor["column"] + 1, y=TOP)
            x = 50 if full else left[cursor["column"]]
            cursor["page"].insert_text((x, cursor["y"]), line, fontsize=11 if bold else 9, fontname="hebo" if bold else "helv")
            cursor["y"] += LINE + (2 if bold else 0)

    new_page()
    for kind, text in fixture["blocks"]:
        put(text, bold=kind in ("title", "h"), full=kind in ("title", "full"))
    document.set_metadata({"title": "", "author": "", "creationDate": "", "modDate": ""})
    document.save(str(path), deflate=False, no_new_id=True)
    document.close()
    return path


def write_fixture_pdfs(directory, fixtures=None):
    """{fixture id: path} for the PDFs written into `directory`; the same fixtures always give the same pages."""
    from pathlib import Path

    Path(directory).mkdir(parents=True, exist_ok=True)
    return {fixture["id"]: build_pdf(fixture, Path(directory) / f"{fixture['id']}.pdf") for fixture in (fixtures or FIXTURES)}
