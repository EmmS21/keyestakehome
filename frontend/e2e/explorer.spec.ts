import { readFileSync, writeFileSync } from "fs";
import { basename, join } from "path";
import { test, expect } from "@playwright/test";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
const SAMPLE_CSV = join(__dirname, "../../data/sample.csv");

async function requireBackend(
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

function uniqueSampleCopy(): string {
  const content = readFileSync(SAMPLE_CSV, "utf-8");
  const path = join(__dirname, "fixtures", `e2e-${Date.now()}.csv`);
  writeFileSync(path, content);
  return path;
}

test.describe("File Explorer", () => {
  test("explorer-shows-empty-state", async ({ page }) => {
    await page.route("**/datasets", async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ datasets: [] }),
        });
        return;
      }
      await route.continue();
    });

    await page.goto("/");
    await expect(page.getByTestId("explorer-title")).toHaveText(
      "Data Cleaning Tool",
    );
    await expect(page.getByTestId("upload-zone")).toBeVisible();
    await expect(page.getByTestId("explorer-empty-message")).toHaveText(
      /No datasets yet/,
    );
    await expect(page.getByTestId("dataset-table")).toHaveCount(0);
    await expect(page.getByTestId("clean-button")).toHaveCount(0);
  });

  test("explorer-lists-datasets-after-upload", async ({ page, request }) => {
    await requireBackend(request);
    const filePath = uniqueSampleCopy();
    const fileName = basename(filePath);

    await page.goto("/");
    await page.getByTestId("upload-input").setInputFiles(filePath);

    await expect(page.getByTestId("dataset-table")).toBeVisible();
    await expect(page.getByRole("row", { name: new RegExp(fileName) })).toBeVisible();
    await expect(
      page.getByRole("row", { name: new RegExp(fileName) }).getByTestId("dataset-status"),
    ).toHaveText("Unchanged");
    await expect(page.getByTestId("clean-button").first()).toBeEnabled();
    await expect(page.getByTestId("explorer-empty-message")).toHaveCount(0);
  });

  test("explorer-navigates-to-cleaning-workspace", async ({ page, request }) => {
    await requireBackend(request);
    const filePath = uniqueSampleCopy();

    await page.goto("/");
    await page.getByTestId("upload-input").setInputFiles(filePath);
    await page
      .getByRole("row", { name: new RegExp(basename(filePath)) })
      .getByTestId("clean-button")
      .click();

    await expect(page).toHaveURL(/\/clean\/[0-9a-f-]{36}$/i);
    await expect(page.getByTestId("workspace-shell")).toBeVisible();
  });
});
