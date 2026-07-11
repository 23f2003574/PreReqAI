from frontend.src import (
    PreReqAIApplication,
)

from frontend.src.workspace import (
    VisualResearchWorkspace,
)


def test_application_creates_workspace():

    application = (
        PreReqAIApplication()
    )

    assert isinstance(

        application.workspace,

        VisualResearchWorkspace,
    )
