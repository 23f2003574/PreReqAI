from typing import (
    Mapping,
    Protocol,
)


class ResearchWorkspaceConsumerProjectionFingerprintPolicy(
    Protocol,
):
    """
    Protocol for projection-specific fingerprinting policies.

    A fingerprinting policy encodes:
    - Which sections are semantically meaningful
    - How each section should be normalized
    - Which fields to include/exclude
    - Whether ordering is meaningful

    Each projection type should have its own policy
    that understands consumer semantics specific to that projection.

    For example:
    - Bootstrap may have sections: readiness, attention, actions, insights
    - Attention may have sections: items
    - Actions may have sections: actions (with priority order preserved)
    """

    @property
    def projection_name(
        self,
    ) -> str:
        """
        Returns the stable projection identifier
        this policy applies to.

        Examples:
        - "workspace.bootstrap"
        - "workspace.attention"
        - "workspace.actions"
        """
        ...

    def extract_sections(
        self,
        projection: object,
    ) -> Mapping[str, object]:
        """
        Extracts the semantic sections
        from a consumer projection.

        Returns a mapping where:
        - Keys are stable section names
        - Values are the section content (may be any object)

        This method decides:
        - Which fields belong to the fingerprint
        - What to call each section
        - Which content to exclude

        For example, from a bootstrap projection:
        {
            "readiness": readiness_object,
            "attention": attention_object,
            "actions": actions_object,
        }

        Arguments:
            projection: The consumer projection to extract sections from

        Returns:
            Mapping of semantic section names to their content
        """
        ...

    def normalize_section(
        self,
        *,
        section_name: str,
        value: object,
    ) -> object:
        """
        Normalizes a section's content to
        a canonical semantic representation.

        This method can:
        - Sort unordered collections if appropriate
        - Exclude non-semantic fields
        - Transform values to canonical forms
        - Validate that the section is supported

        For example, if a section contains
        a set of action codes, this might
        normalize them to a sorted tuple.

        But if a section contains
        a prioritized action list,
        this preserves the ordering.

        Arguments:
            section_name: The section being normalized
            value: The section value from extract_sections

        Returns:
            A normalized representation suitable for canonicalization
        """
        ...
