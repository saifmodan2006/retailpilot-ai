import { test, expect } from "@playwright/test";
import path from "node:path";
const apiBase = (process.env.E2E_API_URL ?? "") + "/api/v1";

test("complete Excel to MIS, approval, analyst and audit journey", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await page.screenshot({ path: "../docs/screenshots/landing.png", fullPage: true });
  await expect(
    page.getByRole("heading", { name: /From Retail Data to Better Decisions/ }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Start guided demo" }).first().click();
  await expect(
    page.getByRole("heading", { name: "Business overview" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Load demo data" }).first().click();
  await expect(page.getByRole("status")).toContainText(
    "Synthetic data loaded",
    { timeout: 150000 },
  );
  await expect(
    page.getByText("Revenue performance", { exact: true }),
  ).toBeVisible({ timeout: 90000 });
  await page.screenshot({
    path: "../docs/screenshots/overview.png",
    fullPage: true,
  });
  const before = await page.request.get(apiBase + "/analytics", {
    headers: {
      Authorization:
        "Bearer " +
        (await page.evaluate(() => localStorage.getItem("rp-token"))),
    },
  });
  const revenue = (await before.json()).metrics.revenue;
  await page
    .getByRole("link", { name: "Data import center", exact: true })
    .click();
  await page
    .getByLabel("Upload spreadsheet")
    .setInputFiles(path.resolve("../sample_data/sales_import.xlsx"));
  await expect(page.getByText("15 accepted", { exact: true })).toBeVisible();
  await expect(page.getByText("4 rejected", { exact: true })).toBeVisible();
  await expect(page.getByText("Unknown SKU", { exact: true })).toBeVisible();
  await page.screenshot({
    path: "../docs/screenshots/import-validation.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Import accepted rows", exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText(
    "Accepted rows imported",
  );
  const after = await page.request.get(apiBase + "/analytics", {
    headers: {
      Authorization:
        "Bearer " +
        (await page.evaluate(() => localStorage.getItem("rp-token"))),
    },
  });
  expect((await after.json()).metrics.revenue).toBeCloseTo(
    revenue + 15 * 3 * 1299 * 0.95,
    2,
  );
  await page
    .getByRole("link", { name: "Inventory intelligence", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Review", exact: true })
    .first()
    .click();
  await expect(page.getByRole("dialog")).toContainText(
    "Why this recommendation?",
  );
  await page.screenshot({
    path: "../docs/screenshots/recommendation.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Submit for approval" }).click();
  await page
    .getByRole("link", { name: "Approval center", exact: true })
    .click();
  await page.getByRole("button", { name: "Use demo manager" }).click();
  await page
    .getByLabel(/Decision reason/)
    .fill("Reviewed recent demand and supplier lead time.");
  await page.getByRole("button", { name: "Approve draft" }).click();
  await expect(
    page.getByText("Simulated Draft", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "../docs/screenshots/approval.png",
    fullPage: true,
  });
  await page
    .getByRole("link", { name: "MIS report builder", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Generate report", exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText("MIS report generated");
  await expect(
    page.getByRole("button", { name: "XLSX", exact: true }).first(),
  ).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "XLSX", exact: true }).first().click();
  expect((await download).suggestedFilename()).toMatch(/\.xlsx$/);
  await page.getByRole("link", { name: /AI business analyst/ }).click();
  await page
    .getByRole("button", { name: /What is our current inventory value/ })
    .click();
  await expect(page.getByText("Your answer, with the workings")).toBeVisible();
  await page.screenshot({
    path: "../docs/screenshots/analyst.png",
    fullPage: true,
  });
  await page
    .getByRole("link", { name: "Demand forecasting", exact: true })
    .click();
  await expect(page.getByText("Rolling backtest results")).toBeVisible();
  await page.screenshot({
    path: "../docs/screenshots/forecast.png",
    fullPage: true,
  });
  await page.getByRole("link", { name: "Audit logs", exact: true }).click();
  await expect(
    page.getByText("approval.approve", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("report.generated", { exact: true }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("mobile navigation, isolated empty state and landing", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.screenshot({
    path: "../docs/screenshots/landing-mobile.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Start guided demo" }).first().click();
  await expect(
    page.getByRole("heading", { name: "Meet your demo workspace" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page
    .getByRole("link", { name: "Data import center", exact: true })
    .click();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});
