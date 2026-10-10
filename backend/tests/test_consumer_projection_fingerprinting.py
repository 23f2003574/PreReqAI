"""
Comprehensive tests for consumer projection fingerprinting
and semantic change detection.

Tests cover:
- Canonicalization determinism
- Fingerprint generation and stability  
- Change detection
- Semantic vs execution differences
- Policy-specific behavior
- Immutability
"""

import pytest
from datetime import datetime, timezone, date
from enum import Enum

from backend.session.research_workspace_consumer_projection_canonicalizer import (
    ResearchWorkspaceConsumerProjectionCanonicalizer,
)

from backend.session.research_workspace_consumer_projection_fingerprint_service import (
    ResearchWorkspaceConsumerProjectionFingerprintService,
)

from backend.session.research_workspace_consumer_projection_fingerprint_algorithm import (
    ResearchWorkspaceConsumerProjectionFingerprintAlgorithm,
)

from backend.session.research_workspace_consumer_projection_change_detector import (
    ResearchWorkspaceConsumerProjectionChangeDetector,
)

from backend.session.research_workspace_consumer_projection_change_status import (
    ResearchWorkspaceConsumerProjectionChangeStatus,
)

from backend.session.research_workspace_consumer_projection_section_change_status import (
    ResearchWorkspaceConsumerProjectionSectionChangeStatus,
)

from backend.session.research_workspace_consumer_projection_fingerprint_policy_registry import (
    ResearchWorkspaceConsumerProjectionFingerprintPolicyRegistry,
)

from backend.session.research_workspace_consumer_projection_fingerprint_errors import (
    ResearchWorkspaceUnsupportedCanonicalValueError,
    ResearchWorkspaceNaiveDatetimeCanonicalizationError,
    ResearchWorkspaceProjectionFingerprintPolicyNotFoundError,
)


# Fixtures
@pytest.fixture
def canonicalizer():
    return ResearchWorkspaceConsumerProjectionCanonicalizer()


@pytest.fixture
def fingerprint_service():
    return ResearchWorkspaceConsumerProjectionFingerprintService()


@pytest.fixture
def change_detector():
    return ResearchWorkspaceConsumerProjectionChangeDetector()


@pytest.fixture
def policy_registry():
    return (
        ResearchWorkspaceConsumerProjectionFingerprintPolicyRegistry()
    )


# ============================================================================
# CANONICALIZATION TESTS
# ============================================================================

