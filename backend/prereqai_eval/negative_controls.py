"""Negative controls: short documents from other fields that use words PreReqAI's registry also knows ("transformer", "dropout", "attention", "regularization", "embedding"). A paper that says nothing about
machine learning must produce no machine-learning concept and no machine-learning prerequisite; each control is a generated PDF run through the production pipeline. They are hand-written (AI-authored,
provisional) and few: they guard against a regression of the domain rule, they do not measure how well it generalises to real non-ML papers."""
import os
import tempfile

CONTROLS = {
    "power-grid": ["Transformer Faults in Power Grids", "1 Introduction",
                   "Power transformer faults in substations are costly. The transformer winding overheats and the transformer oil degrades.",
                   "A transformer with high load fails early. The residual stress of the tank is low.",
                   "Regularization of the grid by the state is discussed. The transformer is inspected yearly.",
                   "2 Method", "We measure transformer temperature with sensors and compare transformer ratings across substations."],
    "student-dropout": ["Student Dropout in Universities", "1 Introduction",
                        "Student dropout in universities is rising. Dropout rates rose after the pandemic.",
                        "Dropout is highest in the first year. Attention to students matters, and attention from teachers.",
                        "The embedding of students in the community helps. Overfitting of curricula to exams is a concern.",
                        "2 Method", "We survey dropout across departments and relate dropout to attention from advisers."],
}


NEUTRAL_PADDING = ["We describe the study design, the data collection and the analysis in the sections that follow.",
                   "The results are discussed with their limits, and the conclusions are stated at the end of the paper."]  # field-neutral sentences, so a control is as long as a short paper


def _pdf(lines):
    import pymupdf  # a runtime requirement, unlike reportlab

    handle, path = tempfile.mkstemp(suffix=".pdf")
    os.close(handle)
    document = pymupdf.open()
    page, y = document.new_page(), 52
    for line in [*lines, *NEUTRAL_PADDING]:
        page.insert_text((50, y), line, fontsize=11)
        y += 16
    document.save(path)
    document.close()
    return path


def evaluate(controls=None):
    """{"controls": {name: {"concepts": [...], "prerequisites": [...]}}, "clean": share of controls with neither}."""
    from backend.pipeline import ResearchPaperPipeline

    found = {}
    for name, lines in (controls or CONTROLS).items():
        path = _pdf(lines)
        try:
            paper = ResearchPaperPipeline().run(path).paper
        finally:
            os.remove(path)
        found[name] = {"concepts": [c.name for c in paper.concepts], "prerequisites": [p.concept for p in paper.prerequisites]}
    clean = sum(1 for row in found.values() if not row["concepts"] and not row["prerequisites"])
    return {"controls": found, "clean": clean / len(found) if found else 1.0}


# Further documents from other fields that reuse words of the registry, and two machine-learning positives that must still be read. Hand-written (AI-authored, provisional).
CONTROLS.update({
    "neuroscience": ["Hippocampal Neural Networks and Attention in Mice", "1 Introduction",
                     "Neural networks in the hippocampus encode space. Selective attention modulates neural firing in cortex.",
                     "The concentration gradient of dopamine drives learning. Reinforcement of behaviour follows reward in mice.",
                     "2 Method", "We recorded neurons and measured the gradient across layers of cortex and the probability of firing."],
    "linguistics": ["Language Models in Historical Linguistics", "1 Introduction",
                    "A language model of Old English grammar is proposed by linguists. Embedding of words in sentences, attention to syntax and transformer verbs are studied.",
                    "2 Method", "We annotate fine-tuning of dialects and the training of scribes."],
    "finance": ["Portfolio Risk Optimization", "1 Introduction",
                "We study convex optimization of a portfolio. The probability of loss and the expected value are estimated by Monte Carlo simulation.",
                "Linear regression of returns on factors gives the loss function. Gradient of the objective is computed analytically.",
                "2 Method", "We fit a regression model by least squares and report standard errors."],
    "education": ["Teacher Attention and Classroom Learning", "1 Introduction",
                  "Teacher attention shapes student learning. Attention to pupils with low reading scores improves reinforcement of skills.",
                  "2 Method", "We observe the training of teachers and the embedding of reading in the curriculum."],
    "ecology": ["Gradient Analysis of Forest Transformers", "1 Introduction",
                "Species richness follows an environmental gradient. Attention to rare species matters.",
                "2 Method", "We measure the gradient of soil moisture and the dropout of seedlings."],
    "psychology": ["Selective Attention and Memory Embedding", "1 Introduction",
                   "Selective attention and working memory are studied. Participants show attention lapses and reinforcement learning of habits in behavioural trials.",
                   "2 Method", "We recorded reaction time and the learning rate of participants."],
    "electronics": ["Transformer Design for Switching Supplies", "1 Introduction",
                    "The transformer core saturates under load. Dropout of the supply voltage and regularization of the output are measured.",
                    "2 Method", "We test the transformer winding and the gradient of temperature."],
    "history": ["Attention and Training in Medieval Guilds", "1 Introduction",
                "Guild training of apprentices drew the attention of the town. The embedding of guilds in civic life is studied.",
                "2 Method", "We read charters on fine-tuning of wages and the dropout of apprentices."],
    "law": ["Regularization of Contracts", "1 Introduction",
            "Regularization of informal contracts by the state is discussed. Attention to precedent and the training of judges matter.",
            "2 Method", "We read cases on the probability of appeal."],
    "chemistry": ["Gradient Elution of Peptides", "1 Introduction",
                  "Peptides are separated by gradient elution. The attention of the analyst, the optimization of the column and the probability of co-elution matter.",
                  "2 Method", "We fit a regression model of retention time."],
})
POSITIVE_CONTROLS = {
    "ml-short": ["Fine-Tuning a Transformer Language Model", "1 Introduction",
                 "We fine-tune a pre-trained transformer model with the Adam optimizer and stochastic gradient descent on the training set.",
                 "Self-attention layers and softmax outputs are trained with the cross-entropy loss and a small learning rate.",
                 "2 Method", "Backpropagation updates the parameters of the neural network, and dropout reduces overfitting."],
}
