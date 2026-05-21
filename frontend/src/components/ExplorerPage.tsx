"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  ApiError,
  type DatasetSummary,
  datasetHasAuditChanges,
  downloadDatasetExport,
  listDatasets,
  uploadDataset,
} from "@/lib/api";
import { changeStatusLabel, formatUploadedAt } from "@/lib/format";

import { ErrorBanner } from "./ErrorBanner";

type LoadState = "loading" | "ready" | "error";

type DatasetRow = DatasetSummary & { hasChanges?: boolean };

export function ExplorerPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const listFetchIdRef = useRef(0);
  const [datasets, setDatasets] = useState<DatasetRow[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [listError, setListError] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [exportingId, setExportingId] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  const loadChangeStatus = useCallback(async (rows: DatasetSummary[]) => {
    const statuses = await Promise.all(
      rows.map(async (d) => {
        try {
          const hasChanges = await datasetHasAuditChanges(d.id);
          return { id: d.id, hasChanges };
        } catch {
          return { id: d.id, hasChanges: false };
        }
      }),
    );
    setDatasets((prev) =>
      prev.map((d) => ({
        ...d,
        hasChanges:
          statuses.find((s) => s.id === d.id)?.hasChanges ?? false,
      })),
    );
  }, []);

  const fetchDatasets = useCallback(async () => {
    const fetchId = ++listFetchIdRef.current;
    setLoadState("loading");
    setListError(null);
    try {
      const rows = await listDatasets();
      if (fetchId !== listFetchIdRef.current) return;
      setDatasets(rows);
      setLoadState("ready");
      void loadChangeStatus(rows);
    } catch (err) {
      if (fetchId !== listFetchIdRef.current) return;
      setLoadState("error");
      setListError(
        err instanceof ApiError ? err.message : "Could not load datasets",
      );
    }
  }, [loadChangeStatus]);

  useEffect(() => {
    fetchDatasets();
  }, [fetchDatasets]);

  const openFilePicker = () => fileInputRef.current?.click();

  const handleFile = async (file: File | undefined) => {
    if (!file) return;
    setUploadError(null);

    if (datasets.some((d) => d.name === file.name)) {
      setUploadError(
        `"${file.name}" is already uploaded. Open that dataset or use a different file name.`,
      );
      return;
    }

    listFetchIdRef.current += 1;
    setUploading(true);
    try {
      const created = await uploadDataset(file);
      setDatasets((prev) => [{ ...created, hasChanges: false }, ...prev]);
      setLoadState("ready");
    } catch (err) {
      if (err instanceof ApiError) {
        setUploadError(err.message);
      } else {
        setUploadError("Upload failed. Check your connection and try again.");
      }
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleExport = async (dataset: DatasetRow) => {
    setExportError(null);
    setExportingId(dataset.id);
    try {
      await downloadDatasetExport(dataset.id, dataset.name);
    } catch (err) {
      setExportError(
        err instanceof ApiError ? err.message : "Export failed. Try again.",
      );
    } finally {
      setExportingId(null);
    }
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (uploading || loadState === "loading") return;
    void handleFile(e.dataTransfer.files[0]);
  };

  const isEmpty = loadState === "ready" && datasets.length === 0;
  const showTable = loadState === "ready" && datasets.length > 0;

  return (
    <>
      <header className="app-header">
        <h1 className="app-title" data-testid="explorer-title">
          Data Cleaning Tool
        </h1>
      </header>

      {listError ? (
        <ErrorBanner message={listError} onRetry={fetchDatasets} />
      ) : null}
      {uploadError ? <ErrorBanner message={uploadError} /> : null}
      {exportError ? <ErrorBanner message={exportError} /> : null}

      <div
        className={`upload-zone${uploading ? " loading" : ""}`}
        data-testid="upload-zone"
        onDragOver={(e) => e.preventDefault()}
        onDrop={onDrop}
        onClick={() => {
          if (!uploading && loadState !== "loading") openFilePicker();
        }}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            if (!uploading && loadState !== "loading") openFilePicker();
          }
        }}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,text/csv"
          hidden
          data-testid="upload-input"
          onChange={(e) => void handleFile(e.target.files?.[0])}
        />
        {uploading
          ? "Uploading…"
          : "[ Upload CSV ] or drag file here — .csv only"}
      </div>

      {loadState === "loading" ? (
        <p className="loading-indicator" data-testid="loading-indicator">
          Loading datasets…
        </p>
      ) : null}

      {isEmpty ? (
        <p className="empty-message" data-testid="explorer-empty-message">
          No datasets yet. Upload a deal file to begin.
        </p>
      ) : null}

      {showTable ? (
        <table className="data" data-testid="dataset-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Rows</th>
              <th>Uploaded</th>
              <th>Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {datasets.map((d) => (
              <tr key={d.id} data-testid="dataset-row" data-dataset-id={d.id}>
                <td>{d.name}</td>
                <td>{d.row_count.toLocaleString()}</td>
                <td>{formatUploadedAt(d.uploaded_at)}</td>
                <td data-testid="dataset-status">
                  {changeStatusLabel(d.hasChanges)}
                </td>
                <td className="explorer-actions">
                  <button
                    type="button"
                    className="btn btn-sm"
                    data-testid="export-button"
                    disabled={exportingId === d.id}
                    onClick={() => void handleExport(d)}
                  >
                    {exportingId === d.id ? "Exporting…" : "Export"}
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    data-testid="clean-button"
                    onClick={() => router.push(`/clean/${d.id}`)}
                  >
                    Clean
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </>
  );
}
