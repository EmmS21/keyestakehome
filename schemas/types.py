"""Shared enums and constrained types."""

from enum import Enum


class CleaningPattern(str, Enum):
    """Pipeline steps. `DONE` = all patterns finished."""

    NEGATIVES = "negatives"
    REFUNDS = "refunds"
    DOUBLE_BOOKING = "double_booking"
    DONE = "done"


# Ordered pipeline for detectors and sidebar (excludes DONE)
PIPELINE_STEPS: tuple[CleaningPattern, ...] = (
    CleaningPattern.NEGATIVES,
    CleaningPattern.REFUNDS,
    CleaningPattern.DOUBLE_BOOKING,
)
