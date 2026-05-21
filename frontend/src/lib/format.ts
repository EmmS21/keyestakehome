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

export function changeStatusLabel(hasChanges: boolean | undefined): string {
  if (hasChanges === undefined) return "…";
  return hasChanges ? "Modified" : "Unchanged";
}
