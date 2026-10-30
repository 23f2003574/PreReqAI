"""The detector's pairwise term-overlap checks are cached; the detected concepts and counts are unchanged."""
import pytest

from backend.concepts.rule_based_concept_detector import RuleBasedConceptDetector, _word_in
from backend.models import Paper, Paragraph

pytestmark = pytest.mark.prereqai

TEXT = ("Self-attention and multi-head attention in the Transformer; graph convolutional networks, GAT, convolutional network, "
        "policy gradient, reinforcement learning, fine-tuning, overfitting, Monte Carlo, cross-entropy, VAE, GANs, diffusion model, "
        "U-Net, softmax, RNN, LSTM, backpropagation.")


def _detect():
    paper = Paper(source_path="p.pdf", metadata=None)
    paper.paragraphs.append(Paragraph(paragraph_id=1, section_title="Body", content=TEXT))
    RuleBasedConceptDetector().detect(paper)
    return {concept.name: concept.occurrences for concept in paper.concepts}


def test_counts_are_those_measured_before_the_cache_and_overlapping_terms_still_belong_to_the_longer_concept():
    found = _detect()
    assert found == {
        "Backpropagation": 1, "Convolutional Neural Network": 1, "Cross-Entropy Loss": 1, "Diffusion Model": 1, "Fine-Tuning": 1,
        "Generative Adversarial Network": 1, "Graph Attention Network": 1, "Graph Convolution": 1, "Monte Carlo Method": 1,
        "Multi-Head Attention": 1, "Overfitting": 1, "Policy Gradient": 1, "Recurrent Neural Network": 2, "Reinforcement Learning": 1,
        "Self-Attention": 1, "Softmax": 1, "Transformer": 1, "U-Net": 1, "Variational Autoencoder": 1}
    assert "Attention" not in found  # only a standalone "attention" counts


def test_a_second_detection_reuses_the_cached_term_checks_and_the_whole_word_rule_holds():
    _detect()
    before = _word_in.cache_info()
    assert _detect() == _detect()
    after = _word_in.cache_info()
    assert after.misses == before.misses and after.hits > before.hits
    assert _word_in("gat", "gated attention") is False and _word_in("attention", "multi-head attention") is True
