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
            12,
        ),

        "Probability": (
            "Khan Academy Probability",
            "Khan Academy",
            "https://www.khanacademy.org/math/statistics-probability",
            10,
        ),

        "Neural Networks": (
            "Neural Networks and Deep Learning",
            "Coursera",
            "https://www.coursera.org/learn/neural-networks-deep-learning",
            15,
        ),

        "Attention": (
            "The Illustrated Transformer",
            "Jay Alammar",
            "https://jalammar.github.io/illustrated-transformer/",
            3,
        ),

        "Transformer": (
            "Attention Is All You Need (Annotated)",
            "The Annotated Transformer",
            "https://nlp.seas.harvard.edu/annotated-transformer/",
            4,
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
