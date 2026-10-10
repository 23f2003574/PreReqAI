from .research_source_detector import (
    ResearchSource,
)

from .base_source_resolver import (
    BaseSourceResolver,
)

from .arxiv_resolver import (
    ArxivResolver,
)


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
            "arxiv": ArxivResolver(),
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
