"""A word split by a line-end hyphen is still detected as its concept; real compounds keep their hyphen."""
from backend.tests.test_prereqai_concept_aliases import _detect


def test_a_word_broken_across_lines_is_detected_as_one_word():
    found = _detect("We study trans-\nformer models and train them with back-\npropagation.",
                    "The trans-\nformers scale; gradi-\nent descent is used.")
    assert found["Transformer"] == 2 and found["Backpropagation"] == 1
    assert found["Gradient Descent"] == 1


def test_real_compounds_and_ordinary_wrapped_words_are_unchanged():
    found = _detect("The self-\nattention layer and multi-\nhead attention follow; a hyper-\nparameter and a state-\nof-the-art run.",
                    "A transformer and a self-attention layer appear plainly.")
    assert found["Self-Attention"] == 2 and found["Transformer"] == 1
    assert "Multi-Head Attention" in found and "Attention" not in found