class TestCanonicalization:
    """Tests for deterministic value canonicalization."""

    def test_none_canonicalization(self, canonicalizer):
        """Test 1: Primitive None Canonicalization"""
        result = canonicalizer.canonicalize(None)
        assert result is None

    def test_boolean_canonicalization(self, canonicalizer):
        """Test 2: Boolean Canonicalization"""
        assert canonicalizer.canonicalize(True) is True
        assert canonicalizer.canonicalize(False) is False

    def test_integer_canonicalization(self, canonicalizer):
        """Test 3: Integer Canonicalization"""
        assert canonicalizer.canonicalize(0) == 0
        assert canonicalizer.canonicalize(42) == 42
        assert canonicalizer.canonicalize(-123) == -123

    def test_string_canonicalization(self, canonicalizer):
        """Test 4: String Canonicalization"""
        assert canonicalizer.canonicalize("hello") == "hello"
        assert canonicalizer.canonicalize("") == ""

    def test_enum_canonicalization(self, canonicalizer):
        """Test 5: Enum Canonicalization"""

        class TestEnum(str, Enum):
            STALE = "stale"
            FRESH = "fresh"

        result = canonicalizer.canonicalize(
            TestEnum.STALE
        )
        assert result == "stale"

    def test_mapping_key_order_normalization(
        self,
        canonicalizer,
    ):
        """Test 6: Mapping Key Order Does Not Affect Canonicalization"""
        result_1 = canonicalizer.canonicalize(
            {"a": 1, "b": 2}
        )
        result_2 = canonicalizer.canonicalize(
            {"b": 2, "a": 1}
        )

        assert result_1 == result_2

    def test_ordered_sequence_order_preserved(
        self,
        canonicalizer,
    ):
        """Test 7: Ordered Sequence Order Is Preserved"""
        result_1 = canonicalizer.canonicalize([1, 2])
        result_2 = canonicalizer.canonicalize([2, 1])

        assert result_1 != result_2

    def test_timezone_equivalent_datetimes(
        self,
        canonicalizer,
    ):
        """Test 9: Timezone-Equivalent Datetimes Canonicalize Identically"""

        utc_dt = datetime(
            2026,
            7,
            14,
            10,
            0,
            0,
            tzinfo=timezone.utc,
        )

        plus_530_offset = __import__(
            'datetime'
        ).timezone(
            __import__('datetime').timedelta(
                hours=5,
                minutes=30,
            ),
        )

        offset_dt = datetime(
            2026,
            7,
            14,
            15,
            30,
            0,
            tzinfo=plus_530_offset,
        )

        result_1 = canonicalizer.canonicalize(utc_dt)
        result_2 = canonicalizer.canonicalize(offset_dt)

        assert result_1 == result_2

    def test_naive_datetime_rejected(
        self,
        canonicalizer,
    ):
        """Test 10: Naive Datetime Is Rejected"""
        naive_dt = datetime(
            2026,
            7,
            14,
            10,
            0,
            0,
        )

        with pytest.raises(
            ResearchWorkspaceNaiveDatetimeCanonicalizationError
        ):
            canonicalizer.canonicalize(naive_dt)

    def test_non_finite_float_rejected(
        self,
        canonicalizer,
    ):
        """Test 11: Non-Finite Float Is Rejected"""

        with pytest.raises(
            ResearchWorkspaceUnsupportedCanonicalValueError
        ):
            canonicalizer.canonicalize(float('nan'))

        with pytest.raises(
            ResearchWorkspaceUnsupportedCanonicalValueError
        ):
            canonicalizer.canonicalize(float('inf'))

        with pytest.raises(
            ResearchWorkspaceUnsupportedCanonicalValueError
        ):
            canonicalizer.canonicalize(float('-inf'))

    def test_unsupported_object_type_rejected(
        self,
        canonicalizer,
    ):
        """Test 12: Unsupported Object Type Is Rejected"""

        class CustomObject:
            pass

        with pytest.raises(
            ResearchWorkspaceUnsupportedCanonicalValueError
        ):
            canonicalizer.canonicalize(
                CustomObject()
            )

    def test_date_canonicalization(self, canonicalizer):
        """Test: Date Canonicalization"""
        d = date(2026, 7, 14)
        result = canonicalizer.canonicalize(d)
        assert result == "2026-07-14"


# ============================================================================
# FINGERPRINT GENERATION TESTS
# ============================================================================

