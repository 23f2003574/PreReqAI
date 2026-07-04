from dataclasses import dataclass


@dataclass
class DetectedConcept:

    name: str

    domain: str

    occurrences: int = 0
