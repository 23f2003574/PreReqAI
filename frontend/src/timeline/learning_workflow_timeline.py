from .timeline_step import (
    TimelineStep,
)

from .timeline_step_status import (
    TimelineStepStatus,
)


class LearningWorkflowTimeline:
    """
    Represents and tracks the visual
    progress of an educational workflow.
    """

    def __init__(self):

        self.steps: list[
            TimelineStep
        ] = []

        self.active_step_id = None

    def load(

        self,

        workflow_steps,

    ):

        self.steps = [

            TimelineStep(

                id=self._step_id(

                    step,

                    index,
                ),

                title=self._step_title(
                    step
                ),

                source=step,
            )

            for index, step

            in enumerate(
                workflow_steps
            )
        ]

        self.active_step_id = None

        return self.steps

    def activate(

        self,

        step_id: str,

    ):

        selected = None

        for step in self.steps:

            if step.id == step_id:

                step.status = (
                    TimelineStepStatus.ACTIVE
                )

                selected = step

            elif (

                step.status

                == TimelineStepStatus.ACTIVE
            ):

                step.status = (
                    TimelineStepStatus.PENDING
                )

        self.active_step_id = (

            step_id

            if selected

            else None
        )

        return selected

    def complete(

        self,

        step_id: str,

    ):

        step = self.get(
            step_id
        )

        if step is None:

            return None

        step.status = (
            TimelineStepStatus.COMPLETED
        )

        if (

            self.active_step_id

            == step_id
        ):

            self.active_step_id = None

        return step

    def fail(

        self,

        step_id: str,

    ):

        step = self.get(
            step_id
        )

        if step is None:

            return None

        step.status = (
            TimelineStepStatus.FAILED
        )

        if (

            self.active_step_id

            == step_id
        ):

            self.active_step_id = None

        return step

    def skip(

        self,

        step_id: str,

    ):

        step = self.get(
            step_id
        )

        if step is None:

            return None

        step.status = (
            TimelineStepStatus.SKIPPED
        )

        if (

            self.active_step_id

            == step_id
        ):

            self.active_step_id = None

        return step

    def get(

        self,

        step_id: str,

    ):

        return next(

            (

                step

                for step in self.steps

                if step.id == step_id
            ),

            None,
        )

    @staticmethod
    def _step_id(

        step,

        index: int,

    ):

        return str(

            getattr(

                step,

                "id",

                f"step-{index + 1}",
            )
        )

    @staticmethod
    def _step_title(step):

        if isinstance(step, str):

            return step

        title = getattr(

            step,

            "title",

            None,
        )

        if (

            title is not None

            and not callable(title)
        ):

            return str(title)

        return str(

            getattr(

                step,

                "value",

                step,
            )
        )
