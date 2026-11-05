// Web walkthrough W01–W08 (spec §17.14.4): one screenshot per step at `${WALK_OUT}/<flow>/<step>.png`, in the
// language APP_LANG. A step that needs something this laptop does not have (a staff session with TOTP, the
// officer console, the LLM) is skipped, and scripts/check_coverage.py lists it as a gap — never faked.
//   WALK_OUT=… APP_LANG=ml-IN pnpm exec playwright test e2e/web/walkthrough.spec.ts
//   TY_SESSIONS=<sessions.json> adds the signed-in family flow (W07); TY_STAFF_SESSION the staff flows.
import { mkdirSync, readFileSync } from "node:fs";
import path from "node:path";

import { expect, type Page, test } from "@playwright/test";

const OUT = process.env.WALK_OUT ?? "test-results/walkthrough";
const LANG = process.env.APP_LANG ?? "en-IN";
const sessions = process.env.TY_SESSIONS
  ? (JSON.parse(readFileSync(process.env.TY_SESSIONS, "utf-8")) as Record<string, unknown> & { storageKey: string })
  : null;

test.use({ video: "on" });

async function shot(page: Page, flow: string, step: string) {
  const dir = path.join(OUT, flow);
  mkdirSync(dir, { recursive: true });
  await page.waitForTimeout(600); // let animations settle
  await page.screenshot({ path: path.join(dir, `${step}.png`) });
}

async function prefs(page: Page, lang: string, who?: "fisher" | "family") {
  await page.addInitScript(
    ([key, session, p]) => {
      if (key && session) localStorage.setItem(key as string, JSON.stringify(session));
      localStorage.setItem("ty.prefs.v1", p as string);
    },
    [
      who && sessions ? sessions.storageKey : null,
      who && sessions ? sessions[who] : null,
      JSON.stringify({ lang, harbour: "rameswaram", boatKind: "small_frp", mode: "simple", onboarded: true, alertsOn: false }),
    ],
  );
}

async function visible(page: Page, testId: string, timeout = 15_000): Promise<boolean> {
  return page
    .getByTestId(testId)
    .first()
    .waitFor({ state: "visible", timeout })
    .then(() => true)
    .catch(() => false);
}

test("W01 public verdict without login", async ({ page }) => {
  await prefs(page, LANG);
  await page.goto("/");
  await expect(page.getByTestId("verdict-card")).toBeVisible({ timeout: 120_000 });
  await shot(page, "W01-public", "01-public-verdict");
  const manifest = await page.locator('link[rel="manifest"]').count();
  if (manifest) await shot(page, "W01-public", "02-install"); // installable: the page links its web app manifest
});

test("W02 staff sign-in", async ({ page }) => {
  await prefs(page, LANG);
  await page.goto("/admin");
  await page.waitForLoadState("networkidle");
  await shot(page, "W02-staff-sign-in", "01-sign-in");
  // 02-totp / 03-signed-in need a staff test account with a seeded TOTP secret (TY_STAFF_SESSION): a gap until then.
});

test("W03 expert console", async ({ page }) => {
  await prefs(page, LANG);
  await page.goto("/expert");
  await expect(page.getByTestId("sea-signal")).toBeVisible({ timeout: 120_000 });
  await shot(page, "W03-expert", "01-sea-signal");
  await expect(page.getByTestId("ledger")).toBeVisible();
  await shot(page, "W03-expert", "02-ledger");
  await page.getByTestId("ledger-row-H2").click();
  await shot(page, "W03-expert", "03-h2-buffer");
  if (await visible(page, "suggest-1", 5_000)) {
    await page.getByTestId("suggest-1").click(); // the agent answers and can move the map
    if (await visible(page, "expert-reply", 150_000)) {
      await shot(page, "W03-expert", "05-fly-to");
      const chip = page.locator('[data-testid^="citation-K"]').first();
      if (await chip.isVisible().catch(() => false)) {
        await chip.click();
        await shot(page, "W03-expert", "04-citations");
        await page.getByTestId("citation-close").click().catch(() => undefined);
      }
    }
  }
  if (await visible(page, "mission-control", 5_000)) await shot(page, "W03-expert", "06-mission-control");
  await page.getByTestId("depart-slider").fill("12");
  await shot(page, "W03-expert", "07-drag-departure");
});

test("W04 analyst tools", async ({ page }) => {
  await prefs(page, LANG);
  await page.goto("/expert");
  await expect(page.getByTestId("sea-signal")).toBeVisible({ timeout: 120_000 });
  await page.getByTestId("analyst-toggle").click().catch(() => undefined);
  if (!(await visible(page, "analyst-panel", 10_000))) return; // needs an analyst session with aal2: a gap
  await shot(page, "W04-analyst", "01-anomaly");
  if (await visible(page, "pfz-overlap", 5_000)) await shot(page, "W04-analyst", "02-overlap");
  if (await visible(page, "downloads", 5_000)) await shot(page, "W04-analyst", "03-downloads");
  if (await visible(page, "kb-browser", 5_000)) await shot(page, "W04-analyst", "04-kb-browser");
});

test("W05 officer console", async () => {
  // The officer console (warning areas, broadcasts) is not built yet: every W05 screenshot is a reported gap.
  test.skip(true, "officer console not built");
});

test("W06 admin console", async ({ page }) => {
  await prefs(page, LANG);
  await page.goto("/admin");
  if (!(await visible(page, "admin-tab-overview", 10_000))) return; // needs platform_admin with aal2: a gap
  // The admin console's tabs (AdminScreen.web.tsx). AI usage, system health and languages have no tab yet: gaps.
  const tabs: [string, string][] = [
    ["overview", "01-overview"], ["sources", "02-data-sources"], ["kb", "03-knowledge-base"],
    ["alerts", "05-alerts"], ["switches", "07-kill-switches"], ["guardrails", "08-guardrails"],
    ["replay", "09-replay"], ["users", "10-users"], ["live", "11-live-map"], ["audit", "12-audit"],
  ];
  for (const [tab, step] of tabs) {
    const t = page.getByTestId(`admin-tab-${tab}`);
    if (await t.isVisible().catch(() => false)) {
      await t.click();
      await shot(page, "W06-admin", step);
    }
  }
});

test("W07 family on the web", async ({ page }) => {
  test.skip(!sessions, "set TY_SESSIONS for the signed-in family flow");
  await prefs(page, LANG, "family");
  await page.goto("/me");
  await expect(page.locator('[data-testid^="family-boat-"]').first()).toBeVisible({ timeout: 60_000 });
  await shot(page, "W07-family-web", "01-family-web");
  if (await visible(page, "alerts-on", 5_000)) await shot(page, "W07-family-web", "02-push-opt-in");
  await page.goto("/alerts");
  await expect(page.getByTestId("alerts-screen")).toBeVisible();
  await shot(page, "W07-family-web", "03-alert-card");
});

test("W08 right-to-left and 200 % zoom", async ({ page }) => {
  await prefs(page, "ur-IN"); // Urdu: the first right-to-left language (draft)
  await page.goto("/");
  await expect(page.getByTestId("verdict-card")).toBeVisible({ timeout: 120_000 });
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await shot(page, "W08-accessibility", "01-rtl");
  await prefs(page, LANG);
  await page.goto("/");
  await expect(page.getByTestId("verdict-card")).toBeVisible({ timeout: 120_000 });
  await page.evaluate(() => {
    document.documentElement.style.zoom = "2";
  });
  await shot(page, "W08-accessibility", "02-zoom-200");
});
