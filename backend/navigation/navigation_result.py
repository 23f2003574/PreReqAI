from dataclasses import dataclass, field


@dataclass
class NavigationResult:
    """
    Represents the destination reached
    after navigating through the paper.
    """

    target: str

    title: str

    summary: str

    metadata: dict = field(
        default_factory=dict,
    )
