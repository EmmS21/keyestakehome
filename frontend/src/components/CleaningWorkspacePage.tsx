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
  findDataset,
  startSession,
} from "@/lib/api";
import {
  countActionableProposals,
  actionableChanges,
  fetchActionableProposalsPage,
} from "@/lib/proposals";
import {
  clearSelection,
  readSelection,
  writeSelection,
} from "@/lib/workspace-storage";
import { formatUtcDateTime } from "@/lib/format";
import {
  PATTERN_LABELS,
  PATTERNS,
  type AuditEventFilter,
  type AuditTimelineEntry,
  type CleaningPattern,
  type Proposal,
} from "@/lib/types";

const PROPOSALS_PAGE = 10;
const AUDIT_PAGE = 20;
const TOAST_MS = 5000;
const AUDIT_SIDEBAR_WIDTH_KEY = "audit-sidebar-width";
const AUDIT_SIDEBAR_DEFAULT = 340;
const AUDIT_SIDEBAR_MIN = 280;
const AUDIT_SIDEBAR_MAX = 640;

function auditSidebarMaxWidth(): number {
  if (typeof window === "undefined") return AUDIT_SIDEBAR_MAX;
  return Math.min(AUDIT_SIDEBAR_MAX, Math.floor(window.innerWidth * 0.55));
}

function clampAuditSidebarWidth(width: number): number {
  return Math.min(
    auditSidebarMaxWidth(),
    Math.max(AUDIT_SIDEBAR_MIN, Math.round(width)),
  );
}

