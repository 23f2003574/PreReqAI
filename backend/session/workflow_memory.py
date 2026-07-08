from dataclasses import dataclass, field

from .workflow_type import (
    WorkflowType,
)


@dataclass
class WorkflowRecord:

    workflow: WorkflowType

    concept: str

    completed: bool = True


@dataclass
class WorkflowMemory:
    """
    Defined here (not in backend.workflows) because backend.workflows'
    own modules (e.g. ExplanationWorkflow) import from backend.session,
    and LearningSession needs this type — sourcing it here avoids a
    circular import back into backend.workflows.
    """

    completed_workflows: list[
        WorkflowRecord
    ] = field(
        default_factory=list,
    )

    def add(

        self,

        workflow: WorkflowType,

        concept: str,

    ):

        self.completed_workflows.append(

            WorkflowRecord(

                workflow=workflow,

                concept=concept,
            )
        )

    def has_completed(

        self,

        workflow: WorkflowType,

        concept: str,

    ) -> bool:

        return any(

            record.workflow == workflow

            and record.concept == concept

            for record
            in self.completed_workflows

        )
