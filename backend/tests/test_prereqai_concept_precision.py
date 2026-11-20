"""Concept detection precision: acronym aliases inside other names, everyday words in technical papers, and the real-paper benchmark."""
import pytest

from backend.concepts.rule_based_concept_detector import RuleBasedConceptDetector
from backend.models import Paper, Paragraph
from backend.prereqai_eval import benchmark

pytestmark = pytest.mark.prereqai


def counts(*sections):
    paper = Paper(source_path="x", metadata=None)
    paper.paragraphs = [Paragraph(i, title, text) for i, (title, text) in enumerate(sections, 1)]
    return {c.name: c.occurrences for c in RuleBasedConceptDetector().detect(paper).concepts}


def test_the_cnn_of_the_news_dataset_is_not_a_convolutional_network():
    assert "Convolutional Neural Network" not in counts(("Experiments", "We evaluate on CNN/DailyMail and on the CNN-DM split, and read CNN news articles from the test set."))
    assert counts(("Method", "A CNN with three layers, and a CNN/RNN hybrid, beat the CNN/DailyMail baseline."))["Convolutional Neural Network"] == 2  # real mentions stay, only the dataset goes


def test_a_bare_attention_in_an_example_prompt_does_not_count_in_a_language_model_paper_but_technical_uses_do():
    paper = [("Introduction", "Language models, fine-tuning and gradient-based prompting are studied here, with a transformer baseline." + " Filler about language models. " * 30),
             ("Appendix", "The weather was mild and the city was quiet that week. " * 8 + "Q: What does a dog want? Choices: (a) bone (b) charm (c) petted (d) lots of attention (e) walked. " + "The market opened early and the streets were busy again. " * 8)]
    assert "Attention" not in counts(*paper)
    technical = [("Method", "The transformer uses attention over the keys and queries, and attention weights are normalised by a softmax. Attention is computed per head.")]
    assert counts(*technical)["Attention"] >= 2


def test_a_mention_next_to_another_concept_still_counts_and_section_attribution_is_unchanged():
    assert counts(("Method", "Self-Attention helps. Attention is all."))["Attention"] == 1


def test_finetuned_without_a_hyphen_is_fine_tuning():
    assert counts(("Intro", "We finetune a pretrained language model; finetuned models and finetuning data matter."))["Fine-Tuning"] == 3


def test_real_paper_concept_precision_reaches_the_target_without_losing_recall():
    report = benchmark.evaluate_benchmark()
    assert report["concepts"]["precision"] >= 0.97 and report["concepts"]["recall"] == 1.0  # was P=0.92 R=1.00
    dpo = next(row for row in report["papers"] if row["id"] == "dpo")
    cot = next(row for row in report["papers"] if row["id"] == "chain-of-thought")
    assert "Convolutional Neural Network" not in dpo["concepts"]["spurious"] and "Attention" not in cot["concepts"]["spurious"]
