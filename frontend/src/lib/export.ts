/** Build export URL and download filename (pure helpers for tests). */

export function getExportUrl(apiBase: string, datasetId: string): string {
  const base = apiBase.replace(/\/$/, "");
  return `${base}/datasets/${datasetId}/export`;
}

export function exportDownloadFilename(datasetName: string): string {
  const trimmed = datasetName.trim() || "export.csv";
  return trimmed.toLowerCase().endsWith(".csv") ? trimmed : `${trimmed}.csv`;
}
