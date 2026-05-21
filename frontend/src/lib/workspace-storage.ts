import type { CleaningPattern } from "./types";

export function selectionKey(
  datasetId: string,
  pattern: CleaningPattern,
): string {
  return `cleaning-selection:${datasetId}:${pattern}`;
}

export function readSelection(
  datasetId: string,
  pattern: CleaningPattern,
): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = sessionStorage.getItem(selectionKey(datasetId, pattern));
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    return Array.isArray(parsed)
      ? parsed.filter((id): id is string => typeof id === "string")
      : [];
  } catch {
    return [];
  }
}

export function writeSelection(
  datasetId: string,
  pattern: CleaningPattern,
  ids: string[],
): void {
  if (typeof window === "undefined") return;
  sessionStorage.setItem(
    selectionKey(datasetId, pattern),
    JSON.stringify(ids),
  );
}

export function clearSelection(
  datasetId: string,
  pattern: CleaningPattern,
): void {
  if (typeof window === "undefined") return;
  sessionStorage.removeItem(selectionKey(datasetId, pattern));
}
