import type {
  AcceptResponse,
  AuditLogResponse,
  CleaningPattern,
  ProposalsResponse,
  SessionResponse,
} from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

export type DatasetSummary = {
  id: string;
  name: string;
  period_columns: string[];
  row_count: number;
  uploaded_at: string;
};

export type DatasetListResponse = {
  datasets: DatasetSummary[];
};

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public detail: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function formatDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "message" in detail) {
    return String((detail as { message: string }).message);
  }
  return JSON.stringify(detail);
}

async function parseError(res: Response): Promise<ApiError> {
  let detail: unknown = res.statusText;
  try {
    const body = await res.json();
    detail = body.detail ?? body;
  } catch {
    /* ignore */
  }
  return new ApiError(formatDetail(detail), res.status, detail);
}

export async function listDatasets(): Promise<DatasetSummary[]> {
  const res = await fetch(`${API_BASE}/datasets`, { cache: "no-store" });
  if (!res.ok) throw await parseError(res);
  const data: DatasetListResponse = await res.json();
  return data.datasets;
}

export async function startSession(
  datasetId: string,
): Promise<SessionResponse> {
  const res = await fetch(`${API_BASE}/datasets/${datasetId}/sessions`, {
    method: "POST",
  });
  if (!res.ok) throw await parseError(res);
  return res.json();
}

export async function createOrResumeSession(datasetId: string): Promise<string> {
  const data = await startSession(datasetId);
  return data.session_id;
}

export async function findDataset(
  datasetId: string,
): Promise<DatasetSummary | null> {
  const datasets = await listDatasets();
  return datasets.find((d) => d.id === datasetId) ?? null;
}

export async function fetchPatternCount(
  sessionId: string,
  pattern: CleaningPattern,
): Promise<number> {
  const page = await fetchProposals(sessionId, pattern, 1, 0);
  return page.total_count;
}

export async function fetchProposals(
  sessionId: string,
  pattern: CleaningPattern,
  limit: number,
  offset: number,
): Promise<ProposalsResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  const res = await fetch(
    `${API_BASE}/sessions/${sessionId}/steps/${pattern}/proposals?${params}`,
    { cache: "no-store" },
  );
  if (!res.ok) throw await parseError(res);
  return res.json();
}

export async function acceptProposals(
  sessionId: string,
  pattern: CleaningPattern,
  proposalIds: string[],
  sessionUpdatedAt: string,
): Promise<AcceptResponse> {
  const res = await fetch(
    `${API_BASE}/sessions/${sessionId}/steps/${pattern}/accept`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        proposal_ids: proposalIds,
        session_updated_at: sessionUpdatedAt,
      }),
    },
  );
  if (!res.ok) throw await parseError(res);
  return res.json();
}

export async function fetchAudit(
  sessionId: string,
  limit: number,
  offset: number,
): Promise<AuditLogResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  const res = await fetch(
    `${API_BASE}/sessions/${sessionId}/audit?${params}`,
    { cache: "no-store" },
  );
  if (!res.ok) throw await parseError(res);
  return res.json();
}

/** True if this dataset's cleaning session has any audit entries. */
export async function datasetHasAuditChanges(datasetId: string): Promise<boolean> {
  const sessionId = await createOrResumeSession(datasetId);
  const res = await fetch(
    `${API_BASE}/sessions/${sessionId}/audit?limit=1&offset=0`,
    { cache: "no-store" },
  );
  if (!res.ok) throw await parseError(res);
  const data: AuditLogResponse = await res.json();
  return data.total_count > 0;
}

export async function uploadDataset(file: File): Promise<DatasetSummary> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/datasets`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw await parseError(res);
  return res.json();
}

export { API_BASE };
