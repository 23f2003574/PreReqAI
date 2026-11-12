from backend.prerequisites.prerequisite_learning_planner import PrerequisiteLearningPlanner
from backend.models import (
    Paper,
    LearningResource,
)


class LearningResourceRecommender:
    """
    Recommends curated learning resources
    for prerequisite concepts.
    """

    RESOURCE_LIBRARY = {

        "Linear Algebra": (
            "MIT 18.06 Linear Algebra",
            "MIT OpenCourseWare",
            "https://ocw.mit.edu/courses/18-06-linear-algebra-spring-2010/",
            PrerequisiteLearningPlanner.STUDY_TIME["Linear Algebra"],  # one source of study hours: the planner's
        ),

        "Probability": (
            "Khan Academy Probability",
            "Khan Academy",
            "https://www.khanacademy.org/math/statistics-probability",
            PrerequisiteLearningPlanner.STUDY_TIME["Probability"],  # one source of study hours: the planner's
        ),

        "Calculus": (
            "MIT 18.01 Single Variable Calculus",
            "MIT OpenCourseWare",
            "https://ocw.mit.edu/courses/18-01-single-variable-calculus-fall-2006/",
            PrerequisiteLearningPlanner.STUDY_TIME["Calculus"],  # one source of study hours: the planner's
        ),

        "Information Theory": (
            "Information Theory, Inference and Learning Algorithms",
            "David MacKay (University of Cambridge)",
            "https://www.inference.org.uk/mackay/itila/",
            PrerequisiteLearningPlanner.STUDY_TIME["Information Theory"],  # one source of study hours: the planner's
        ),

        "Neural Networks": (
            "Neural Networks and Deep Learning",
            "Coursera",
            "https://www.coursera.org/learn/neural-networks-deep-learning",
            PrerequisiteLearningPlanner.STUDY_TIME["Neural Networks"],  # one source of study hours: the planner's
        ),

        "Graphs": (
            "Machine Learning with Graphs (CS224W)",
            "Stanford University",
            "https://web.stanford.edu/class/cs224w/",
            PrerequisiteLearningPlanner.STUDY_TIME["Graphs"],  # one source of study hours: the planner's
        ),

        "Markov Decision Process": (
            "Introduction to Reinforcement Learning: Markov Decision Processes",
            "David Silver (UCL)",
            "https://www.davidsilver.uk/teaching/",
            PrerequisiteLearningPlanner.STUDY_TIME["Markov Decision Process"],  # one source of study hours: the planner's
        ),

        "Attention": (
            "The Illustrated Transformer",
            "Jay Alammar",
            "https://jalammar.github.io/illustrated-transformer/",
            PrerequisiteLearningPlanner.STUDY_TIME["Attention"],  # one source of study hours: the planner's
        ),

        "Transformer": (
            "Attention Is All You Need (Annotated)",
            "The Annotated Transformer",
            "https://nlp.seas.harvard.edu/annotated-transformer/",
            PrerequisiteLearningPlanner.STUDY_TIME["Transformer"],  # one source of study hours: the planner's
        ),
    }

    def recommend(
        self,
        paper: Paper,
    ) -> Paper:

        paper.learning_resources.clear()

        for prerequisite in paper.missing_prerequisites:

            if prerequisite.satisfied:
                continue

            resource = self.RESOURCE_LIBRARY.get(
                prerequisite.concept
            )

            if resource is None:
                continue

            title, provider, url, hours = resource

            paper.learning_resources.append(

                LearningResource(

                    concept=prerequisite.concept,

                    title=title,

                    provider=provider,

                    url=url,

                    estimated_hours=hours,
                )
            )

        return paper
