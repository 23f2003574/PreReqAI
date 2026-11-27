"""Field-level accuracy of the reference parser over 22 lines in common bibliography styles (hand-written from well-known papers, not extracted from the benchmark)."""
import pytest

from backend.parsing.reference_metadata_parser import ReferenceMetadataParser

pytestmark = pytest.mark.prereqai

# (raw line, title, number of authors listed, first author's surname)
CASES = [
    ("[12] Kingma, D. P. and Ba, J. Adam: A method for stochastic optimization. arXiv preprint arXiv:1412.6980, 2014.", "Adam: A method for stochastic optimization", 2, "Kingma"),
    ("Brown, T. B. et al. Language models are few-shot learners. NeurIPS 2020.", "Language models are few-shot learners", 1, "Brown"),
    ("J. Devlin, M.-W. Chang, K. Lee, and K. Toutanova. BERT: Pre-training of deep bidirectional transformers for language understanding. In NAACL-HLT, 2019.", "BERT: Pre-training of deep bidirectional transformers for language understanding", 4, "Devlin"),
    ("Vaswani, A., Shazeer, N., Parmar, N., et al. Attention is all you need. In NeurIPS, 2017.", "Attention is all you need", 3, "Vaswani"),
    ("Ho, J., Jain, A., and Abbeel, P. Denoising diffusion probabilistic models. In Advances in Neural Information Processing Systems 33, 2020.", "Denoising diffusion probabilistic models", 3, "Ho"),
    ("[3] A. Radford, J. W. Kim, C. Hallacy, A. Ramesh, G. Goh, and I. Sutskever. Learning transferable visual models from natural language supervision. In ICML, 2021.", "Learning transferable visual models from natural language supervision", 6, "Radford"),
    ("(7) He, K., Zhang, X., Ren, S., and Sun, J. Deep residual learning for image recognition. In CVPR, 2016.", "Deep residual learning for image recognition", 4, "He"),
    ("4. Ioffe, S. and Szegedy, C. Batch normalization: Accelerating deep network training by reducing internal covariate shift. In ICML, 2015.", "Batch normalization: Accelerating deep network training by reducing internal covariate shift", 2, "Ioffe"),
    ("Hu, E. J., Shen, Y., Wallis, P., Allen-Zhu, Z., Li, Y., Wang, S., Wang, L., and Chen, W. LoRA: Low-rank adaptation of large language models. In ICLR, 2022.", "LoRA: Low-rank adaptation of large language models", 8, "Hu"),
    ("Rafailov, R., Sharma, A., Mitchell, E., Ermon, S., Manning, C. D., and Finn, C. Direct preference optimization: Your language model is secretly a reward model. arXiv preprint arXiv:2305.18290, 2023.", "Direct preference optimization: Your language model is secretly a reward model", 6, "Rafailov"),
    ("Wei, J., Wang, X., Schuurmans, D., Bosma, M., Ichter, B., Xia, F., Chi, E., Le, Q., and Zhou, D. Chain-of-thought prompting elicits reasoning in large language models. In NeurIPS, 2022.", "Chain-of-thought prompting elicits reasoning in large language models", 9, "Wei"),
    ("Jiang, A. Q., Sablayrolles, A., Roux, A., et al. Mixtral of experts. arXiv preprint arXiv:2401.04088, 2024.", "Mixtral of experts", 3, "Jiang"),
    ("OpenAI. GPT-4 technical report. arXiv preprint arXiv:2303.08774, 2023.", "GPT-4 technical report", 1, "OpenAI"),
    ("Sutskever, I., Vinyals, O., and Le, Q. V. Sequence to sequence learning with neural networks. In NIPS, 2014.", "Sequence to sequence learning with neural networks", 3, "Sutskever"),
    ("Goodfellow, I., Pouget-Abadie, J., Mirza, M., Xu, B., Warde-Farley, D., Ozair, S., Courville, A., and Bengio, Y. Generative adversarial nets. In NIPS, 2014.", "Generative adversarial nets", 8, "Goodfellow"),
    ("D. P. Kingma and M. Welling. Auto-encoding variational Bayes. In ICLR, 2014.", "Auto-encoding variational Bayes", 2, "D. P. Kingma"),
    ("K. Simonyan and A. Zisserman. Very deep convolutional networks for large-scale image recognition. In ICLR, 2015.", "Very deep convolutional networks for large-scale image recognition", 2, "K. Simonyan"),
    ("Schulman, J., Wolski, F., Dhariwal, P., Radford, A., and Klimov, O. Proximal policy optimization algorithms. arXiv preprint arXiv:1707.06347, 2017.", "Proximal policy optimization algorithms", 5, "Schulman"),
    ("[21] M. Abadi, A. Agarwal, P. Barham, et al. TensorFlow: Large-scale machine learning on heterogeneous systems. 2015.", "TensorFlow: Large-scale machine learning on heterogeneous systems", 3, "M. Abadi"),
    ("Bahdanau, D., Cho, K., and Bengio, Y. Neural machine translation by jointly learning to align and translate. In ICLR, 2015.", "Neural machine translation by jointly learning to align and translate", 3, "Bahdanau"),
    ("Hochreiter, S. and Schmidhuber, J. Long short-term memory. Neural Computation, 9(8):1735-1780, 1997.", "Long short-term memory", 2, "Hochreiter"),
    ("Aida Amini, Saadia Gabriel, and Hannaneh Hajishirzi. 2019. MathQA: Towards interpretable math word problem solving. In NAACL.", "MathQA: Towards interpretable math word problem solving", 3, "Aida Amini"),
]


def _scores():
    parser = ReferenceMetadataParser()
    title_ok = author_ok = 0
    for raw, title, count, first in CASES:
        got = parser.parse(raw)
        title_ok += got["title"].rstrip(".") == title
        author_ok += len(got["authors"]) == count and got["authors"][0].startswith(first)
    return title_ok / len(CASES), author_ok / len(CASES)


def test_the_fixture_has_at_least_twenty_lines():
    assert len(CASES) >= 20


def test_title_and_author_accuracy_are_at_least_ninety_percent():
    title, authors = _scores()
    assert title >= 0.90 and authors >= 0.90, (title, authors)


@pytest.mark.parametrize("raw,title", [(c[0], c[1]) for c in CASES[:3]])
def test_the_reported_cases_have_the_right_title(raw, title):
    assert ReferenceMetadataParser().parse(raw)["title"].rstrip(".") == title
