from datetime import (
    datetime,
    date,
)

from enum import Enum
from typing import Any

from .research_workspace_consumer_projection_fingerprint_errors import (
    ResearchWorkspaceUnsupportedCanonicalValueError,
    ResearchWorkspaceNaiveDatetimeCanonicalizationError,
)


class ResearchWorkspaceConsumerProjectionCanonicalizer:
    """
    Converts semantic projection values to deterministic
    primitive representations suitable for stable hashing.

    Supported types:
    - None → null
    - bool → boolean
    - int → number
    - float → number (finite only)
    - str → string
    - Enum → string (stable serialized value)
    - datetime → ISO 8601 UTC string
    - date → ISO 8601 string
    - tuple → array
    - list → array
    - dict/Mapping → object (sorted keys)
    - dataclass → object
    - Pydantic model → object

    Unsupported types raise clear errors.
    Non-finite floats raise errors.
    Naive datetimes raise errors.

    The canonicalizer produces only JSON-compatible
    primitive data structures.
    """

    def canonicalize(
        self,
        value: Any,
    ) -> Any:
        """
        Converts a value to a deterministic
        primitive representation.

        Arguments:
            value: The value to canonicalize

        Returns:
            A JSON-compatible primitive structure

        Raises:
            ResearchWorkspaceUnsupportedCanonicalValueError:
                If the value type is not supported

            ResearchWorkspaceNaiveDatetimeCanonicalizationError:
                If a naive datetime is encountered
        """

        # None
        if value is None:
            return None

        # Boolean
        if isinstance(value, bool):
            return value

        # Integer
        if isinstance(value, int):
            return value

        # Float
        if isinstance(value, float):
            if not (-float('inf') < value < float('inf')):
                raise ResearchWorkspaceUnsupportedCanonicalValueError(
                    f"Non-finite float not supported: {value}"
                )
            return value

        # String
        if isinstance(value, str):
            return value

        # Enum
        if isinstance(value, Enum):
            return self._canonicalize_enum(value)

        # Datetime (must check before date)
        if isinstance(value, datetime):
            return self._canonicalize_datetime(value)

        # Date
        if isinstance(value, date):
            return self._canonicalize_date(value)

        # Tuple
        if isinstance(value, tuple):
            return [
                self.canonicalize(item)
                for item in value
            ]

        # List
        if isinstance(value, list):
            return [
                self.canonicalize(item)
                for item in value
            ]

        # Dictionary
        if isinstance(value, dict):
            return self._canonicalize_mapping(value)

        # Dataclass (check before Pydantic)
        if hasattr(value, '__dataclass_fields__'):
            return self._canonicalize_dataclass(value)

        # Pydantic model
        if hasattr(value, 'model_dump'):
            return self._canonicalize_mapping(
                value.model_dump()
            )

        # Unsupported type
        raise ResearchWorkspaceUnsupportedCanonicalValueError(
            f"Cannot canonicalize type {type(value).__name__}: {value!r}"
        )

    def _canonicalize_enum(
        self,
        value: Enum,
    ) -> str:
        """
        Converts an enum to its stable string value.
        """
        return value.value

    def _canonicalize_datetime(
        self,
        value: datetime,
    ) -> str:
        """
        Converts a datetime to ISO 8601 UTC string.

        Raises if the datetime is naive (timezone-unaware).
        """
        if value.tzinfo is None:
            raise ResearchWorkspaceNaiveDatetimeCanonicalizationError(
                f"Naive datetime not supported: {value!r}. "
                f"All datetimes must be timezone-aware."
            )

        # Convert to UTC and format deterministically
        utc_value = value.astimezone(
            __import__('datetime').timezone.utc
        )

        # ISO 8601 format with Z suffix
        return utc_value.strftime(
            '%Y-%m-%dT%H:%M:%S.%fZ'
        )

    def _canonicalize_date(
        self,
        value: date,
    ) -> str:
        """
        Converts a date to ISO 8601 string.
        """
        return value.isoformat()

    def _canonicalize_mapping(
        self,
        value: dict,
    ) -> dict:
        """
        Canonicalizes a mapping by:
        - Canonicalizing all keys (must be strings)
        - Sorting keys deterministically
        - Canonicalizing all values
        """
        result = {}

        for key, val in value.items():
            # Only string-like keys are supported
            if not isinstance(key, str):
                raise ResearchWorkspaceUnsupportedCanonicalValueError(
                    f"Non-string mapping key not supported: {key!r}"
                )

            result[key] = self.canonicalize(val)

        # Return with sorted keys for determinism
        return {
            k: result[k]
            for k in sorted(result.keys())
        }

    def _canonicalize_dataclass(
        self,
        value: object,
    ) -> dict:
        """
        Canonicalizes a dataclass by converting
        it to a dict and canonicalizing that.
        """
        from dataclasses import asdict

        data_dict = asdict(value)
        return self._canonicalize_mapping(data_dict)
