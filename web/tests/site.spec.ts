import { expect, test } from "@playwright/test";
import repos from "../sample/repos.json";
import health from "../sample/health.json";
import meetings from "../sample/meetings.json";
import meeting from "../sample/meeting.json";
import answer from "../sample/ask/concurrency.json";
import refusal from "../sample/ask/refusal.json";
import pulse from "../sample/pulse.json";
import { sampleDecision, sampleTimeline } from "../src/lib/sample";

// Browser integration tests use recorded API contracts. Live service checks run separately.
const concurrencyKey = { id: "cfg:knadh/listmonk:schema.sql::app.concurrency", label: "ConfigKey", name: "app.concurrency", path: "schema.sql", key: "app.concurrency", score: 1 };

test.beforeEach(async ({ page }) => {
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const path = decodeURIComponent(url.pathname.slice(4));
    let body: unknown;
    if (path === "/health") body = health;
    else if (path === "/repos") body = repos;
    else if (path === "/pulse") body = pulse;
    else if (path === "/meetings") body = meetings;
    else if (path.startsWith("/meetings/")) body = meeting;
    else if (path === "/ask") {
      const request = route.request().postDataJSON();
      body = request.question.includes("MongoDB") ? refusal : { ...answer, baseline: request.mode === "both" ? answer.baseline : null };
    } else if (path === "/timeline") body = await sampleTimeline(url.searchParams.get("at") ?? new Date().toISOString());
    else if (path.startsWith("/decisions/")) body = await sampleDecision(path.slice(11));
    else if (path === "/kt/ingest") body = { meeting_id: meeting.id, utterances: 40, decisions: 15 };
    else if (path === "/stats") body = { nodes: 120, relationships: 300, labels: { Decision: 18, ConfigKey: 40, Commit: 62 }, relationship_types: { ABOUT: 30 } };
    else if (path === "/search") body = { entities: [concurrencyKey], people: [{ id: "person:gh:knadh", name: "Kailash Nadh", login: "knadh", score: 1 }] };
    else if (path.startsWith("/entities/")) {
      const why = await sampleDecision(answer.evidence_chain[0].id!);
      body = { entity: { ...concurrencyKey, file: { path: "schema.sql", id: "file:knadh/listmonk:schema.sql" } }, decisions: [why.decision], people: [], recent_commits: [] };
    }
    else throw new Error(`Unexpected API request: ${path}`);
    await route.fulfill({ json: body });
  });
});

test("landing assets load and the app opens", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", err => errors.push(err.message));
  await page.goto("/");
  await page.getByRole("link", { name: "Open app", exact: true }).click();
  await expect(page).toHaveURL(/\/ask$/);
  await expect(page.getByLabel("Repository", { exact: true })).toHaveValue("knadh/listmonk");
  expect(errors).toEqual([]);
});

test("new sessions prefer Untangle and preserve a subsequent repository choice", async ({ page }) => {
  await page.route("**/api/repos", route => route.fulfill({ json: [
    ...repos,
    { ...repos[0], full_name: "PDGamerSG/Untangle", url: "https://github.com/PDGamerSG/Untangle" },
  ] }));
  await page.goto("/ask");
  await expect(page.getByLabel("Repository", { exact: true })).toHaveValue("PDGamerSG/Untangle");
  await page.getByLabel("Repository", { exact: true }).selectOption("knadh/listmonk");
  await page.reload();
  await expect(page.getByLabel("Repository", { exact: true })).toHaveValue("knadh/listmonk");
});

test("ask, compare, inspect evidence and follow a decision", async ({ page }) => {
  await page.goto("/ask");
  await page.getByLabel("Your question", { exact: true }).fill("why is app.concurrency set the way it is?");
  await page.getByLabel("Compare with vector-only search").check();
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByText("Answer ready.", { exact: true })).toBeAttached();
  await page.getByText("Why this answer", { exact: true }).click();
  await expect(page.getByText("Cypher calls, in order")).toBeVisible();
  const link = page.locator('a[href^="/decisions/"]').first();
  await link.click();
  await expect(page).toHaveURL(/\/decisions\//);
  await expect(page.getByText("Could not load the decision")).toHaveCount(0);
  await page.getByRole("navigation", { name: "Breadcrumb" }).getByRole("link", { name: "Ask", exact: true }).click();
  await expect(page).toHaveURL(/\/ask$/);
});