class TestFingerprintGeneration:
    """Tests for fingerprint generation and stability."""

    def _make_policy(self, value):
        """Helper to create mock policy."""
        return type(
            'MockPolicy',
            (),
            {
                'projection_name': (
                    'test.projection'
                ),
                'extract_sections': (
                    lambda self, proj: {
                        'data': value
                    }
                ),
                'normalize_section': (
                    lambda self, section_name, val: (
                        val
                    )
                ),
            },
        )()

    def test_same_canonical_produces_same_fingerprint(
        self,
        fingerprint_service,
    ):
        """Test 13: Same Canonical Value Produces Same Fingerprint"""
        value = {"name": "test", "count": 42}

        fp1 = fingerprint_service.fingerprint(
            projection=object(),
            policy=self._make_policy(value),
        )

        fp2 = fingerprint_service.fingerprint(
            projection=object(),
            policy=self._make_policy(value),
        )

        assert fp1.overall == fp2.overall

    def test_different_values_different_fingerprints(
        self,
        fingerprint_service,
    ):
        """Test 14: Different Semantic Values Produce Different Fingerprints"""

        fp1 = fingerprint_service.fingerprint(
            projection=object(),
            policy=self._make_policy("ready"),
        )

        fp2 = fingerprint_service.fingerprint(
            projection=object(),
            policy=self._make_policy("blocked"),
        )

        assert fp1.overall != fp2.overall

    def test_fingerprint_algorithm_recorded(
        self,
        fingerprint_service,
    ):
        """Test 15: Fingerprint Algorithm Is Recorded"""

        snapshot = fingerprint_service.fingerprint(
            projection=object(),
            policy=self._make_policy("test"),
        )

        assert (
            snapshot.overall.algorithm
            == ResearchWorkspaceConsumerProjectionFingerprintAlgorithm.SHA256
        )

    def test_fingerprint_lowercase_hexadecimal(
        self,
        fingerprint_service,
    ):
        """Test 16: Fingerprint Uses Lowercase Hexadecimal"""

        snapshot = fingerprint_service.fingerprint(
            projection=object(),
            policy=self._make_policy("test"),
        )

        # Should be lowercase hex
        assert all(
            c in '0123456789abcdef'
            for c in snapshot.overall.value
        )

    def test_projection_name_recorded(
        self,
        fingerprint_service,
    ):
        """Test: Projection Name Is Recorded in Snapshot"""
        snapshot = fingerprint_service.fingerprint(
            projection=object(),
            policy=self._make_policy("test"),
        )

        assert snapshot.projection_name == "test.projection"

    def test_contract_version_recorded(
        self,
        fingerprint_service,
    ):
        """Test: Contract Version Is Recorded When Provided"""
        snapshot = fingerprint_service.fingerprint(
            projection=object(),
            policy=self._make_policy("test"),
            contract_version="1.0",
        )

        assert snapshot.contract_version == "1.0"

    def test_section_fingerprints_ordered(
        self,
        fingerprint_service,
    ):
        """Test: Section Fingerprints Are Deterministically Ordered"""

        policy = type(
            'MockPolicy',
            (),
            {
                'projection_name': (
                    'test.projection'
                ),
                'extract_sections': (
                    lambda self, proj: {
                        'zebra': 1,
                        'alpha': 2,
                        'beta': 3,
                    }
                ),
                'normalize_section': (
                    lambda self, section_name, val: val
                ),
            },
        )()

        snapshot = fingerprint_service.fingerprint(
            projection=object(),
            policy=policy,
        )

        section_names = [sf.section_name for sf in (
            snapshot.sections
        )]

        # Should be alphabetically sorted
        assert section_names == ["alpha", "beta", "zebra"]


# ============================================================================
# CHANGE DETECTION TESTS
# ============================================================================

