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


class PDFResolver(BaseSourceResolver):

    def resolve(
        self,
        source: ResearchSource,
    ) -> str:

        return source.identifier


class ResearchSourceResolver:
    """
    Resolves supported research sources
    into local PDF files.
    """

    def __init__(self):

        self._resolvers = {
            "pdf": PDFResolver(),
        }

    def resolve(
        self,
        source: ResearchSource,
    ) -> str:

        resolver = self._resolvers.get(
            source.source_type,
        )

        if resolver is None:

            raise NotImplementedError(
                f"{source.source_type} resolution has not been implemented."
            )

        return resolver.resolve(source)