test("missing decisions and pages return to Ask", async ({ page }) => {
  await page.route("**/api/decisions/missing", route => route.fulfill({ status: 404, json: { error: "No such decision" } }));
  await page.goto("/decisions/missing");
  await page.getByRole("link", { name: "Ask a question", exact: true }).click();
  await expect(page).toHaveURL(/\/ask$/);
  await page.goto("/missing-page");
  await page.getByRole("link", { name: "Ask page", exact: true }).click();
  await expect(page).toHaveURL(/\/ask$/);
});

test("unsupported questions show a refusal", async ({ page }) => {
  await page.goto("/ask");
  await page.getByLabel("Your question", { exact: true }).fill("why does listmonk use MongoDB?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByText("Answer ready.", { exact: true })).toBeAttached();
  await expect(page.getByRole("heading", { name: "Nothing in the graph answers this.", exact: true })).toBeVisible();
});

test("timeline date changes reach the API", async ({ page }) => {
  await page.goto("/timeline");
  const request = page.waitForRequest(req => req.url().includes("/api/timeline?") && req.url().includes("2020-01-01"));
  await page.getByLabel("Jump to", { exact: true }).fill("2020-01-01");
  await expect(page.getByRole("button", { name: "Today", exact: true })).toBeVisible();
  await request;
  await expect(page.getByText("Could not load the timeline", { exact: true })).toHaveCount(0);
});

test("Pulse links open an Ask question", async ({ page }) => {
  await page.goto("/pulse");
  await page.getByRole("link", { name: /Ask why/ }).first().click();
  await expect(page.getByLabel("Your question", { exact: true })).not.toHaveValue("");
  await expect(page).toHaveURL(/\/ask/);
});

test("upload a handover and open its transcript", async ({ page }) => {
  await page.goto("/meetings");
  await page.getByLabel("Meeting title", { exact: true }).fill("Test handover");
  await page.getByLabel("Recording or transcript", { exact: true }).setInputFiles({ name: "handover.txt", mimeType: "text/plain", buffer: Buffer.from("Sam: We use Neo4j for decision history.") });
  await page.getByRole("button", { name: "Upload handover", exact: true }).click();
  await page.getByRole("link", { name: "View transcript and decisions" }).click();
  await expect(page.getByRole("list", { name: "Transcript", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Decisions from this call/ })).toBeVisible();
});

test("API errors show the server message and recover on retry", async ({ page }) => {
  await page.route("**/api/repos", route => route.fulfill({ status: 503, json: { error: "The graph is waking up" } }));
  await page.goto("/ask");
  await expect(page.getByRole("alert").filter({ hasText: "The graph is waking up" })).toBeVisible();
  await page.unroute("**/api/repos");
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page.getByLabel("Repository", { exact: true })).toHaveValue("knadh/listmonk");
});

test("phone layout stays within the viewport", async ({ page }) => {
  const longRepo = "example-organization/a-repository-with-a-long-name";
  await page.route("**/api/repos", route => route.fulfill({ json: [{ ...repos[0], full_name: longRepo }] }));
  await page.setViewportSize({ width: 390, height: 844 });
  for (const path of ["/ask", "/pulse", "/meetings", "/timeline"]) {
    await page.goto(path);
    await expect(page.getByLabel("Repository", { exact: true })).toHaveValue(longRepo);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), path).toBe(true);
  }
});

test("Explore searches the graph and opens an entity page", async ({ page }) => {
  await page.goto("/explore");
  await expect(page.getByRole("list", { name: "Nodes by type" })).toContainText("decisions");
  await page.getByLabel(/Search knadh\/listmonk|Search PDGamerSG\/Untangle/).fill("concurrency");
  await page.getByRole("link", { name: /ConfigKey\s*app\.concurrency/ }).click();
  await expect(page).toHaveURL(/\/entities\//);
  await expect(page.getByRole("heading", { level: 1, name: "app.concurrency" })).toBeVisible();
  await expect(page.getByText("Declared in")).toBeVisible();
  await page.getByRole("link", { name: /Ask why/ }).click();
  await expect(page.getByLabel("Your question", { exact: true })).toHaveValue("why is app.concurrency like this?");
});
