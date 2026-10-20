"""A mention of a graph convolutional network is not also a mention of Convolutional Neural Network."""
from backend.concepts.rule_based_concept_detector import RuleBasedConceptDetector
from backend.models import Paper, Paragraph


def _counts(text):
    paper = Paper(source_path="p.pdf", metadata=None)
    paper.paragraphs.append(Paragraph(paragraph_id=1, section_title="Body", content=text))
    return {c.name: c.occurrences for c in RuleBasedConceptDetector().detect(paper).concepts}


def test_graph_convolutional_network_counts_for_graph_convolution_only():
    assert _counts("A graph convolutional network, then another graph convolutional network.") == {"Graph Convolution": 2}


def test_a_plain_convolutional_network_still_counts_and_overlapping_aliases_count_once():
    assert _counts("A graph convolutional network and a convolutional network and a CNN.") == {
        "Graph Convolution": 1, "Convolutional Neural Network": 2}
    assert _counts("A graph convolutional layer and a GCN.") == {"Graph Convolution": 2}
