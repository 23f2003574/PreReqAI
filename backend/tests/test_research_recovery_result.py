from datetime import datetime

from backend.session import (
    ResearchRecoveryResult,
)


def test_recovery_result_serializes():

    result = ResearchRecoveryResult(

        session_id="session-1",

        source_checkpoint_id=(
            "checkpoint-1"
        ),

        source_version_id=(
            "version-1"
        ),

        safety_checkpoint_id=(
            "checkpoint-2"
        ),

        recovery_checkpoint_id=(
            "checkpoint-3"
        ),

        recovered_at=(
            datetime.utcnow()
        ),
    )

    data = result.to_dict()

    assert (

        data[
            "source_checkpoint_id"
        ]

        == "checkpoint-1"
    )

    assert isinstance(

        data[
            "recovered_at"
        ],

        str,
    )
