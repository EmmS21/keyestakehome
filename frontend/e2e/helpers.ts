import { readFileSync, writeFileSync } from "fs";
import { basename, join } from "path";
import { expect, test, type Page } from "@playwright/test";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
export const SAMPLE_CSV = join(__dirname, "../../data/sample.csv");

/** Escape a string for use inside `new RegExp(...)`. */
export function escapeRegex(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export async function requireBackend(
  request: import("@playwright/test").APIRequestContext,
) {
  try {
    const res = await request.get(`${API_URL}/health`);
    if (!res.ok()) {
      test.skip(true, "Backend not running at " + API_URL);
    }
  } catch {
    test.skip(true, "Backend not running at " + API_URL);
  }
}

/** Dataset table row containing the given file name. */
export function datasetRow(page: Page, fileName: string) {
  return page.getByTestId("dataset-row").filter({ hasText: fileName });
}

export function uniqueSampleCopy(): string {
  const content = readFileSync(SAMPLE_CSV, "utf-8");
  const path = join(
    __dirname,
    "fixtures",
    `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}.csv`,
  );
  writeFileSync(path, content);
  return path;
}

/** Upload sample CSV on explorer and open cleaning workspace. */
export async function goToWorkspace(
  page: Page,
  request: import("@playwright/test").APIRequestContext,
) {
  await requireBackend(request);
  const filePath = uniqueSampleCopy();
  const fileName = basename(filePath);

  await page.goto("/");
  await page.getByTestId("upload-input").setInputFiles(filePath);
  await expect(page.getByTestId("upload-zone")).not.toHaveClass(/loading/, {
    timeout: 20_000,
  });
  await expect(page.getByTestId("error-banner")).toHaveCount(0);
  const row = datasetRow(page, fileName);
  await expect(row).toBeVisible({ timeout: 15_000 });
  await row.getByTestId("clean-button").click();

  await expect(page).toHaveURL(/\/clean\/[0-9a-f-]{36}$/i, { timeout: 15_000 });
  await expect(page.getByTestId("workspace-shell")).toBeVisible();
  await expect(page.getByTestId("pattern-badge-negatives")).toHaveText("4", {
    timeout: 15_000,
  });

  return { fileName, filePath };
}

export async function openNegativesTab(page: Page) {
  await page.getByTestId("pattern-tab-negatives").click();
  await expect(page.getByTestId("compare-area")).toBeVisible();
}

export type PatternBadges = Record<
  "negatives" | "refunds" | "double_booking",
  string
>;

/** Sidebar badge counts after the workspace has finished loading counts. */
export async function readPatternBadges(page: Page): Promise<PatternBadges> {
  return {
    negatives: await page.getByTestId("pattern-badge-negatives").innerText(),
    refunds: await page.getByTestId("pattern-badge-refunds").innerText(),
    double_booking: await page
      .getByTestId("pattern-badge-double_booking")
      .innerText(),
  };
}

export async function expectPatternBadges(
  page: Page,
  expected: PatternBadges,
  options?: { timeout?: number },
) {
  const timeout = options?.timeout ?? 5_000;
  await expect(page.getByTestId("pattern-badge-negatives")).toHaveText(
    expected.negatives,
    { timeout },
  );
  await expect(page.getByTestId("pattern-badge-refunds")).toHaveText(
    expected.refunds,
    { timeout },
  );
  await expect(page.getByTestId("pattern-badge-double_booking")).toHaveText(
    expected.double_booking,
    { timeout },
  );
}
