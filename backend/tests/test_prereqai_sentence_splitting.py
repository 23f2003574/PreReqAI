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


@pytest.mark.parametrize("text, expected", [
    ("We train the model. 3 layers are used. Then we stop.", ["We train the model.", "3 layers are used.", "Then we stop."]),
    ("The loss is low. α controls the rate. Next.", ["The loss is low.", "α controls the rate.", "Next."]),
    ("Weights are tied. λ-regularisation is applied to them.", ["Weights are tied.", "λ-regularisation is applied to them."]),
    ("He stopped. 'Hello there,' she replied. End.", ["He stopped.", "'Hello there,' she replied.", "End."]),
    ("He stopped. ‘Hello there,’ she replied.", ["He stopped.", "‘Hello there,’ she replied."]),
    ("Results are in Table 2. 95% of runs converge.", ["Results are in Table 2.", "95% of runs converge."]),
])
def test_a_sentence_that_starts_with_a_digit_a_greek_letter_or_a_single_quote_is_split_off(text, expected):
    pieces = split_sentences(text)
    assert pieces == expected
    assert " ".join(pieces) == text  # the pieces stay exact, contiguous parts of the text


@pytest.mark.parametrize("text", [
    "See Fig. 3 for the setup and Eq. 4 for the loss, as in No. 5 of the list.",
    "We use a small model, e.g. 5 layers, and a variant, i.e. α fixed to zero.",
    "The noise is Gaussian w.r.t. θ, and Smith et al. 2020 report vs. 3 baselines.",
    "The value is 0.5 and the ratio is 3.14 for all runs.",
    "1. 2 apples are red.",
    "The model was trained for 3.5 epochs on α-scaled data.",
])
def test_digit_greek_and_quote_starts_do_not_split_abbreviations_decimals_or_list_labels(text):
    assert split_sentences(text) == [text]