function readStoredAuditSidebarWidth(): number {
  if (typeof window === "undefined") return AUDIT_SIDEBAR_DEFAULT;
  try {
    const raw = localStorage.getItem(AUDIT_SIDEBAR_WIDTH_KEY);
    if (!raw) return AUDIT_SIDEBAR_DEFAULT;
    const n = Number.parseInt(raw, 10);
    return Number.isFinite(n) ? clampAuditSidebarWidth(n) : AUDIT_SIDEBAR_DEFAULT;
  } catch {
    return AUDIT_SIDEBAR_DEFAULT;
  }
}

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
  const [auditFilter, setAuditFilter] = useState<AuditEventFilter>("all");
  const [auditEntries, setAuditEntries] = useState<AuditTimelineEntry[]>([]);
  const [auditTotal, setAuditTotal] = useState(0);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditLoadingMore, setAuditLoadingMore] = useState(false);
  const [auditSidebarWidth, setAuditSidebarWidth] = useState(
    AUDIT_SIDEBAR_DEFAULT,
  );
  const [auditResizing, setAuditResizing] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [toastSeconds, setToastSeconds] = useState(5);

  const beforeScrollRef = useRef<HTMLDivElement>(null);
  const afterScrollRef = useRef<HTMLDivElement>(null);
  const loadMoreRef = useRef<HTMLDivElement>(null);
  const proposalsServerOffsetRef = useRef(0);
  const syncingScroll = useRef(false);
  const toastTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const auditResizeRef = useRef<{ startX: number; startWidth: number } | null>(
    null,
  );

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
        const count = await countActionableProposals(sid, pattern);
        return { pattern, count };
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
      if (append) setLoadingMore(true);
      else setProposalsLoading(true);

      try {
        if (!append) {
          const [actionableTotal, page] = await Promise.all([
            countActionableProposals(sessionId, pattern),
            fetchActionableProposalsPage(
              sessionId,
              pattern,
              PROPOSALS_PAGE,
              0,
            ),
          ]);
          setProposalsTotal(actionableTotal);
          setSessionUpdatedAt(page.session_updated_at);
          setProposals(page.proposals);
          proposalsServerOffsetRef.current = page.nextServerOffset;

          const stored = readSelection(datasetId, pattern);
          const valid = new Set(page.proposals.map((p) => p.id));
          setSelectedIds(new Set(stored.filter((id) => valid.has(id))));
        } else {
          const page = await fetchActionableProposalsPage(
            sessionId,
            pattern,
            PROPOSALS_PAGE,
            proposalsServerOffsetRef.current,
          );
          setSessionUpdatedAt(page.session_updated_at);
          setProposals((prev) => [...prev, ...page.proposals]);
          proposalsServerOffsetRef.current = page.nextServerOffset;
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
    [sessionId, datasetId, showToast],
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
        const page = await fetchAudit(
          sessionId,
          AUDIT_PAGE,
          offset,
          auditFilter,
        );
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
    [sessionId, auditEntries.length, showToast, auditFilter],
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
    if (!auditOpen || !sessionId) return;
    setAuditEntries([]);
    void loadAudit(true);
  }, [auditOpen, sessionId, auditFilter]); // eslint-disable-line react-hooks/exhaustive-deps -- reload when filter or open changes

  useEffect(() => {
    setAuditSidebarWidth(readStoredAuditSidebarWidth());
  }, []);

  useEffect(() => {
    const onWindowResize = () => {
      setAuditSidebarWidth((w) => clampAuditSidebarWidth(w));
    };
    window.addEventListener("resize", onWindowResize);
    return () => window.removeEventListener("resize", onWindowResize);
  }, []);

  useEffect(() => {
    if (!auditResizing) return;

    const onMove = (e: MouseEvent) => {
      const drag = auditResizeRef.current;
      if (!drag) return;
      const delta = drag.startX - e.clientX;
      setAuditSidebarWidth(clampAuditSidebarWidth(drag.startWidth + delta));
    };

    const onUp = () => {
      auditResizeRef.current = null;
      setAuditResizing(false);
      document.body.classList.remove("audit-resize-active");
      setAuditSidebarWidth((w) => {
        const clamped = clampAuditSidebarWidth(w);
        try {
          localStorage.setItem(AUDIT_SIDEBAR_WIDTH_KEY, String(clamped));
        } catch {
          /* ignore quota / private mode */
        }
        return clamped;
      });
    };

    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
    return () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };
  }, [auditResizing]);

  const startAuditSidebarResize = (e: React.MouseEvent) => {
    e.preventDefault();
    auditResizeRef.current = {
      startX: e.clientX,
      startWidth: auditSidebarWidth,
    };
    setAuditResizing(true);
    document.body.classList.add("audit-resize-active");
  };

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
                                  actionableChanges(p.changes).map((c) => [
                                    c.period,
                                    c,
                                  ]),
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
                                  actionableChanges(p.changes).map((c) => [
                                    c.period,
                                    c,
                                  ]),
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
          className={`audit-sidebar${auditOpen ? "" : " is-hidden"}${auditResizing ? " is-resizing" : ""}`}
          data-testid="audit-sidebar"
          style={{ width: auditSidebarWidth }}
        >
          <div
            className="audit-sidebar-resizer"
            role="separator"
            aria-orientation="vertical"
            aria-label="Resize audit log panel"
            aria-valuemin={AUDIT_SIDEBAR_MIN}
            aria-valuemax={auditSidebarMaxWidth()}
            aria-valuenow={auditSidebarWidth}
            data-testid="audit-sidebar-resizer"
            onMouseDown={startAuditSidebarResize}
          />
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
          <p className="audit-legend" data-testid="audit-legend">
            <span className="audit-legend-item">
              <span
                className="audit-legend-swatch audit-legend-swatch--alteration"
                aria-hidden
              />
              Alterations — accepted cell fixes
            </span>
            <span className="audit-legend-item">
              <span
                className="audit-legend-swatch audit-legend-swatch--download"
                aria-hidden
              />
              Downloads — CSV exports
            </span>
            <span className="audit-legend-utc">Times shown in UTC</span>
          </p>
          <div className="audit-filters" role="group" aria-label="Filter audit log">
            {(
              [
                ["all", "All"],
                ["alteration", "Alterations"],
                ["download", "Downloads"],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                type="button"
                className={`audit-filter-btn${auditFilter === value ? " is-active" : ""}`}
                data-testid={`audit-filter-${value}`}
                aria-pressed={auditFilter === value}
                onClick={() => setAuditFilter(value)}
              >
                {label}
              </button>
            ))}
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
                {auditFilter === "alteration"
                  ? "No alterations yet"
                  : auditFilter === "download"
                    ? "No downloads yet"
                    : "No activity yet"}
              </p>
            ) : auditFilter === "alteration" ? (
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
                  {auditEntries.map((e) => {
                    if (e.kind !== "alteration") return null;
                    return (
                      <tr
                        key={e.id}
                        className="audit-row-alteration"
                        data-testid="audit-row"
                        data-audit-kind="alteration"
                      >
                        <td>{formatUtcDateTime(e.created_at)}</td>
                        <td>{patternShort(e.pattern)}</td>
                        <td>{e.dataset_row_id.slice(0, 8)}…</td>
                        <td>{e.period}</td>
                        <td>{formatCell(e.value_before)}</td>
                        <td>{formatCell(e.value_after)}</td>
                      </tr>
                    );
                  })}
                  {auditLoadingMore ? (
                    <tr>
                      <td colSpan={6}>Loading more…</td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            ) : auditFilter === "download" ? (
              <table className="data" data-testid="audit-table">
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Export</th>
                    <th>Snapshot</th>
                  </tr>
                </thead>
                <tbody>
                  {auditEntries.map((e) => {
                    if (e.kind !== "download") return null;
                    return (
                      <tr
                        key={e.id}
                        className="audit-row-download"
                        data-testid="audit-row"
                        data-audit-kind="download"
                      >
                        <td>{formatUtcDateTime(e.created_at)}</td>
                        <td>#{e.export_number}</td>
                        <td>
                          {e.audit_entry_count === 0
                            ? "Before any alterations"
                            : `After ${e.audit_entry_count} alteration${e.audit_entry_count === 1 ? "" : "s"}`}
                        </td>
                      </tr>
                    );
                  })}
                  {auditLoadingMore ? (
                    <tr>
                      <td colSpan={3}>Loading more…</td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            ) : (
              <table className="data" data-testid="audit-table">
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Type</th>
                    <th>Pattern</th>
                    <th>Row</th>
                    <th>Period</th>
                    <th>Before</th>
                    <th>After</th>
                  </tr>
                </thead>
                <tbody>
                  {auditEntries.map((e) =>
                    e.kind === "download" ? (
                      <tr
                        key={e.id}
                        className="audit-row-download"
                        data-testid="audit-row"
                        data-audit-kind="download"
                      >
                        <td>{formatUtcDateTime(e.created_at)}</td>
                        <td>Download</td>
                        <td colSpan={5}>
                          Export #{e.export_number}
                          {e.audit_entry_count === 0
                            ? " · before any alterations"
                            : ` · after ${e.audit_entry_count} alteration${e.audit_entry_count === 1 ? "" : "s"}`}
                        </td>
                      </tr>
                    ) : (
                      <tr
                        key={e.id}
                        className="audit-row-alteration"
                        data-testid="audit-row"
                        data-audit-kind="alteration"
                      >
                        <td>{formatUtcDateTime(e.created_at)}</td>
                        <td>Alteration</td>
                        <td>{patternShort(e.pattern)}</td>
                        <td>{e.dataset_row_id.slice(0, 8)}…</td>
                        <td>{e.period}</td>
                        <td>{formatCell(e.value_before)}</td>
                        <td>{formatCell(e.value_after)}</td>
                      </tr>
                    ),
                  )}
                  {auditLoadingMore ? (
                    <tr>
                      <td colSpan={7}>Loading more…</td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            )}
            {auditEntries.length > 0 &&
            auditEntries.length >= auditTotal ? (
              <p className="list-end-marker">
                End of log — all {auditTotal}{" "}
                {auditTotal === 1 ? "event" : "events"} loaded
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
