"""Domain errors for ingest and cleaning logic."""


class IngestError(Exception):
    """Base class for dataset ingest failures."""


class EmptyDatasetError(IngestError):
    """File is empty or whitespace only."""


class NoDataRowsError(IngestError):
    """CSV has a header but no data rows."""


class NoPeriodColumnsError(IngestError):
    """No YYYYMM period columns found in the header."""


class InvalidPeriodValueError(IngestError):
    """A period cell is not numeric."""

    def __init__(self, row_index: int, period: str, raw_value: str) -> None:
        self.row_index = row_index
        self.period = period
        self.raw_value = raw_value
        super().__init__(
            f"Non-numeric value {raw_value!r} at row {row_index}, period {period}"
        )
