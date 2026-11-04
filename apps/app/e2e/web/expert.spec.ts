// Hero flow (Milestone 7): Expert console → Sea Signal → ledger (open by default) → H2 border buffer → layers →
// drag the departure → analyst tools. Uses the live data services; no LLM.
import { expect, test } from "@playwright/test";

test("expert console hero flow", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto("/expert");

  const signal = page.getByTestId("sea-signal");
  await expect(signal).toBeVisible();
  await expect(signal).toContainText(/GO|CAUTION|NO-GO/);
  await expect(page.getByTestId("ledger")).toBeVisible();
  for (const id of ["H1", "H2", "H5", "H8", "S3"]) await expect(page.getByTestId(`ledger-row-${id}`)).toBeVisible();
  await expect(page.getByTestId("ledger-row-H2")).toContainText("limit");
  await expect(page.locator("canvas.maplibregl-canvas")).toBeVisible();
  await page.screenshot({ path: "test-results/expert-01-sea-signal.png" });

  // tapping H2 draws the border buffer
  await page.getByTestId("ledger-row-H2").click();
  await expect(page.getByTestId("layer-imblBuffer")).toBeChecked();
  await page.screenshot({ path: "test-results/expert-02-h2-buffer.png" });

  // layers toggle
  await page.getByTestId("layer-chl").check();
  await expect(page.getByTestId("layer-chl")).toBeChecked();

  // drag the departure: the plan is re-evaluated for that time
  const before = await page.getByTestId("depart-label").textContent();
  await page.getByTestId("depart-slider").fill("12");
  await expect(page.getByTestId("depart-label")).not.toHaveText(before ?? "");
  const hhmm = ((await page.getByTestId("depart-label").textContent()) ?? "").match(/\d{2}:\d{2}/)?.[0];
  await expect(signal).toContainText(`Depart ${hhmm}`); // the plan was re-evaluated for that departure
  await page.screenshot({ path: "test-results/expert-03-depart.png" });

  // Mission Control toggle
  await expect(page.getByTestId("mission-control")).toBeVisible();
  await page.getByTestId("show-how").uncheck();
  await expect(page.getByTestId("mission-control")).toHaveCount(0);

  // analyst tools are for analysts/admins with MFA (Milestone 9): a public visitor sees the lock message
  await page.getByTestId("analyst-toggle").click();
  await expect(page.getByTestId("analyst-locked")).toBeVisible();
  await expect(page.getByTestId("analyst-panel")).toHaveCount(0);
  await page.screenshot({ path: "test-results/expert-04-analyst-locked.png", fullPage: true });

  expect(errors).toEqual([]);
});
