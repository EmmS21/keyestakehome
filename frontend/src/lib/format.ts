export function formatUploadedAt(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

/** ISO datetime as `YYYY-MM-DD HH:MM` (UTC components; label elsewhere in UI). */
export function formatUtcDateTime(iso: string): string {
  const d = new Date(iso);
  const y = d.getUTCFullYear();
  const mo = String(d.getUTCMonth() + 1).padStart(2, "0");
  const day = String(d.getUTCDate()).padStart(2, "0");
  const h = String(d.getUTCHours()).padStart(2, "0");
  const min = String(d.getUTCMinutes()).padStart(2, "0");
  return `${y}-${mo}-${day} ${h}:${min}`;
}

export function changeStatusLabel(hasChanges: boolean | undefined): string {
  if (hasChanges === undefined) return "…";
  return hasChanges ? "Modified" : "Unchanged";
}
