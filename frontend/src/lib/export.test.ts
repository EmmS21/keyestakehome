import { describe, expect, it } from "vitest";

import { exportDownloadFilename, getExportUrl } from "./export";

describe("export helpers", () => {
  it("builds export URL from api base and dataset id", () => {
    expect(getExportUrl("http://127.0.0.1:8000", "abc-123")).toBe(
      "http://127.0.0.1:8000/datasets/abc-123/export",
    );
    expect(getExportUrl("http://127.0.0.1:8000/", "abc-123")).toBe(
      "http://127.0.0.1:8000/datasets/abc-123/export",
    );
  });

  it("ensures download filename ends with .csv", () => {
    expect(exportDownloadFilename("deal.csv")).toBe("deal.csv");
    expect(exportDownloadFilename("deal")).toBe("deal.csv");
    expect(exportDownloadFilename("  ")).toBe("export.csv");
  });
});
