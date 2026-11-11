from types import SimpleNamespace as N

from backend.parsing import AlgorithmExtractor


def _algorithms(*sections):
    paper = N(algorithms=[], sections=[N(title=t, content=c) for t, c in sections])
    return [(a.title, a.section) for a in AlgorithmExtractor().extract(paper).algorithms]


def test_a_sentence_mentioning_an_algorithm_is_not_an_algorithm_block():
    text = "We train as described in Algorithm 1 and repeat it.\n\nSee also algorithm 2: ours is faster."
    assert _algorithms(("3 Method", text)) == []


def test_a_caption_at_the_start_of_a_line_is_extracted_once():
    text = "We train as described in Algorithm 1 and repeat it.\n\nAlgorithm 1 Training loop\nRequire: data\nfor i in 1..n\n\nText."
    assert _algorithms(("3 Method", text)) == [("Algorithm 1 Training loop", "3 Method")]
    assert _algorithms(("3 Method", "  Algorithm 2: Sampling\nstep one")) == [("Algorithm 2: Sampling", "3 Method")]


def test_bibliography_entries_are_not_algorithms():
    assert _algorithms(("References", "Algorithm 4 for sorting. 2001.")) == []
