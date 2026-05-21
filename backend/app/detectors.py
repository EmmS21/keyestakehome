"""Per-row anomaly detectors — rules from the brief (see README.md)."""

from uuid import UUID

from schemas.api import CellChange
from schemas.types import CleaningPattern

_SUM_EPSILON = 1e-9


def _period_map(period_columns: list[str], values: list[tuple[str, float]]) -> dict[str, float]:
    by_period = {period: value for period, value in values}
    return {period: by_period.get(period, 0.0) for period in period_columns}


def detect_negatives(period_columns: list[str], periods: dict[str, float]) -> list[CellChange]:
    changes: list[CellChange] = []
    for period in period_columns:
        value = periods[period]
        if value < 0:
            changes.append(
                CellChange(period=period, value_before=value, value_after=0.0)
            )
    return changes


def detect_refunds(period_columns: list[str], periods: dict[str, float]) -> list[CellChange]:
    flagged: set[str] = set()
    n = len(period_columns)
    for start in range(n):
        running_sum = 0.0
        for end in range(start, n):
            running_sum += periods[period_columns[end]]
            if end > start and abs(running_sum) < _SUM_EPSILON:
                for idx in range(start, end + 1):
                    flagged.add(period_columns[idx])

    if not flagged:
        return []

    return [
        CellChange(period=period, value_before=periods[period], value_after=0.0)
        for period in period_columns
        if period in flagged
    ]


def detect_double_booking(
    period_columns: list[str], periods: dict[str, float]
) -> list[CellChange]:
    changes_by_period: dict[str, CellChange] = {}
    for idx in range(len(period_columns) - 1):
        left = period_columns[idx]
        right = period_columns[idx + 1]
        m_i = periods[left]
        m_next = periods[right]
        if m_i <= 0:
            continue
        average = (m_i + m_next) / 2
        if abs(average - m_i / 2) >= _SUM_EPSILON:
            continue
        for period, value_before in ((left, m_i), (right, m_next)):
            if period not in changes_by_period:
                changes_by_period[period] = CellChange(
                    period=period,
                    value_before=value_before,
                    value_after=average,
                )

    return [changes_by_period[period] for period in period_columns if period in changes_by_period]


def detect_for_pattern(
    pattern: CleaningPattern,
    period_columns: list[str],
    periods: dict[str, float],
) -> list[CellChange]:
    if pattern == CleaningPattern.NEGATIVES:
        return detect_negatives(period_columns, periods)
    if pattern == CleaningPattern.REFUNDS:
        return detect_refunds(period_columns, periods)
    if pattern == CleaningPattern.DOUBLE_BOOKING:
        return detect_double_booking(period_columns, periods)
    return []


def proposal_id(pattern: CleaningPattern, dataset_row_id: UUID) -> str:
    return f"{pattern.value}:{dataset_row_id}"
