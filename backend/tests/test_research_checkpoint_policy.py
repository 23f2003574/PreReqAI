from backend.session import (

    ResearchCheckpointPolicy,

    ResearchCheckpointReason,
)


def test_manual_checkpoint_is_always_allowed():

    policy = (

        ResearchCheckpointPolicy(

            enabled_reasons=[]
        )
    )

    assert (

        policy.should_checkpoint(

            ResearchCheckpointReason
            .MANUAL
        )

        is True
    )


def test_disabled_reason_is_rejected():

    policy = (

        ResearchCheckpointPolicy(

            enabled_reasons=[]
        )
    )

    assert (

        policy.should_checkpoint(

            ResearchCheckpointReason
            .ARTIFACT_CREATED
        )

        is False
    )


def test_default_policy_allows_artifact_created():

    policy = (
        ResearchCheckpointPolicy()
    )

    assert (

        policy.should_checkpoint(

            ResearchCheckpointReason
            .ARTIFACT_CREATED
        )

        is True
    )
