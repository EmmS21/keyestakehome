export type CleaningPattern = "negatives" | "refunds" | "double_booking";

export const PATTERNS: CleaningPattern[] = [
  "negatives",
  "refunds",
  "double_booking",
];

export const PATTERN_LABELS: Record<CleaningPattern, string> = {
  negatives: "Negative values",
  refunds: "Refunds",
  double_booking: "Double booking",
};

export type CellChange = {
  period: string;
  value_before: number;
  value_after: number;
};

export type Proposal = {
  id: string;
  pattern: CleaningPattern;
  dataset_row_id: string;
  row_index: number;
  dimension_a: string | null;
  dimension_b: string | null;
  dimension_c: string | null;
  changes: CellChange[];
};

export type ProposalsResponse = {
  pattern: CleaningPattern;
  session_updated_at: string;
  proposals: Proposal[];
  total_count: number;
  limit: number;
  offset: number;
};

export type AcceptResponse = {
  submit_id: string;
  changes: {
    dataset_row_id: string;
    period: string;
    value_before: number;
    value_after: number;
  }[];
};

export type AuditEventFilter = "all" | "alteration" | "download";

export type AuditAlterationEntry = {
  kind: "alteration";
  id: string;
  submit_id: string;
  pattern: CleaningPattern;
  dataset_row_id: string;
  period: string;
  value_before: number;
  value_after: number;
  created_at: string;
};

export type AuditDownloadEntry = {
  kind: "download";
  id: string;
  created_at: string;
  export_number: number;
  audit_entry_count: number;
};

export type AuditTimelineEntry = AuditAlterationEntry | AuditDownloadEntry;

export type AuditLogResponse = {
  entries: AuditTimelineEntry[];
  total_count: number;
};

export type SessionResponse = {
  session_id: string;
  dataset_id: string;
  created_at: string;
  updated_at: string;
};
