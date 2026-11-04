// Expert chat through ty-copilot → ty-agent (Gemini). Tagged @llm: run on the laptop with `pnpm e2e:web --grep @llm`.
import { expect, test } from "@playwright/test";

test("@llm agent answers, Mission Control ticks and the map follows", async ({ page }) => {
  await page.goto("/expert");
  await expect(page.getByTestId("sea-signal")).toBeVisible();
  await page.getByTestId("suggest-0").click(); // "Can a small fibre boat go out tomorrow morning?"
  const reply = page.getByTestId("expert-reply").first();
  await expect(reply).toBeVisible({ timeout: 120_000 });
  await expect(reply).toContainText("Advisory only");
  await expect(page.getByTestId("mission-yukti")).toContainText("✓");
  await expect(page.getByTestId("mission-language")).toContainText("✓");
  await expect(page.getByTestId("ledger")).toBeVisible(); // openLedger ran (Expert mode)
  await page.screenshot({ path: "test-results/expert-05-chat.png" });
});