class TestChangeDetection:
    """Tests for semantic change detection between snapshots."""

    def _make_policy(self, value):
        """Helper to create mock policy."""
        return type(
            'MockPolicy',
            (),
            {
                'projection_name': (
                    'test.projection'
                ),
                'extract_sections': (
                    lambda self, proj: value
                ),
                'normalize_section': (
                    lambda self, section_name, val: (
                        val
                    )
                ),
            },
        )()

    def test_identical_snapshots_unchanged(
        self,
        fingerprint_service,
        change_detector,
    ):
        """Test 30: Change Detector Reports Unchanged"""

        snap1 = fingerprint_service.fingerprint(
            projection=object(),
            policy=self._make_policy(
                {"data": "test"}
            ),
        )

        snap2 = fingerprint_service.fingerprint(
            projection=object(),
            policy=self._make_policy(
                {"data": "test"}
            ),
        )

        report = change_detector.compare(
            previous=snap1,
            current=snap2,
        )

        assert (
            report.status
            == ResearchWorkspaceConsumerProjectionChangeStatus.UNCHANGED
        )

    def test_different_overall_reported_changed(
        self,
        fingerprint_service,
        change_detector,
    ):
        """Test 31: Change Detector Reports Changed"""

        snap1 = fingerprint_service.fingerprint(
            projection=object(),
            policy=self._make_policy(
                {"data": "ready"}
            ),
        )

        snap2 = fingerprint_service.fingerprint(
            projection=object(),
            policy=self._make_policy(
                {"data": "blocked"}
            ),
        )

        report = change_detector.compare(
            previous=snap1,
            current=snap2,
        )

        assert (
            report.status
            == ResearchWorkspaceConsumerProjectionChangeStatus.CHANGED
        )

    def test_section_changes_detected(
        self,
        fingerprint_service,
        change_detector,
    ):
        """Test 32: Change Detector Reports Changed Section"""

        policy_old = self._make_policy(
            {
                "status": "ready",
                "items": [],
            }
        )

        policy_new = self._make_policy(
            {
                "status": "ready",
                "items": ["new"],
            }
        )

        snap1 = fingerprint_service.fingerprint(
            projection=object(),
            policy=policy_old,
        )

        snap2 = fingerprint_service.fingerprint(
            projection=object(),
            policy=policy_new,
        )

        report = change_detector.compare(
            previous=snap1,
            current=snap2,
        )

        # Find items section
        items_change = next(
            (
                sc
                for sc in report.section_changes
                if sc.section_name == "items"
            ),
            None,
        )

        assert items_change is not None
        assert (
            items_change.status
            == ResearchWorkspaceConsumerProjectionSectionChangeStatus.CHANGED
        )

    def test_projection_name_mismatch_incomparable(
        self,
        fingerprint_service,
        change_detector,
    ):
        """Test 35: Projection Name Mismatch Is Incomparable"""

        policy1 = type(
            'MockPolicy1',
            (),
            {
                'projection_name': (
                    'workspace.bootstrap'
                ),
                'extract_sections': (
                    lambda self, proj: {"data": 1}
                ),
                'normalize_section': (
                    lambda self, section_name, val: val
                ),
            },
        )()

        policy2 = type(
            'MockPolicy2',
            (),
            {
                'projection_name': (
                    'workspace.attention'
                ),
                'extract_sections': (
                    lambda self, proj: {"data": 1}
                ),
                'normalize_section': (
                    lambda self, section_name, val: val
                ),
            },
        )()

        snap1 = fingerprint_service.fingerprint(
            projection=object(),
            policy=policy1,
        )

        snap2 = fingerprint_service.fingerprint(
            projection=object(),
            policy=policy2,
        )

        report = change_detector.compare(
            previous=snap1,
            current=snap2,
        )

        assert (
            report.status
            == ResearchWorkspaceConsumerProjectionChangeStatus.INCOMPARABLE
        )

    def test_snapshot_immutability(
        self,
        fingerprint_service,
    ):
        """Test 37: Fingerprint Snapshot Is Immutable"""

        snapshot = fingerprint_service.fingerprint(
            projection=object(),
            policy=self._make_policy(
                {"data": "test"}
            ),
        )

        # Should not be able to modify
        with pytest.raises(AttributeError):
            snapshot.overall = None  # type: ignore

    def test_change_report_immutability(
        self,
        fingerprint_service,
        change_detector,
    ):
        """Test 38: Change Report Is Immutable"""

        snap1 = fingerprint_service.fingerprint(
            projection=object(),
            policy=self._make_policy(
                {"data": "test"}
            ),
        )

        snap2 = fingerprint_service.fingerprint(
            projection=object(),
            policy=self._make_policy(
                {"data": "test"}
            ),
        )

        report = change_detector.compare(
            previous=snap1,
            current=snap2,
        )

        # Should not be able to modify
        with pytest.raises(AttributeError):
            report.status = (
                ResearchWorkspaceConsumerProjectionChangeStatus.CHANGED
            )  # type: ignore


# ============================================================================
# REGISTRY TESTS
# ============================================================================

class TestFingerprintPolicyRegistry:
    """Tests for fingerprint policy registry."""

    def test_policy_registration(
        self,
        policy_registry,
    ):
        """Test: Policy Can Be Registered"""

        class TestPolicy:
            @property
            def projection_name(self):
                return "test.projection"

        policy_registry.register_policy(
            TestPolicy()
        )

        retrieved = policy_registry.get_policy(
            "test.projection"
        )

        assert retrieved is not None

    def test_unregistered_policy_error(
        self,
        policy_registry,
    ):
        """Test 51: Unsupported Projection Policy Fails Clearly"""

        with pytest.raises(
            ResearchWorkspaceProjectionFingerprintPolicyNotFoundError
        ):
            policy_registry.get_policy(
                "nonexistent.projection"
            )

