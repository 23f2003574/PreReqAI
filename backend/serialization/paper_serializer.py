from dataclasses import asdict

from backend.models import Paper


class PaperSerializer:
    """
    Serializes the complete Paper Object Model
    into a JSON-compatible dictionary.
    """

    def serialize(
        self,
        paper: Paper,
    ) -> dict:

        return asdict(paper)
