import logging

from backend.models import (
    Paper,
    Prerequisite,
)


logger = logging.getLogger("prereqai.prerequisites")


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

        "Reinforcement Learning": [
            "Probability",
            "Calculus",
        ],

        "Large Language Model": [
            "Neural Networks",
            "Linear Algebra",
            "Probability",
        ],

        "Cross-Entropy Loss": [
            "Probability",
            "Information Theory",
        ],

        "Maximum Likelihood Estimation": [
            "Probability",
            "Calculus",
        ],

        "Overfitting": [
            "Probability",
            "Neural Networks",
        ],

        "Embedding": [
            "Linear Algebra",
            "Neural Networks",
        ],

        "Fine-Tuning": [
            "Neural Networks",
            "Calculus",
        ],

        "Monte Carlo Method": [
            "Probability",
            "Calculus",
        ],

        "Variational Autoencoder": [
            "Neural Networks",
            "Probability",
            "Information Theory",
        ],

        "Generative Adversarial Network": [
            "Neural Networks",
            "Probability",
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

        "Parameter-Efficient Fine-Tuning": [
            "Neural Networks",
            "Linear Algebra",
        ],

        "LoRA": [
            "Linear Algebra",
            "Neural Networks",
        ],

        "Reinforcement Learning from Human Feedback": [
            "Markov Decision Process",
            "Probability",
            "Neural Networks",
        ],

        "Proximal Policy Optimization": [
            "Markov Decision Process",
            "Probability",
            "Calculus",
        ],

        "Contrastive Learning": [
            "Neural Networks",
            "Probability",
            "Information Theory",
        ],

        "Tokenization": [
            "Probability",
        ],

        "Vision Transformer": [
            "Transformer",
            "Linear Algebra",
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

        paper.concepts_without_rules = [
            concept.name for concept in paper.concepts if concept.name not in self.PREREQUISITE_RULES
        ]

        if paper.concepts_without_rules:

            logger.warning(
                "no prerequisite rule for detected concepts (their prerequisites are unknown, not absent): %s",
                ", ".join(paper.concepts_without_rules),
            )

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
        # Importance comes only from dependency evidence, with no tuned weights. `confidence` is the share of the paper's
        # rule-bearing concepts (those with at least one prerequisite) that need the prerequisite, directly or through
        # another prerequisite: a measured fraction, not a certainty. A prerequisite needed by at least half of them
        # (dependents * 2 >= total) is "essential", otherwise "supporting". The mentions of the dependent concepts break
        # ties when ranking (see rank_prerequisites); the list itself keeps the rule order.
        occurrences = {concept.name: concept.occurrences for concept in paper.concepts}
        total = sum(1 for concept in paper.concepts if self.PREREQUISITE_RULES.get(concept.name))

        for prerequisite, concepts in needed_by.items():

            share = len(concepts) / total if total else 0.0
            essential = bool(total) and len(concepts) * 2 >= total
            mentions = sum(occurrences.get(name, 0) for name in concepts)

            paper.prerequisites.append(

                Prerequisite(

                    concept=prerequisite,

                    reason=(
                        f"Required to understand "
                        f"{', '.join(concepts)}"
                    ),

                    confidence=round(share, 2),

                    importance="essential" if essential else "supporting",

                    importance_reason=(
                        f"Needed by {len(concepts)} of the paper's {total} concepts that have prerequisites "
                        f"({mentions} mentions): {'essential' if essential else 'supporting'}."
                    ),

                    dependent_mentions=mentions,
                )
            )

        return paper


def rank_prerequisites(prerequisites):
    """Prerequisites most-needed first: by number of dependent concepts (taken from the reason), then by the mentions of those
    concepts, then by name, so equal evidence always ranks the same way."""
    return sorted(prerequisites, key=lambda p: (-(p.reason.count(",") + 1), -p.dependent_mentions, p.concept))
