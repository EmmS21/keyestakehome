const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

export type DatasetSummary = {
  id: string;
  name: string;
  period_columns: string[];
  row_count: number;
  uploaded_at: string;
};

export type AuditLogResponse = {
  entries: unknown[];
  total_count: number;
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

export async function createOrResumeSession(datasetId: string): Promise<string> {
  const res = await fetch(`${API_BASE}/datasets/${datasetId}/sessions`, {
    method: "POST",
  });
  if (!res.ok) throw await parseError(res);
  const data: { session_id: string } = await res.json();
  return data.session_id;
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
