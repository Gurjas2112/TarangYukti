// Signed-in flows (Milestone 8) with the dev test accounts: the fisher's Trip tab and family sharing, and the family
// member's boat card. Dev only — needs TY_SESSIONS (a JSON file of Supabase sessions for ty-test-fisher@ and
// ty-test-family@example.com, minted locally through the admin API) and a trip already posted by sim_boat.py.
import { readFileSync } from "node:fs";

import { expect, type Page, test } from "@playwright/test";

const file = process.env.TY_SESSIONS;
const sessions = file ? (JSON.parse(readFileSync(file, "utf-8")) as Record<string, unknown> & { storageKey: string }) : null;

test.skip(!sessions, "set TY_SESSIONS to run the signed-in flows");

async function signIn(page: Page, who: "fisher" | "family") {
  await page.addInitScript(
    ([key, session, prefs]) => {
      localStorage.setItem(key as string, JSON.stringify(session));
      localStorage.setItem("ty.prefs.v1", prefs as string);
    },
    [
      sessions!.storageKey,
      sessions![who],
      JSON.stringify({ lang: "en-IN", harbour: "rameswaram", boatKind: "small_frp", mode: "simple", onboarded: true, alertsOn: false }),
    ],
  );
}

test("fisher: trip history, right-on count and family sharing", async ({ page }) => {
  await signIn(page, "fisher");
  await page.goto("/trip");
  await expect(page.getByTestId("trip-screen")).toBeVisible();
  await expect(page.getByTestId("trip-none")).toContainText("Back at harbour at");
  await expect(page.getByTestId("trip-right-on")).toContainText(/Right on \d+ of the last \d+ days/);
  await page.screenshot({ path: "test-results/trip-01-fisher.png" });

  await page.goto("/me");
  await expect(page.getByTestId("family-sharing")).toBeVisible();
  await expect(page.getByTestId("family-sharing")).toContainText("ty-test-family@example.com");
  await page.screenshot({ path: "test-results/trip-02-sharing.png", fullPage: true });
});

test("family: shared boat card shows back at harbour", async ({ page }) => {
  await signIn(page, "family");
  await page.goto("/me");
  const boat = page.locator('[data-testid^="family-boat-"]').first();
  await expect(boat).toBeVisible();
  await boat.click();
  await expect(page.getByTestId("family-status")).toContainText(/Back at Rameswaram at|At sea since/);
  await page.screenshot({ path: "test-results/trip-03-family-card.png" });
});
