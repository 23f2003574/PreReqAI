from backend.models import (
    Paper,
    Prerequisite,
)


class PrerequisiteDetector:
    """
    Identifies prerequisite concepts required
    to understand a research paper.

    The initial implementation uses deterministic
    rules derived from the detected concepts.
    """

    PREREQUISITE_RULES = {

        "Transformer": [
            "Attention",
            "Neural Networks",
        ],

        "Multi-Head Attention": [
            "Attention",
            "Linear Algebra",
        ],

        "Attention": [
            "Linear Algebra",
            "Probability",
        ],

        "Softmax": [
            "Probability",
        ],

        "Graph Neural Network": [
            "Graphs",
            "Neural Networks",
        ],

        "Policy Gradient": [
            "Markov Decision Process",
            "Probability",
            "Calculus",
        ],

        "Self-Attention": [
            "Attention",
            "Linear Algebra",
        ],

        "Diffusion Model": [
            "Probability",
            "Information Theory",
            "Neural Networks",
        ],

        "Information Theory": [
            "Probability",
        ],

        "Forward Process": [
            "Probability",
        ],

        "Noise Schedule": [
            "Probability",
        ],

        "Score Matching": [
            "Probability",
            "Information Theory",
            "Neural Networks",
            "Calculus",
        ],

        "U-Net": [
            "Neural Networks",
        ],

        "Cross-Attention": [
            "Attention",
            "Linear Algebra",
        ],

        "Positional Encoding": [
            "Linear Algebra",
        ],

        "Layer Normalization": [
            "Neural Networks",
            "Probability",
        ],

        "Residual Connection": [
            "Neural Networks",
        ],

        "Feed Forward Network": [
            "Neural Networks",
            "Linear Algebra",
        ],

        "Gradient Descent": [
            "Calculus",
            "Linear Algebra",
        ],

        "Backpropagation": [
            "Calculus",
            "Neural Networks",
        ],

        "Convolutional Neural Network": [
            "Neural Networks",
            "Linear Algebra",
        ],

        "Batch Normalization": [
            "Neural Networks",
            "Probability",
        ],

        "Dropout": [
            "Neural Networks",
            "Probability",
        ],

        "Recurrent Neural Network": [
            "Neural Networks",
            "Calculus",
        ],

        "Variational Inference": [
            "Probability",
            "Information Theory",
            "Calculus",
        ],

        "Adam Optimizer": [
            "Calculus",
            "Probability",
            "Neural Networks",
        ],

        "Reverse Process": [
            "Probability",
            "Information Theory",
            "Neural Networks",
            "Calculus",
        ],

        "Markov Decision Process": [
            "Probability",
        ],

        "Bellman Equation": [
            "Markov Decision Process",
            "Probability",
        ],

        "Value Function": [
            "Markov Decision Process",
        ],

        "Q-Learning": [
            "Markov Decision Process",
            "Probability",
        ],

        "Actor-Critic": [
            "Markov Decision Process",
            "Neural Networks",
            "Calculus",
        ],

        "Message Passing": [
            "Graphs",
            "Neural Networks",
        ],

        "Graph Convolution": [
            "Graphs",
            "Linear Algebra",
        ],

        "Graph Attention Network": [
            "Graphs",
            "Attention",
        ],

        "Node Embedding": [
            "Graphs",
            "Linear Algebra",
        ],
    }

    def detect(
        self,
        paper: Paper,
    ) -> Paper:

        paper.prerequisites.clear()

        # A prerequisite needed by several concepts is listed once, and its reason names every concept that
        # needs it (not only the first one found), so the learner sees how much of the paper depends on it.
        needed_by = {}

        for concept in paper.concepts:

            for prerequisite in self.PREREQUISITE_RULES.get(
                concept.name,
                [],
            ):

                needed_by.setdefault(prerequisite, []).append(concept.name)

        # A prerequisite the paper does not discuss may itself need others (a graph attention paper needs Attention,
        # which needs Probability): the learner must study those too, or the plan would send them to a course that
        # assumes knowledge the plan never covers. Only prerequisites not already listed are added this way.
        direct = list(needed_by)
        for prerequisite in direct:
            pending, seen = list(self.PREREQUISITE_RULES.get(prerequisite, [])), {prerequisite}
            while pending:
                deeper = pending.pop(0)
                if deeper in seen:
                    continue
                seen.add(deeper)
                if deeper not in direct:
                    for concept in needed_by[prerequisite]:
                        if concept not in needed_by.setdefault(deeper, []):
                            needed_by[deeper].append(concept)
                pending.extend(self.PREREQUISITE_RULES.get(deeper, []))
        for prerequisite, concepts in needed_by.items():

            paper.prerequisites.append(

                Prerequisite(

                    concept=prerequisite,

                    reason=(
                        f"Required to understand "
                        f"{', '.join(concepts)}"
                    ),

                    confidence=1.0,
                )
            )

        return paper
