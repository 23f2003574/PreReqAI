from dataclasses import dataclass

from backend.session import (
    ResearchRuntimeRegistry,
)


@dataclass
class ResearchObject:

    id: str


def test_registers_and_resolves_object():

    registry = (
        ResearchRuntimeRegistry()
    )

    research_object = (

        ResearchObject(

            id="attention"
        )
    )

    registry.register_object(

        research_object
    )

    resolved = registry.get_object(

        "attention"
    )

    assert (

        resolved

        is research_object
    )


def test_returns_none_for_unknown_object():

    registry = (
        ResearchRuntimeRegistry()
    )

    assert (

        registry.get_object(

            "missing"
        )

        is None
    )


def test_registers_objects_sections_and_graph_nodes_in_bulk():

    registry = (
        ResearchRuntimeRegistry()
    )

    objects = [

        ResearchObject(id="attention"),

        ResearchObject(id="transformer"),
    ]

    registry.register_objects(
        objects
    )

    assert (

        registry.get_object(
            "transformer"
        )

        is objects[1]
    )
