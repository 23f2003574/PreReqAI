import json

import os

from json import JSONDecodeError

from pathlib import Path

from tempfile import NamedTemporaryFile

from threading import RLock

from typing import Any


class AtomicJsonFile:
    """
    Provides thread-safe JSON file
    reading and atomic replacement.
    """

    def __init__(

        self,

        path: str | Path,

        default_factory,

    ):

        self.path = Path(
            path
        )

        self.default_factory = (
            default_factory
        )

        self._lock = RLock()

    def read(self) -> Any:

        with self._lock:

            if not self.path.exists():

                return (
                    self.default_factory()
                )

            try:

                with self.path.open(

                    "r",

                    encoding="utf-8",

                ) as file:

                    return json.load(
                        file
                    )

            except JSONDecodeError as error:

                raise ValueError(

                    "Could not read JSON "
                    "persistence file: "
                    f"{self.path}"
                ) from error

    def write(

        self,

        data: Any,

    ) -> None:

        with self._lock:

            self.path.parent.mkdir(

                parents=True,

                exist_ok=True,
            )

            temporary_path = None

            try:

                with NamedTemporaryFile(

                    mode="w",

                    encoding="utf-8",

                    dir=self.path.parent,

                    prefix=(

                        f".{self.path.name}."
                    ),

                    suffix=".tmp",

                    delete=False,

                ) as temporary_file:

                    temporary_path = Path(

                        temporary_file.name
                    )

                    json.dump(

                        data,

                        temporary_file,

                        ensure_ascii=False,

                        indent=2,
                    )

                    temporary_file.flush()

                    os.fsync(

                        temporary_file
                        .fileno()
                    )

                os.replace(

                    temporary_path,

                    self.path,
                )

            finally:

                if (

                    temporary_path
                    is not None

                    and

                    temporary_path.exists()
                ):

                    temporary_path.unlink()
