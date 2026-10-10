from .paper_outline import (
    PaperOutline,
)

from .paper_outline_node import (
    PaperOutlineNode,
)


class PaperOutlineExplorer:
    """
    Builds and navigates a hierarchical
    research paper outline.
    """

    def __init__(self):

        self.outline = None

        self.selected_node = None

    def build(

        self,

        paper_title: str,

        sections,

    ) -> PaperOutline:

        roots = []

        stack = []

        for section in sections:

            node = PaperOutlineNode(

                id=section.id,

                title=section.title,

                level=section.level,

                section_number=getattr(

                    section,

                    "section_number",

                    None,
                ),

                page=getattr(

                    section,

                    "page",

                    None,
                ),

                source=section,
            )

            while (

                stack

                and stack[-1].level

                >= node.level
            ):

                stack.pop()

            if stack:

                stack[-1].children.append(
                    node
                )

            else:

                roots.append(
                    node
                )

            stack.append(
                node
            )

        self.outline = PaperOutline(

            paper_title=paper_title,

            roots=roots,
        )

        return self.outline

    def select(

        self,

        node: PaperOutlineNode,

    ):

        self.selected_node = node

        return node.source
