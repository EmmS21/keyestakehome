import { expect, test } from "@playwright/test";

import { goToWorkspace, openNegativesTab, requireBackend } from "./helpers";

test.describe("Cleaning Workspace", () => {
  test("workspace-loads-idle-with-pattern-badges", async ({ page, request }) => {
    const { fileName } = await goToWorkspace(page, request);

    await expect(page.getByTestId("workspace-explorer-link")).toBeVisible();
    await expect(page.getByTestId("workspace-dataset-name")).toContainText(
      fileName,
    );
    await expect(page.getByTestId("workspace-idle-prompt")).toHaveText(
      /Select an anomaly to review/,
    );
    await expect(page.getByTestId("compare-area")).toHaveCount(0);
    await expect(page.getByTestId("submit-button")).toHaveCount(0);

    await expect(page.getByTestId("pattern-tab-negatives")).not.toHaveClass(
      /active/,
    );
    await expect(page.getByTestId("pattern-badge-negatives")).toHaveText("4");
    await expect(page.getByTestId("pattern-badge-refunds")).toHaveText("2");
    await expect(page.getByTestId("pattern-badge-double_booking")).toHaveText(
      "1",
    );
  });

  test("workspace-opens-pattern-with-compare-tables", async ({
    page,
    request,
  }) => {
    await goToWorkspace(page, request);
    await openNegativesTab(page);

    await expect(page.getByTestId("pattern-tab-negatives")).toHaveClass(
      /active/,
    );
    await expect(page.getByTestId("pattern-header")).toContainText(
      /Negative values/,
    );
    await expect(page.getByTestId("pattern-header")).toContainText(
      /4 rows with issues/,
    );
    await expect(page.getByTestId("before-table")).toBeVisible();
    await expect(page.getByTestId("after-table")).toBeVisible();
    await expect(page.getByTestId("proposal-checkbox").first()).toBeVisible();
    await expect(
      page.getByTestId("after-table").getByRole("checkbox"),
    ).toHaveCount(0);
    await expect(page.getByTestId("submit-button")).toBeVisible();
  });

  test("workspace-submit-with-no-selection-shows-nothing-changed", async ({
    page,
    request,
  }) => {
    await goToWorkspace(page, request);
    await openNegativesTab(page);

    await page.getByTestId("submit-button").click();

    await expect(page.getByTestId("toast-message")).toHaveText(
      "Nothing changed",
    );
    await expect(page.getByTestId("compare-area")).toHaveCount(0);
    await expect(page.getByTestId("pattern-tab-negatives")).not.toHaveClass(
      /active/,
    );
  });

  test("workspace-submit-applies-changes-and-refreshes-counts", async ({
    page,
    request,
  }) => {
    await goToWorkspace(page, request);
    await openNegativesTab(page);

    await page.getByTestId("proposal-checkbox").first().check();
    await page.getByTestId("submit-button").click();

    await expect(page.getByTestId("toast-message")).toHaveText(
      /Applied 1 change/,
    );
    await expect(page.getByTestId("compare-area")).toHaveCount(0);
    await expect(page.getByTestId("pattern-tab-negatives")).not.toHaveClass(
      /active/,
    );
    await expect(page.getByTestId("pattern-badge-negatives")).toHaveText("3");

    await openNegativesTab(page);
    await expect(page.getByTestId("pattern-header")).toContainText(
      /3 rows with issues/,
    );
  });

  test("workspace-restores-checkbox-selection-after-refresh", async ({
    page,
    request,
  }) => {
    await goToWorkspace(page, request);
    await openNegativesTab(page);

    const checkbox = page.getByTestId("proposal-checkbox").first();
    await checkbox.check();
    const proposalId = await checkbox.getAttribute("data-proposal-id");
    expect(proposalId).toBeTruthy();

    await page.reload();
    await expect(page.getByTestId("workspace-idle-prompt")).toBeVisible();

    await openNegativesTab(page);
    await expect(
      page.locator(`[data-proposal-id="${proposalId}"]`),
    ).toBeChecked();
  });

  test("workspace-shows-empty-state-when-pattern-has-no-issues", async ({
    page,
    request,
  }) => {
    test.setTimeout(60_000);
    await goToWorkspace(page, request);
    await openNegativesTab(page);

    await page.getByTestId("select-all-button").click();
    await page.getByTestId("submit-button").click();
    await expect(page.getByTestId("toast-message")).toHaveText(
      /Applied \d+ change(s)?/,
    );
    await expect(page.getByTestId("pattern-badge-negatives")).toHaveText("0", {
      timeout: 10000,
    });

    await openNegativesTab(page);
    await expect(page.getByTestId("pattern-empty-message")).toHaveText(
      /Nothing to clean for this pattern/,
    );
    await expect(page.getByTestId("submit-button")).toHaveCount(0);
  });

  test("workspace-audit-empty-then-shows-entries-after-accept", async ({
    page,
    request,
  }) => {
    await goToWorkspace(page, request);

    await page.getByTestId("audit-toggle").click();
    await expect(page.getByTestId("audit-sidebar")).toBeVisible();
    await expect(page.getByTestId("audit-empty")).toHaveText(/No changes yet/);

    await page.getByTestId("audit-toggle").click();
    await openNegativesTab(page);
    await page.getByTestId("proposal-checkbox").first().check();
    await page.getByTestId("submit-button").click();
    await expect(page.getByTestId("toast-message")).toHaveText(
      /Applied 1 change/,
    );

    await page.getByTestId("audit-toggle").click();
    await expect(page.getByTestId("audit-table")).toBeVisible();
    await expect(page.getByTestId("audit-row").first()).toBeVisible();
  });

  test("workspace-invalid-dataset-redirects-to-explorer", async ({
    page,
    request,
  }) => {
    await requireBackend(request);
    await page.goto(
      "/clean/00000000-0000-0000-0000-000000000000",
    );
    await expect(page).toHaveURL("/");
    await expect(page.getByTestId("explorer-title")).toBeVisible();
  });
});
