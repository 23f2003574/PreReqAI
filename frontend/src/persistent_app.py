from pathlib import Path

from backend.session import (

    ResearchPersistenceConfig,

    ResearchPersistenceFactory,
)

from .app import (
    PreReqAIApplication,
)


def create_persistent_application(

    data_directory:
        str | Path = ".prereqai",

):

    config = ResearchPersistenceConfig(

        root_directory=Path(
            data_directory
        )
    )

    stores = (

        ResearchPersistenceFactory
        .create(

            config
        )
    )

    return PreReqAIApplication(

        session_store=(

            stores[
                "session_store"
            ]
        ),

        artifact_store=(

            stores[
                "artifact_store"
            ]
        ),

        interaction_link_store=(

            stores[
                "interaction_link_store"
            ]
        ),

        checkpoint_store=(

            stores[
                "checkpoint_store"
            ]
        ),

        session_version_store=(

            stores[
                "session_version_store"
            ]
        ),

        checkpoint_annotation_store=(

            stores[
                "checkpoint_annotation_store"
            ]
        ),

        session_branch_store=(

            stores[
                "session_branch_store"
            ]
        ),

        session_profile_store=(

            stores[
                "session_profile_store"
            ]
        ),
    )
