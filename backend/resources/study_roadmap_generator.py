from backend.models import (
    Paper,
    RoadmapStep,
)


class StudyRoadmapGenerator:
    """
    Builds a sequential roadmap by combining
    prerequisite ordering with curated learning
    resources.
    """

    def generate(
        self,
        paper: Paper,
    ) -> Paper:

        paper.study_roadmap.clear()

        resources = {
            resource.concept: resource
            for resource in paper.learning_resources
        }

        step = 1

        for learning_step in paper.learning_plan:

            resource = resources.get(
                learning_step.concept
            )

            if resource is None:
                continue

            paper.study_roadmap.append(

                RoadmapStep(

                    step=step,

                    concept=learning_step.concept,

                    resource_title=resource.title,

                    provider=resource.provider,

                    estimated_hours=resource.estimated_hours,
                )
            )

            step += 1

        return paper
