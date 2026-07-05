from dataclasses import dataclass

import requests


@dataclass
class PaperMetadata:

    title: str

    doi: str

    landing_page: str

    publisher: str


class ResearchMetadataResolver:
    """
    Resolves scholarly identifiers into
    canonical paper metadata.

    Current implementation supports DOI
    resolution using the Crossref API.
    """

    CROSSREF_API = "https://api.crossref.org/works/"

    def resolve_doi(
        self,
        doi: str,
    ) -> PaperMetadata:

        response = requests.get(
            self.CROSSREF_API + doi,
            timeout=30,
        )

        response.raise_for_status()

        message = response.json()["message"]

        title = ""

        if message.get("title"):
            title = message["title"][0]

        return PaperMetadata(

            title=title,

            doi=doi,

            landing_page=message.get("URL", ""),

            publisher=message.get(
                "publisher",
                "",
            ),
        )
