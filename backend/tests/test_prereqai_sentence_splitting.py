import pytest

from backend.sentences import split_sentences

pytestmark = pytest.mark.prereqai


@pytest.mark.parametrize("text", [
    "Vaswani et al. (2017) introduced the Transformer, which relies entirely on attention.",
    "Following Eq. (3), we minimise the loss over all tokens in the batch.",
    "We use a small model, e.g. GPT-2 Small, for all experiments in this section.",
    "See Fig. 3 for the setup, i.e. Section 4 describes it in detail.",
    "The method of J. Smith and K. Lee. Their results were later extended by Refs. [3] and [4].",
])
def test_an_abbreviation_does_not_end_a_sentence(text):
    pieces = split_sentences(text)
    assert len(pieces) == (2 if "Lee. Their" in text else 1), pieces


def test_real_sentence_ends_still_split_and_pieces_are_exact_parts_of_the_text():
    text = "Attention is all you need. It replaces recurrence (see Eq. 2). We train on 8 GPUs! Does it scale? Yes."
    pieces = split_sentences(text)
    assert pieces == ["Attention is all you need.", "It replaces recurrence (see Eq. 2).", "We train on 8 GPUs!", "Does it scale?", "Yes."]
    assert all(piece in text for piece in pieces)


def test_etc_can_still_end_a_sentence_and_empty_text_is_safe():
    assert split_sentences("We tried SGD, Adam, etc. The result was the same.") == ["We tried SGD, Adam, etc.", "The result was the same."]
    assert split_sentences("") == [""]
