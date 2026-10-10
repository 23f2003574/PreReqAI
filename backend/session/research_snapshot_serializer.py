import json

from pathlib import (
    Path,
)

from .research_snapshot import (
    ResearchSnapshot,
)


class ResearchSnapshotSerializer:
    """
    Serializes and deserializes portable
    research snapshots as JSON.
    """

    def dumps(

        self,

        snapshot,

        indent=2,

    ):

        return json.dumps(

            snapshot.to_dict(),

            indent=indent,

            ensure_ascii=False,

            sort_keys=True,
        )

    def loads(

        self,

        payload,

    ):

        data = json.loads(
            payload
        )

        return (

            ResearchSnapshot
            .from_dict(
                data
            )
        )

    def write(

        self,

        snapshot,

        path,

    ):

        destination = Path(
            path
        )

        destination.parent.mkdir(

            parents=True,

            exist_ok=True,
        )

        temporary = (

            destination
            .with_suffix(

                destination.suffix

                + ".tmp"
            )
        )

        temporary.write_text(

            self.dumps(
                snapshot
            ),

            encoding=(
                "utf-8"
            ),
        )

        temporary.replace(
            destination
        )

        return destination

    def read(

        self,

        path,

    ):

        payload = (

            Path(
                path
            )
            .read_text(

                encoding=(
                    "utf-8"
                )
            )
        )

        return self.loads(
            payload
        )
