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

## Related v1 scope (not limitations of the data model)

- One analyst per dataset session; no collaboration.
- Detection rules fixed by the brief — not user-configurable.
- Analyst may open and accept patterns in any order; sidebar order is display-only. Which tab is active is frontend state, not stored on `cleaning_sessions`.

Full product assumptions: [`architecture.md`](../architecture.md) §2.2–2.4.
