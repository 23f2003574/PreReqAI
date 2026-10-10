from abc import ABC, abstractmethod

from .research_source_detector import (
    ResearchSource,
)


class BaseSourceResolver(ABC):
    """
    Base interface for all research source
    resolvers.
    """

    @abstractmethod
    def resolve(
        self,
        source: ResearchSource,
    ) -> str:
        """
        Returns the path to a local PDF.
        """
