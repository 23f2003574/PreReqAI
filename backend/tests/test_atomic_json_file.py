import pytest

from backend.storage import (
    AtomicJsonFile,
)


def test_reads_default_when_file_missing(

    tmp_path,

):

    file = AtomicJsonFile(

        tmp_path / "data.json",

        default_factory=dict,
    )

    assert file.read() == {}


def test_writes_and_reads_json(

    tmp_path,

):

    file = AtomicJsonFile(

        tmp_path / "data.json",

        default_factory=dict,
    )

    file.write(

        {

            "session": "session-1"
        }
    )

    assert (

        file.read()

        == {

            "session": "session-1"
        }
    )


def test_reports_corrupted_json(

    tmp_path,

):

    path = (

        tmp_path

        / "data.json"
    )

    path.write_text(

        "{broken-json",

        encoding="utf-8",
    )

    file = AtomicJsonFile(

        path,

        default_factory=dict,
    )

    with pytest.raises(

        ValueError,

        match=(

            "Could not read JSON "
            "persistence file"
        ),
    ):

        file.read()
