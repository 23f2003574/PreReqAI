"""Concepts are detected under the acronyms and spellings papers actually use, not only the registry's canonical name."""
from backend.concepts.rule_based_concept_detector import RuleBasedConceptDetector
from backend.models import Paper, Paragraph


def _detect(*sentences):
    paper = Paper(source_path="p.pdf", metadata=None, pages=[], sections=[])
    paper.paragraphs = [Paragraph(content=text, **_extra()) for text in sentences]
    RuleBasedConceptDetector().detect(paper)
    return {c.name: c.occurrences for c in paper.concepts}


def _extra():
    import dataclasses
    required = [f.name for f in dataclasses.fields(Paragraph) if f.name != "content" and f.default is dataclasses.MISSING
                and f.default_factory is dataclasses.MISSING]
    return {name: ("" if name != "page" else 1) for name in required}


def test_acronyms_and_variant_spellings_count_toward_the_concept():
    found = _detect("We train a GNN with a GCN layer. GNNs are common.", "DDPM follows denoising diffusion. The MDP is finite.",
                    "LayerNorm and a skip connection wrap the FFN; actor critic and Q learning appear.")
    assert found["Graph Neural Network"] == 2 and found["Graph Convolution"] == 1
    assert found["Diffusion Model"] == 2 and found["Markov Decision Process"] == 1
    assert found["Layer Normalization"] == found["Residual Connection"] == found["Feed Forward Network"] == 1
    assert found["Actor-Critic"] == found["Q-Learning"] == 1


def test_aliases_match_whole_words_only_and_never_double_count_the_full_name():
    found = _detect("The gnat and the combat gate stay unmatched, as does a ragtag mdpx.",
                    "Layer Normalization is one mention; Graph Neural Network is one mention.")
    assert "Graph Neural Network" in found and found["Graph Neural Network"] == 1
    assert found["Layer Normalization"] == 1
    assert "Graph Attention Network" not in found and "Markov Decision Process" not in found
