import { expect, test } from "@playwright/test";
import type { Download } from "@playwright/test";

// Explicit opt-in: these checks use the deployed database and real Claude billing.
// No uploads or repository writes. Run separately from the recorded-contract suite.
test.skip(process.env.UNTANGLE_LIVE_TESTS !== "1", "Set UNTANGLE_LIVE_TESTS=1 and E2E_BASE_URL to a live deployment.");
test.setTimeout(180_000);

async function downloadedText(download: Download) {
  const stream = await download.createReadStream();
  const parts: Buffer[] = [];
  for await (const part of stream!) parts.push(Buffer.from(part));
  return Buffer.concat(parts).toString();
}

test("live graph, decision workbench and risk exports", async ({ page, request }, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  const response = await request.get("/api/health");
  expect(response.ok()).toBe(true);
  const health = await response.json();
  expect(health.ok).toBe(true);
  expect(health.llm.backend).toBe("anthropic");
  expect(health.embed.backend).toBe("fastembed");

  await page.goto("/dashboard");
  await expect(page.getByLabel("Repository", { exact: true })).toHaveValue("PDGamerSG/Untangle", { timeout: 30_000 });
  await page.getByRole("link", { name: /Explore decision history/ }).click();
  const details = page.getByRole("region", { name: "Selected decision" });
  await expect(details).toBeVisible({ timeout: 30_000 });
  const subject = await details.getByRole("heading", { level: 3 }).innerText();
  await page.getByLabel("Filter decisions", { exact: true }).fill(subject);
  await expect(details.getByRole("heading", { level: 3 })).toHaveText(subject);
  const decisionDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export view", exact: true }).click();
  const decisions = await downloadedText(await decisionDownload);
  expect(decisions).toContain("Repository: PDGamerSG/Untangle");
  expect(decisions).toContain("# Untangle decision brief");
  expect(decisions).toContain("/decisions/");
  await page.screenshot({ path: testInfo.outputPath("live-workbench.png"), fullPage: true });
  await details.getByRole("link", { name: "Open evidence path", exact: true }).click();
  await expect(page).toHaveURL(/\/decisions\//);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Could not load the decision", { exact: true })).toHaveCount(0);

  await page.goto("/pulse");
  await expect(page.locator("article[data-risk]").first()).toBeVisible({ timeout: 30_000 });
  await page.getByLabel("Filter risks", { exact: true }).fill("no-such-decision-untangle-smoke");
  await expect(page.getByText("No risks match these filters.", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Clear risk filters", exact: true }).click();
  const riskDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export risks", exact: true }).click();
  const risks = await downloadedText(await riskDownload);
  expect(risks).toContain("# Untangle risk brief");
  expect(risks).toContain("Repository: PDGamerSG/Untangle");
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("live-pulse-phone.png"), fullPage: true });
  expect(errors).toEqual([]);
});

test("live Claude answers with citations and compares against vector retrieval", async ({ page }) => {
  await page.goto("/ask");
  await expect(page.getByLabel("Repository", { exact: true })).toHaveValue("PDGamerSG/Untangle", { timeout: 30_000 });
  await page.getByLabel("Your question", { exact: true }).fill("why do we use neo4j in pyproject.toml?");
  await page.getByLabel("Compare with vector-only search").check();
  const response = page.waitForResponse(res => new URL(res.url()).pathname === "/api/ask" && res.request().method() === "POST");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  const result = await response;
  expect(result.ok()).toBe(true);
  const answer = await result.json();
  expect(answer.why.llm.used).toBe(true);
  expect(Object.keys(answer.citations).length).toBeGreaterThan(0);
  expect(answer.baseline).not.toBeNull();
  await expect(page.getByText("Answer ready.", { exact: true })).toBeAttached();
});

test("live feature map traces commits and downloads an Obsidian vault", async ({ page, request }, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  const response = await request.get("/api/repository-map?repo=PDGamerSG%2FUntangle&limit=40");
  expect(response.ok()).toBe(true);
  const data = await response.json();
  expect(data.features.length).toBeGreaterThanOrEqual(8);
  expect(data.imports.length).toBeGreaterThan(100);
  expect(data.total_commits).toBeGreaterThan(1);
  if (process.env.UNTANGLE_EXPECT_MAP_SHA) expect(data.head_sha).toBe(process.env.UNTANGLE_EXPECT_MAP_SHA);
  await page.goto("/map");
  const graph = page.getByRole("group", { name: "Repository graph", exact: true });
  await expect(graph.getByRole("button", { name: "Feature Ask & evidence", exact: true })).toBeVisible({ timeout: 30_000 });
  await page.screenshot({ path: testInfo.outputPath("live-feature-map.png"), fullPage: true });
  await graph.getByRole("button", { name: "Feature Ask & evidence", exact: true }).click();
  await expect(page.getByRole("region", { name: "Graph inspector" })).toContainText("Entry points");
  await page.getByRole("button", { name: `Inspect commit ${data.commits[0].sha.slice(0, 7)}`, exact: true }).click();
  await expect(page.getByRole("region", { name: "Graph inspector" })).toContainText("No revert has been run");
  await page.screenshot({ path: testInfo.outputPath("live-commit-impact.png"), fullPage: true });
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "Export to Obsidian", exact: true }).click();
  const vault = await download;
  await vault.saveAs(testInfo.outputPath("untangle-obsidian.zip"));
  expect(await vault.failure()).toBeNull();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("live-commit-impact-phone.png"), fullPage: true });
  expect(errors).toEqual([]);
});
