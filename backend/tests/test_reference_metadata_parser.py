from backend.navigation import ReferenceMetadataParser


def test_parses_authors_title_venue_year_when_cleanly_split():

    parser = ReferenceMetadataParser()

    result = parser.parse(
        "Dzmitry Bahdanau, Kyunghyun Cho, and Yoshua Bengio. "
        "Neural machine translation by jointly learning to align and translate. "
        "CoRR, abs/1409.0473, 2014."
    )

    assert result["authors"] == [
        "Dzmitry Bahdanau",
        "Kyunghyun Cho",
        "Yoshua Bengio",
    ]
    assert (
        result["title"]
        == "Neural machine translation by jointly learning to align and translate"
    )
    assert result["venue"] == "CoRR, abs/1409.0473, 2014."
    assert result["year"] == 2014


def test_degrades_gracefully_on_truncated_entry():

    parser = ReferenceMetadataParser()

    result = parser.parse("Alex Graves.")

    assert result["title"] == ""
    assert result["venue"] == ""
    assert result["year"] is None
