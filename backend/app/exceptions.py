"""Domain errors for ingest and cleaning logic."""


class IngestError(Exception):
    """Base class for dataset ingest failures."""


class EmptyDatasetError(IngestError):
    """File is empty or whitespace only."""


class NoDataRowsError(IngestError):
    """CSV has a header but no data rows."""


class NoPeriodColumnsError(IngestError):
    """No YYYYMM period columns found in the header."""


class DuplicateDatasetNameError(IngestError):
    """A dataset with this filename already exists."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f'A dataset named "{name}" is already uploaded')


class DatasetNotFoundError(Exception):
    """No dataset exists for the given id."""

    def __init__(self, dataset_id) -> None:
        self.dataset_id = dataset_id
        super().__init__(f"Dataset not found: {dataset_id}")


class SessionNotFoundError(Exception):
    """No cleaning session exists for the given id."""

    def __init__(self, session_id) -> None:
        self.session_id = session_id
        super().__init__(f"Session not found: {session_id}")


class ProposalNotFoundError(Exception):
    """Proposal id is missing or not valid for this session and pattern."""

    def __init__(self, proposal_id: str) -> None:
        self.proposal_id = proposal_id
        super().__init__(f"Proposal not found: {proposal_id}")


class SessionConflictError(Exception):
    """Session changed since the client loaded proposals."""

    def __init__(self, session_id) -> None:
        self.session_id = session_id
        super().__init__(
            f"Session {session_id} was updated; reload proposals before submitting"
        )


class InvalidPeriodValueError(IngestError):
    """A period cell is not numeric."""

    def __init__(self, row_index: int, period: str, raw_value: str) -> None:
        self.row_index = row_index
        self.period = period
        self.raw_value = raw_value
        super().__init__(
            f"Non-numeric value {raw_value!r} at row {row_index}, period {period}"
        )
