from collections import (
    deque,
)

from .research_session_lineage_node import (
    ResearchSessionLineageNode,
)

from .research_session_lineage_path import (
    ResearchSessionLineagePath,
)

from .research_session_lineage_summary import (
    ResearchSessionLineageSummary,
)


class ResearchSessionLineageService:
    """
    Provides graph traversal and
    relationship queries over research
    session branch records.
    """

    def __init__(

        self,

        branch_store,

    ):

        self.branch_store = (
            branch_store
        )

    def parent_session_id(

        self,

        session_id: str,

    ) -> str | None:

        origin = (

            self.branch_store
            .get_by_branch_session(

                session_id
            )
        )

        if origin is None:

            return None

        return (
            origin.source_session_id
        )

    def child_session_ids(

        self,

        session_id: str,

    ) -> list[str]:

        branches = (

            self.branch_store
            .list_from_session(

                session_id
            )
        )

        return [

            branch.branch_session_id

            for branch

            in branches
        ]

    def ancestor_session_ids(

        self,

        session_id: str,

    ) -> list[str]:

        ancestors = []

        visited = {
            session_id
        }

        current_session_id = (
            session_id
        )

        while True:

            parent = (

                self.parent_session_id(

                    current_session_id
                )
            )

            if parent is None:

                break

            if parent in visited:

                raise ValueError(

                    "Cycle detected in research "
                    "session lineage while "
                    "traversing ancestors"
                )

            visited.add(
                parent
            )

            ancestors.append(
                parent
            )

            current_session_id = (
                parent
            )

        return ancestors

    def root_session_id(

        self,

        session_id: str,

    ) -> str:

        ancestors = (

            self.ancestor_session_ids(

                session_id
            )
        )

        if not ancestors:

            return session_id

        return ancestors[-1]

    def depth(

        self,

        session_id: str,

    ) -> int:

        return len(

            self.ancestor_session_ids(

                session_id
            )
        )

    def path_from_root(

        self,

        session_id: str,

    ) -> ResearchSessionLineagePath:

        ancestors = (

            self.ancestor_session_ids(

                session_id
            )
        )

        session_ids = (

            list(
                reversed(
                    ancestors
                )
            )

            + [
                session_id
            ]
        )

        return (

            ResearchSessionLineagePath(

                session_ids=(
                    session_ids
                )
            )
        )

    def descendant_session_ids(

        self,

        session_id: str,

    ) -> list[str]:

        descendants = []

        visited = {
            session_id
        }

        queue = deque(

            self.child_session_ids(

                session_id
            )
        )

        while queue:

            current = (
                queue.popleft()
            )

            if current in visited:

                raise ValueError(

                    "Cycle detected in research "
                    "session lineage while "
                    "traversing descendants"
                )

            visited.add(
                current
            )

            descendants.append(
                current
            )

            queue.extend(

                self.child_session_ids(

                    current
                )
            )

        return descendants

    def are_related(

        self,

        first_session_id: str,

        second_session_id: str,

    ) -> bool:

        return (

            self.root_session_id(

                first_session_id
            )

            ==

            self.root_session_id(

                second_session_id
            )
        )

    def is_ancestor(

        self,

        ancestor_session_id: str,

        descendant_session_id: str,

    ) -> bool:

        return (

            ancestor_session_id

            in self.ancestor_session_ids(

                descendant_session_id
            )
        )

    def is_descendant(

        self,

        descendant_session_id: str,

        ancestor_session_id: str,

    ) -> bool:

        return self.is_ancestor(

            ancestor_session_id=(
                ancestor_session_id
            ),

            descendant_session_id=(
                descendant_session_id
            ),
        )

    def lowest_common_ancestor(

        self,

        first_session_id: str,

        second_session_id: str,

    ) -> str | None:

        first_path = (

            self.path_from_root(

                first_session_id
            )
            .session_ids
        )

        second_path = (

            self.path_from_root(

                second_session_id
            )
            .session_ids
        )

        common = None

        for first, second in zip(

            first_path,

            second_path,
        ):

            if first != second:

                break

            common = first

        return common

    def path_between(

        self,

        first_session_id: str,

        second_session_id: str,

    ) -> ResearchSessionLineagePath | None:

        common = (

            self.lowest_common_ancestor(

                first_session_id,

                second_session_id,
            )
        )

        if common is None:

            return None

        first_path = (

            self.path_from_root(

                first_session_id
            )
            .session_ids
        )

        second_path = (

            self.path_from_root(

                second_session_id
            )
            .session_ids
        )

        first_common_index = (

            first_path.index(
                common
            )
        )

        second_common_index = (

            second_path.index(
                common
            )
        )

        upward = list(

            reversed(

                first_path[

                    first_common_index
                    + 1:
                ]
            )
        )

        downward = (

            second_path[

                second_common_index:
            ]
        )

        return (

            ResearchSessionLineagePath(

                session_ids=(

                    upward

                    + downward
                )
            )
        )

    def build_tree(

        self,

        root_session_id: str,

    ) -> ResearchSessionLineageNode:

        return self._build_node(

            session_id=(
                root_session_id
            ),

            depth=0,

            visited=set(),
        )

    def _build_node(

        self,

        session_id: str,

        depth: int,

        visited: set[str],

    ):

        if session_id in visited:

            raise ValueError(

                "Cycle detected in research "
                "session lineage while "
                "building tree"
            )

        visited.add(
            session_id
        )

        origin = (

            self.branch_store
            .get_by_branch_session(

                session_id
            )
        )

        node = (

            ResearchSessionLineageNode(

                session_id=(
                    session_id
                ),

                parent_session_id=(

                    origin.source_session_id

                    if origin

                    else None
                ),

                source_checkpoint_id=(

                    origin.source_checkpoint_id

                    if origin

                    else None
                ),

                source_version_id=(

                    origin.source_version_id

                    if origin

                    else None
                ),

                branch_id=(

                    origin.id

                    if origin

                    else None
                ),

                depth=depth,
            )
        )

        for child_session_id in (

            self.child_session_ids(

                session_id
            )
        ):

            child = self._build_node(

                session_id=(
                    child_session_id
                ),

                depth=(
                    depth + 1
                ),

                visited=visited,
            )

            node.children.append(
                child
            )

        return node

    def lineage_tree(

        self,

        session_id: str,

    ) -> ResearchSessionLineageNode:

        root = (

            self.root_session_id(

                session_id
            )
        )

        return self.build_tree(
            root
        )

    def summarize(

        self,

        session_id: str,

    ) -> ResearchSessionLineageSummary:

        ancestors = (

            self.ancestor_session_ids(

                session_id
            )
        )

        children = (

            self.child_session_ids(

                session_id
            )
        )

        descendants = (

            self.descendant_session_ids(

                session_id
            )
        )

        return (

            ResearchSessionLineageSummary(

                session_id=(
                    session_id
                ),

                root_session_id=(

                    ancestors[-1]

                    if ancestors

                    else session_id
                ),

                parent_session_id=(

                    ancestors[0]

                    if ancestors

                    else None
                ),

                depth=(
                    len(
                        ancestors
                    )
                ),

                ancestor_count=(
                    len(
                        ancestors
                    )
                ),

                child_count=(
                    len(
                        children
                    )
                ),

                descendant_count=(
                    len(
                        descendants
                    )
                ),
            )
        )
