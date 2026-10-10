import hashlib
import json

from typing import (
    Optional,
)

from .research_workspace_consumer_projection_canonicalizer import (
    ResearchWorkspaceConsumerProjectionCanonicalizer,
)

from .research_workspace_consumer_projection_fingerprint import (
    ResearchWorkspaceConsumerProjectionFingerprint,
)

from .research_workspace_consumer_projection_fingerprint_algorithm import (
    ResearchWorkspaceConsumerProjectionFingerprintAlgorithm,
)

from .research_workspace_consumer_projection_fingerprint_policy import (
    ResearchWorkspaceConsumerProjectionFingerprintPolicy,
)

from .research_workspace_consumer_projection_fingerprint_snapshot import (
    ResearchWorkspaceConsumerProjectionFingerprintSnapshot,
)

from .research_workspace_consumer_projection_section_fingerprint import (
    ResearchWorkspaceConsumerProjectionSectionFingerprint,
)


class ResearchWorkspaceConsumerProjectionFingerprintService:
    """
    Service for computing stable deterministic fingerprints
    of consumer projections.

    Orchestrates the fingerprinting pipeline:
    1. Extract semantic sections via policy
    2. Normalize each section via policy
    3. Canonicalize normalized values
    4. Deterministically serialize to JSON
    5. Compute section fingerprints (SHA-256)
    6. Compute overall fingerprint from section fingerprints
    7. Build immutable fingerprint snapshot

    The resulting fingerprint uniquely identifies
    the consumer-meaningful state, excluding:
    - Request timestamps
    - Diagnostics metadata
    - Provenance node IDs
    - Execution duration
    - Dictionary key ordering
    """

    def __init__(
        self,
    ):
        self._canonicalizer = (
            ResearchWorkspaceConsumerProjectionCanonicalizer()
        )

    def fingerprint(
        self,
        *,
        projection: object,
        policy: (
            ResearchWorkspaceConsumerProjectionFingerprintPolicy
        ),
        contract_version: Optional[str] = None,
    ) -> ResearchWorkspaceConsumerProjectionFingerprintSnapshot:
        """
        Computes the semantic fingerprint of a projection.

        Arguments:
            projection: The consumer projection to fingerprint
            policy: The projection-specific fingerprinting policy
            contract_version: Optional contract version identifier

        Returns:
            An immutable fingerprint snapshot

        Raises:
            Various canonicalization errors if semantic values
            cannot be converted to deterministic representations
        """

        # Step 1: Extract semantic sections
        sections_dict = policy.extract_sections(
            projection,
        )

        # Step 2 & 3: Normalize and canonicalize each section
        canonical_sections = {}

        for section_name, section_value in sections_dict.items():
            normalized = policy.normalize_section(
                section_name=section_name,
                value=section_value,
            )

            canonical = self._canonicalizer.canonicalize(
                normalized,
            )

            canonical_sections[section_name] = canonical

        # Step 4 & 5: Compute section fingerprints
        section_fingerprints = []

        for section_name in sorted(
            canonical_sections.keys()
        ):
            canonical_value = canonical_sections[
                section_name
            ]

            section_fingerprint = (
                self._compute_fingerprint(
                    canonical_value,
                )
            )

            section_fingerprints.append(
                ResearchWorkspaceConsumerProjectionSectionFingerprint(
                    section_name=section_name,
                    fingerprint=section_fingerprint,
                )
            )

        # Step 6: Compute overall fingerprint
        # Use the ordered section map to derive it
        overall_canonical = {
            fp.section_name: fp.fingerprint.value
            for fp in section_fingerprints
        }

        overall_fingerprint = self._compute_fingerprint(
            overall_canonical,
        )

        # Step 7: Build snapshot
        snapshot = (
            ResearchWorkspaceConsumerProjectionFingerprintSnapshot(
                projection_name=policy.projection_name,
                contract_version=contract_version,
                overall=overall_fingerprint,
                sections=tuple(section_fingerprints),
            )
        )

        return snapshot

    def _compute_fingerprint(
        self,
        canonical_value: object,
    ) -> ResearchWorkspaceConsumerProjectionFingerprint:
        """
        Computes a fingerprint of a canonical value
        using deterministic SHA-256 hashing.

        Arguments:
            canonical_value: A JSON-compatible primitive value

        Returns:
            A fingerprint with algorithm and hex digest
        """

        # Deterministically serialize
        serialized = self._serialize_canonical(
            canonical_value,
        )

        # Compute SHA-256
        digest = hashlib.sha256(
            serialized.encode('utf-8'),
        ).hexdigest()

        return ResearchWorkspaceConsumerProjectionFingerprint(
            algorithm=(
                ResearchWorkspaceConsumerProjectionFingerprintAlgorithm.SHA256
            ),
            value=digest,
        )

    def _serialize_canonical(
        self,
        value: object,
    ) -> str:
        """
        Deterministically serializes a canonical value to JSON.

        Uses:
        - Sorted keys for mappings
        - Stable separators
        - UTF-8 encoding
        - No pretty-printing
        """

        return json.dumps(
            value,
            sort_keys=True,
            separators=(',', ':'),
            ensure_ascii=False,
        )
