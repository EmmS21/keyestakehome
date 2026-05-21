"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type UIEvent,
} from "react";

import {
  ApiError,
  acceptProposals,
  fetchAudit,
  fetchProposals,
  findDataset,
  startSession,
} from "@/lib/api";
import {
  clearSelection,
  readSelection,
  writeSelection,
} from "@/lib/workspace-storage";
import {
  PATTERN_LABELS,
  PATTERNS,
  type AuditEntry,
  type CleaningPattern,
  type Proposal,
} from "@/lib/types";

const PROPOSALS_PAGE = 10;
const AUDIT_PAGE = 20;
const TOAST_MS = 5000;

type Props = { datasetId: string };

type PatternCounts = Record<CleaningPattern, number | null>;

function formatCell(value: number | undefined): string {
  if (value === undefined) return "—";
  return Number.isInteger(value) ? String(value) : String(value);
}

function patternShort(pattern: CleaningPattern): string {
  if (pattern === "negatives") return "neg.";
  if (pattern === "refunds") return "ref.";
  return "dbl.";
}

export function CleaningWorkspacePage({ datasetId }: Props) {
  const router = useRouter();
  const [booting, setBooting] = useState(true);
  const [datasetName, setDatasetName] = useState("");
  const [periodColumns, setPeriodColumns] = useState<string[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionUpdatedAt, setSessionUpdatedAt] = useState<string | null>(
    null,
  );
  const [patternCounts, setPatternCounts] = useState<PatternCounts>({
    negatives: null,
    refunds: null,
    double_booking: null,
  });
  const [activePattern, setActivePattern] = useState<CleaningPattern | null>(
    null,
  );
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [proposalsTotal, setProposalsTotal] = useState(0);
  const [proposalsLoading, setProposalsLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [submitting, setSubmitting] = useState(false);
  const [auditOpen, setAuditOpen] = useState(false);
  const [auditEntries, setAuditEntries] = useState<AuditEntry[]>([]);
  const [auditTotal, setAuditTotal] = useState(0);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditLoadingMore, setAuditLoadingMore] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [toastSeconds, setToastSeconds] = useState(5);

  const beforeScrollRef = useRef<HTMLDivElement>(null);
  const afterScrollRef = useRef<HTMLDivElement>(null);
  const loadMoreRef = useRef<HTMLDivElement>(null);
  const syncingScroll = useRef(false);
  const toastTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const showToast = useCallback((message: string) => {
    setToast(message);
    setToastSeconds(5);
    if (toastTimerRef.current) clearInterval(toastTimerRef.current);
    toastTimerRef.current = setInterval(() => {
      setToastSeconds((s) => {
        if (s <= 1) {
          if (toastTimerRef.current) clearInterval(toastTimerRef.current);
          setToast(null);
          return 5;
        }
        return s - 1;
      });
    }, 1000);
  }, []);

  const dismissToast = useCallback(() => {
    if (toastTimerRef.current) clearInterval(toastTimerRef.current);
    setToast(null);
    setToastSeconds(5);
  }, []);

  const refetchCounts = useCallback(async (sid: string) => {
    const counts = await Promise.all(
      PATTERNS.map(async (pattern) => {
        const page = await fetchProposals(sid, pattern, 1, 0);
        return { pattern, count: page.total_count };
      }),
    );
    setPatternCounts((prev) => {
      const next = { ...prev };
      for (const { pattern, count } of counts) {
        next[pattern] = count;
      }
      return next;
    });
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function boot() {
      try {
        const [session, dataset] = await Promise.all([
          startSession(datasetId),
          findDataset(datasetId),
        ]);
        if (cancelled) return;
        if (!dataset) {
          router.replace("/");
          return;
        }
        setSessionId(session.session_id);
        setDatasetName(dataset.name);
        setPeriodColumns(dataset.period_columns);
        await refetchCounts(session.session_id);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) {
          router.replace("/");
          return;
        }
        showToast(
          err instanceof ApiError ? err.message : "Could not load workspace",
        );
      } finally {
        if (!cancelled) setBooting(false);
      }
    }

    void boot();
    return () => {
      cancelled = true;
    };
  }, [datasetId, router, refetchCounts, showToast]);

  const loadProposals = useCallback(
    async (pattern: CleaningPattern, append: boolean) => {
      if (!sessionId) return;
      const offset = append ? proposals.length : 0;
      if (append) setLoadingMore(true);
      else setProposalsLoading(true);

      try {
        const page = await fetchProposals(
          sessionId,
          pattern,
          PROPOSALS_PAGE,
          offset,
        );
        setSessionUpdatedAt(page.session_updated_at);
        setProposalsTotal(page.total_count);
        setProposals((prev) =>
          append ? [...prev, ...page.proposals] : page.proposals,
        );

        if (!append) {
          const stored = readSelection(datasetId, pattern);
          const valid = new Set(page.proposals.map((p) => p.id));
          setSelectedIds(
            new Set(stored.filter((id) => valid.has(id))),
          );
        }
      } catch (err) {
        showToast(
          err instanceof ApiError ? err.message : "Could not load proposals",
        );
      } finally {
        setProposalsLoading(false);
        setLoadingMore(false);
      }
    },
    [sessionId, proposals.length, datasetId, showToast],
  );

  const openPattern = useCallback(
    (pattern: CleaningPattern) => {
      setActivePattern(pattern);
      setProposals([]);
      setProposalsTotal(0);
      setSelectedIds(new Set());
      void loadProposals(pattern, false);
    },
    [loadProposals],
  );

  const persistSelection = useCallback(
    (pattern: CleaningPattern, ids: Set<string>) => {
      writeSelection(datasetId, pattern, [...ids]);
    },
    [datasetId],
  );

  const toggleProposal = useCallback(
    (id: string) => {
      if (!activePattern) return;
      setSelectedIds((prev) => {
        const next = new Set(prev);
        if (next.has(id)) next.delete(id);
        else next.add(id);
        persistSelection(activePattern, next);
        return next;
      });
    },
    [activePattern, persistSelection],
  );

  const selectAllLoaded = useCallback(() => {
    if (!activePattern) return;
    const next = new Set(proposals.map((p) => p.id));
    setSelectedIds(next);
    persistSelection(activePattern, next);
  }, [activePattern, proposals, persistSelection]);

  const selectNone = useCallback(() => {
    if (!activePattern) return;
    setSelectedIds(new Set());
    persistSelection(activePattern, new Set());
  }, [activePattern, persistSelection]);

  const returnToIdle = useCallback(() => {
    setActivePattern(null);
    setProposals([]);
    setProposalsTotal(0);
    setSelectedIds(new Set());
  }, []);

  const loadAudit = useCallback(
    async (reset: boolean) => {
      if (!sessionId) return;
      const offset = reset ? 0 : auditEntries.length;
      if (reset) setAuditLoading(true);
      else setAuditLoadingMore(true);
      try {
        const page = await fetchAudit(sessionId, AUDIT_PAGE, offset);
        setAuditTotal(page.total_count);
        setAuditEntries((prev) =>
          reset ? page.entries : [...prev, ...page.entries],
        );
      } catch (err) {
        showToast(
          err instanceof ApiError ? err.message : "Could not load audit log",
        );
      } finally {
        setAuditLoading(false);
        setAuditLoadingMore(false);
      }
    },
    [sessionId, auditEntries.length, showToast],
  );

  const handleSubmit = useCallback(async () => {
    if (!sessionId || !activePattern || !sessionUpdatedAt) return;
    const ids = [...selectedIds];
    setSubmitting(true);
    try {
      const result = await acceptProposals(
        sessionId,
        activePattern,
        ids,
        sessionUpdatedAt,
      );
      const pattern = activePattern;
      clearSelection(datasetId, pattern);
      returnToIdle();
      await refetchCounts(sessionId);

      if (ids.length === 0 || result.changes.length === 0) {
        showToast("Nothing changed");
      } else {
        const n = result.changes.length;
        showToast(`Applied ${n} ${n === 1 ? "change" : "changes"}`);
      }

      if (auditOpen) {
        setAuditEntries([]);
        void loadAudit(true);
      }
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 404) {
          router.replace("/");
          return;
        }
        showToast(err.message);
        if (err.status === 409 || err.status === 400) {
          void loadProposals(activePattern, false);
        }
      } else {
        showToast("Submit failed. Try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }, [
    sessionId,
    activePattern,
    sessionUpdatedAt,
    selectedIds,
    datasetId,
    returnToIdle,
    refetchCounts,
    showToast,
    auditOpen,
    router,
    loadProposals,
    loadAudit,
  ]);

  useEffect(() => {
    if (auditOpen && sessionId && auditEntries.length === 0 && !auditLoading) {
      void loadAudit(true);
    }
  }, [auditOpen, sessionId, auditEntries.length, auditLoading, loadAudit]);

  useEffect(() => {
    if (!activePattern || !loadMoreRef.current) return;
    const el = loadMoreRef.current;
    const obs = new IntersectionObserver(
      (entries) => {
        if (
          entries[0]?.isIntersecting &&
          !loadingMore &&
          !proposalsLoading &&
          proposals.length < proposalsTotal
        ) {
          void loadProposals(activePattern, true);
        }
      },
      { root: beforeScrollRef.current, threshold: 0.1 },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [
    activePattern,
    loadingMore,
    proposalsLoading,
    proposals.length,
    proposalsTotal,
    loadProposals,
  ]);

  const syncScroll = (source: "before" | "after", e: UIEvent<HTMLDivElement>) => {
    if (syncingScroll.current) return;
    syncingScroll.current = true;
    const top = (e.target as HTMLDivElement).scrollTop;
    const other =
      source === "before" ? afterScrollRef.current : beforeScrollRef.current;
    if (other) other.scrollTop = top;
    syncingScroll.current = false;
  };

  const isIdle = activePattern === null;
  const hasMoreProposals = proposals.length < proposalsTotal;
  const patternEmpty =
    activePattern != null && !proposalsLoading && proposalsTotal === 0;
  const showCompare =
    activePattern != null && !proposalsLoading && proposalsTotal > 0;
  const allLoadedSelected =
    proposals.length > 0 &&
    proposals.every((p) => selectedIds.has(p.id));
  const anySelected = selectedIds.size > 0;

  if (booting) {
    return (
      <div data-testid="workspace-shell" className="workspace-loading">
        <p>Loading workspace…</p>
      </div>
    );
  }

  return (
    <div data-testid="workspace-shell" className="workspace-page">
      <header className="app-header workspace-header">
        <div className="workspace-header-left">
          <Link
            href="/"
            className="link"
            data-testid="workspace-explorer-link"
          >
            ← Explorer
          </Link>
          <span
            className="workspace-dataset-name"
            data-testid="workspace-dataset-name"
          >
            {datasetName}
          </span>
        </div>
        <button
          type="button"
          className="audit-toggle"
          data-testid="audit-toggle"
          aria-pressed={auditOpen}
          aria-label={auditOpen ? "Hide audit log" : "Show audit log"}
          onClick={() => setAuditOpen((o) => !o)}
        >
          <span className="audit-toggle-icon" aria-hidden>
            📋
          </span>
          <span className="audit-toggle-label">Audit log</span>
        </button>
      </header>

      <div className="workspace-body">
        <aside className="sidebar" data-testid="workspace-sidebar">
          {PATTERNS.map((pattern) => {
            const count = patternCounts[pattern];
            const muted = count === 0;
            const active = activePattern === pattern;
            return (
              <button
                key={pattern}
                type="button"
                className={`anomaly-tab${active ? " active" : ""}${muted ? " muted" : ""}`}
                data-testid={`pattern-tab-${pattern}`}
                onClick={() => {
                  if (activePattern === pattern) return;
                  openPattern(pattern);
                }}
              >
                {PATTERN_LABELS[pattern]}
                <span
                  className={`badge${muted ? " muted" : ""}`}
                  data-testid={`pattern-badge-${pattern}`}
                >
                  {count === null ? "—" : count}
                </span>
              </button>
            );
          })}
        </aside>

        <main
          className={`main${isIdle ? " idle" : ""}${toast ? " has-toast" : ""}`}
        >
          {isIdle ? (
            <>
              <p
                className="idle-prompt"
                data-testid="workspace-idle-prompt"
              >
                Select an anomaly to review
              </p>
              {toast ? (
                <div className="toast-overlay">
                  <div className="toast-card">
                    <button
                      type="button"
                      className="toast-close"
                      aria-label="Dismiss"
                      onClick={dismissToast}
                    >
                      ×
                    </button>
                    <p className="toast-message" data-testid="toast-message">
                      {toast}
                    </p>
                    <p className="toast-timer">
                      Closing in <strong>{toastSeconds}</strong>s
                    </p>
                  </div>
                </div>
              ) : null}
            </>
          ) : null}

          {activePattern && !isIdle ? (
            <div data-testid="compare-area" className="compare-area">
              <div className="main-header" data-testid="pattern-header">
                <div>
                  <h2>{PATTERN_LABELS[activePattern]}</h2>
                  <p className="sub">
                    {proposalsTotal} rows with issues
                  </p>
                </div>
                {showCompare ? (
                  <div className="toolbar">
                    {!allLoadedSelected ? (
                      <button
                        type="button"
                        className="btn btn-sm"
                        data-testid="select-all-button"
                        onClick={selectAllLoaded}
                      >
                        Select all
                      </button>
                    ) : null}
                    {anySelected ? (
                      <button
                        type="button"
                        className="btn btn-sm"
                        data-testid="select-none-button"
                        onClick={selectNone}
                      >
                        Select none
                      </button>
                    ) : null}
                  </div>
                ) : null}
              </div>

              {proposalsLoading ? (
                <div className="skeleton-table" data-testid="proposals-skeleton" />
              ) : null}

              {patternEmpty ? (
                <p
                  className="empty-state"
                  data-testid="pattern-empty-message"
                >
                  Nothing to clean for this pattern
                </p>
              ) : null}

              {showCompare ? (
                <>
                  <div className="compare-wrap">
                    <div className="compare-panels-row">
                      <div className="compare-panel before">
                        <div className="panel-title">BEFORE</div>
                        <div
                          className="grid-wrap"
                          ref={beforeScrollRef}
                          onScroll={(e) => syncScroll("before", e)}
                        >
                          <table
                            className="grid-table"
                            data-testid="before-table"
                          >
                            <thead>
                              <tr>
                                <th className="col-check">✓</th>
                                <th className="col-dim">A</th>
                                <th className="col-dim">B</th>
                                <th className="col-dim">C</th>
                                {periodColumns.map((col) => (
                                  <th key={col}>{col}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {proposals.map((p) => {
                                const changeMap = Object.fromEntries(
                                  p.changes.map((c) => [c.period, c]),
                                );
                                const checked = selectedIds.has(p.id);
                                return (
                                  <tr
                                    key={p.id}
                                    className={`proposal-row${checked ? " row-checked" : ""}`}
                                  >
                                    <td className="col-check">
                                      <input
                                        type="checkbox"
                                        data-testid="proposal-checkbox"
                                        data-proposal-id={p.id}
                                        checked={checked}
                                        onChange={() => toggleProposal(p.id)}
                                      />
                                    </td>
                                    <td className="col-dim">
                                      {p.dimension_a ?? ""}
                                    </td>
                                    <td className="col-dim">
                                      {p.dimension_b ?? ""}
                                    </td>
                                    <td className="col-dim">
                                      {p.dimension_c ?? ""}
                                    </td>
                                    {periodColumns.map((col) => {
                                      const ch = changeMap[col];
                                      return (
                                        <td
                                          key={col}
                                          className={
                                            ch
                                              ? "cell-anomaly"
                                              : "cell-normal"
                                          }
                                        >
                                          {formatCell(ch?.value_before)}
                                        </td>
                                      );
                                    })}
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                          {hasMoreProposals ? (
                            <div ref={loadMoreRef} className="load-more-sentinel">
                              {loadingMore ? "Loading more…" : ""}
                            </div>
                          ) : proposals.length > 0 ? (
                            <p
                              className="list-end-marker"
                              data-testid="proposals-end-marker"
                            >
                              End of list — all {proposalsTotal} rows loaded
                            </p>
                          ) : null}
                        </div>
                      </div>
                      <div className="compare-panel after">
                        <div className="panel-title">AFTER</div>
                        <div
                          className="grid-wrap"
                          ref={afterScrollRef}
                          onScroll={(e) => syncScroll("after", e)}
                        >
                          <table
                            className="grid-table after-table"
                            data-testid="after-table"
                          >
                            <thead>
                              <tr>
                                <th className="col-dim">A</th>
                                <th className="col-dim">B</th>
                                <th className="col-dim">C</th>
                                {periodColumns.map((col) => (
                                  <th key={col}>{col}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {proposals.map((p) => {
                                const changeMap = Object.fromEntries(
                                  p.changes.map((c) => [c.period, c]),
                                );
                                const checked = selectedIds.has(p.id);
                                return (
                                  <tr
                                    key={p.id}
                                    className={`proposal-row${checked ? " row-checked" : ""}`}
                                  >
                                    <td className="col-dim">
                                      {p.dimension_a ?? ""}
                                    </td>
                                    <td className="col-dim">
                                      {p.dimension_b ?? ""}
                                    </td>
                                    <td className="col-dim">
                                      {p.dimension_c ?? ""}
                                    </td>
                                    {periodColumns.map((col) => {
                                      const ch = changeMap[col];
                                      return (
                                        <td
                                          key={col}
                                          className={
                                            ch ? "cell-fix" : "cell-normal"
                                          }
                                        >
                                          {formatCell(ch?.value_after)}
                                        </td>
                                      );
                                    })}
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div className="submit-row">
                    <span className="legend">
                      Dark = anomaly · Gray = proposed fix
                    </span>
                    <button
                      type="button"
                      className="btn btn-primary"
                      data-testid="submit-button"
                      disabled={submitting}
                      onClick={() => void handleSubmit()}
                    >
                      Submit
                    </button>
                  </div>
                </>
              ) : null}
            </div>
          ) : null}
        </main>

        <aside
          className={`audit-sidebar${auditOpen ? "" : " is-hidden"}`}
          data-testid="audit-sidebar"
        >
          <div className="audit-sidebar-header">
            <span>Audit log</span>
            <button
              type="button"
              className="btn btn-sm"
              aria-label="Close audit log"
              onClick={() => setAuditOpen(false)}
            >
              ×
            </button>
          </div>
          <div
            className="audit-sidebar-body"
            onScroll={(e) => {
              const el = e.currentTarget;
              if (
                auditLoadingMore ||
                auditLoading ||
                auditEntries.length >= auditTotal
              ) {
                return;
              }
              if (
                el.scrollTop + el.clientHeight >=
                el.scrollHeight - 40
              ) {
                void loadAudit(false);
              }
            }}
          >
            {auditLoading && auditEntries.length === 0 ? (
              <p className="audit-sidebar-empty">Loading…</p>
            ) : auditTotal === 0 ? (
              <p className="audit-sidebar-empty" data-testid="audit-empty">
                No changes yet
              </p>
            ) : (
              <table className="data" data-testid="audit-table">
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Pattern</th>
                    <th>Row</th>
                    <th>Period</th>
                    <th>Before</th>
                    <th>After</th>
                  </tr>
                </thead>
                <tbody>
                  {auditEntries.map((e) => (
                    <tr key={e.id} data-testid="audit-row">
                      <td>
                        {new Date(e.created_at).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </td>
                      <td>{patternShort(e.pattern)}</td>
                      <td>{e.dataset_row_id.slice(0, 8)}…</td>
                      <td>{e.period}</td>
                      <td>{formatCell(e.value_before)}</td>
                      <td>{formatCell(e.value_after)}</td>
                    </tr>
                  ))}
                  {auditLoadingMore ? (
                    <tr>
                      <td colSpan={6}>Loading more…</td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            )}
            {auditEntries.length > 0 &&
            auditEntries.length >= auditTotal ? (
              <p className="list-end-marker">
                End of audit log — all {auditTotal} changes loaded
              </p>
            ) : null}
          </div>
          {auditTotal > 0 ? (
            <p className="audit-sidebar-footer">
              Scroll up for newer entries
            </p>
          ) : null}
        </aside>
      </div>
    </div>
  );
}
