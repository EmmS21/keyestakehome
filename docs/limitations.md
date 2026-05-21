# Limitations (v1)

Known boundaries of the design. Intentional for scope, not oversights.

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

## Related v1 scope (not limitations of the data model)

- One analyst per dataset session; no collaboration.
- Detection rules fixed by the brief — not user-configurable.
- Analyst may open and accept patterns in any order; sidebar order is display-only. Which tab is active is frontend state, not stored on `cleaning_sessions`.

Full product assumptions: [`architecture.md`](../architecture.md) §2.2–2.4.
