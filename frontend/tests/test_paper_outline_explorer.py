from dataclasses import dataclass

from frontend.src.explorer import (
    PaperOutlineExplorer,
)


@dataclass
class Section:

    id: str

    title: str

    level: int

    section_number: str

    page: int


def test_builds_hierarchical_outline():

    explorer = (
        PaperOutlineExplorer()
    )

    sections = [

        Section(

            id="intro",

            title="Introduction",

            level=1,

            section_number="1",

            page=1,
        ),

        Section(

            id="background",

            title="Background",

            level=1,

            section_number="2",

            page=2,
        ),

        Section(

            id="attention",

            title="Attention",

            level=2,

            section_number="2.1",

            page=3,
        ),
    ]

    outline = explorer.build(

        "Example Paper",

        sections,
    )

    assert (

        len(outline.roots)

        == 2
    )

    assert (

        outline
        .roots[1]
        .children[0]
        .title

        == "Attention"
    )


def test_selects_outline_node():

    explorer = (
        PaperOutlineExplorer()
    )

    sections = [

        Section(

            id="intro",

            title="Introduction",

            level=1,

            section_number="1",

            page=1,
        ),
    ]

    outline = explorer.build(

        "Example Paper",

        sections,
    )

    selected = explorer.select(

        outline.roots[0]
    )

    assert (

        selected

        == sections[0]
    )
