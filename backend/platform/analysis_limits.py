from dataclasses import dataclass
from typing import Optional

from backend.llm.config import InvalidConfigurationError


@dataclass(frozen=True)
class AnalysisLimits:
    """Optional resource limits for one analysis run, following the repository's
    configuration convention (a dataclass whose validate() raises
    InvalidConfigurationError). Both default to None: no limit, exactly the
    behaviour before limits existed.

    max_seconds: wall-clock budget, checked between pipeline stages (a running
        stage is not interrupted, so a run can overshoot by one stage).
    max_file_bytes: largest local paper file accepted, checked before any
        processing starts.
    """

    max_seconds: Optional[float] = None
    max_file_bytes: Optional[int] = None

    def validate(self) -> "AnalysisLimits":
        problems = []
        if self.max_seconds is not None and (
            isinstance(self.max_seconds, bool) or not isinstance(self.max_seconds, (int, float)) or not self.max_seconds > 0
        ):
            problems.append(f"max_seconds {self.max_seconds!r} must be a number greater than 0")
        if self.max_file_bytes is not None and (
            isinstance(self.max_file_bytes, bool) or not isinstance(self.max_file_bytes, int) or self.max_file_bytes < 1
        ):
            problems.append(f"max_file_bytes {self.max_file_bytes!r} must be an integer of at least 1")
        if problems:
            raise InvalidConfigurationError("; ".join(problems))
        return self
