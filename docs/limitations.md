# Limitations (v1)

Known boundaries of the design. Intentional for scope, not oversights.

---

## Data shape and scale

Deal revenue CSVs are **long × wide**: few dimension columns (`A`, `B`, `C`, …) and many period columns (`202401`, `202402`, …). Row counts and period counts can be large; anomalies are sparse but detectors must scan **every row**.

| Approach | Why |
|----------|-----|
| Full grid on server only | Too large to load in the browser |
| Streamed ingest → batched DB insert | Avoid holding whole files in RAM |
| Chunked detectors | Scan all rows without one giant in-memory grid |
| Paginated proposals + `total_count` | Context (a page) + scope (how many issues) |
| Delta submit | `UPDATE` only accepted cells; API returns `changes[]` only |
| Paginated audit | Trail grows over multi-day sessions |
| Materialized `cell_values` | Working copy for detectors and export |

**Not in v1:** job queues, sharding, read replicas, long-lived proposal cache tables, proposal storage as source of truth (proposals are computed from `cell_values`).

---

## Product assumptions

- **One analyst, one dataset at a time** — no real-time collaboration or auth.
- **Schema stable per file** — leading columns are dimensions; remaining columns are periods.
- **Each row is independent** — detectors do not look across rows (see below).
- **Pipeline order is display-only** — sidebar lists negatives → refunds → double booking; the analyst may open and accept **any** pattern in any order. Fixes still change what other detectors see on the working copy.
- **One pattern in the main panel** — user clicks a tab to review; default is **no tab selected** (idle). Submit does not auto-switch tabs.
- **Detection rules are fixed** — negatives, refunds, double booking per the brief; not configurable in the UI.
- **Re-clean** — clicking a tab again may show new proposals if the working copy changed; there is no dedicated “reopen completed step” flow.

---

## Row-independent detection only

**Limitation:** Detectors run **per row**. Rules do not look across rows (e.g. matching a credit on customer A to a debit on customer B).

**Rationale:** The brief’s patterns — negatives, refunds (consecutive periods summing to zero), double booking (adjacent months on one row) — all depend on **one row’s** period columns. Chunked processing reads rows in batches but still scans **every row**; it does not change results for these rules.

---

## Stale submit / two tabs

**Behavior:** `GET .../proposals` returns `session_updated_at`. `POST .../accept` must send the same value; otherwise **409 Conflict** (reload proposals). Cells already at the fix value are skipped (no audit row).

---

## Export tracking without user identity

**Behavior:** Each `GET /datasets/{id}/export` appends a row to `export_events` with `exported_at`, `export_number` (1st, 2nd, … download for that dataset), `session_updated_at`, and `audit_entry_count` (how many cell-level audit rows existed at download time).

**Limitation:** We do **not** record **who** exported the file (no auth, no user id, no IP logging in v1).

**Rationale:** We still need to retrace **what** left the system and **which version** of the cleaned grid it was — pair `export_events` with `audit_log_entries` (and `session_updated_at`) to reconstruct history. Analyst identity is a later concern when multi-user auth exists.

---

## Out of scope (v1)

- Multi-user auth, roles, or “who exported” identity
- Editing detection formulas in the UI
- Undo beyond “don’t accept” (no single-step undo)
- Cross-row detection rules
- Bulk upload scheduling or external API integrations
- Statistical / ML explanations for proposals
- Full deal grid in the browser (only proposal rows and audit pages)
- Auto-advance to the next pattern tab after Submit
- Persisting active tab, audit panel open state, or scroll position in the URL
- Separate `/audit` route (audit is a sidebar in the workspace)
- Job queues, horizontal scale, read replicas
