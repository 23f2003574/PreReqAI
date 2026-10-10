from backend.platform import (
    PreReqAIPlatform,
)


def test_platform():

    platform = (
        PreReqAIPlatform()
    )

    assert platform is not None


def test_platform_wires_every_subsystem():

    platform = (
        PreReqAIPlatform()
    )

    assert platform.analysis is not None

    assert platform.navigation is not None

    assert platform.interaction is not None

    assert platform.learning is not None
