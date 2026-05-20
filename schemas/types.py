"""Shared enums and constrained types."""

from enum import Enum


class CleaningPattern(str, Enum):
    """Pipeline steps. `DONE` = all patterns finished."""

    NEGATIVES = "negatives"
    REFUNDS = "refunds"
    DOUBLE_BOOKING = "double_booking"
    DONE = "done"


# Sidebar display order only — not enforced on the server (any pattern may be opened/accepted)
PIPELINE_STEPS: tuple[CleaningPattern, ...] = (
    CleaningPattern.NEGATIVES,
    CleaningPattern.REFUNDS,
    CleaningPattern.DOUBLE_BOOKING,
)
