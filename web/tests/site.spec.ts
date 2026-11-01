import { expect, test } from "@playwright/test";
import repos from "../sample/repos.json";
import health from "../sample/health.json";
import meetings from "../sample/meetings.json";
import meeting from "../sample/meeting.json";
import answer from "../sample/ask/concurrency.json";
import refusal from "../sample/ask/refusal.json";
import pulse from "../sample/pulse.json";
import repositoryMap from "../sample/repository-map.json";
import { sampleDecision, sampleTimeline } from "../src/lib/sample";

// Browser integration tests use recorded API contracts. Live service checks run separately.
// The inventory and import shapes the backend returns; values are illustrative, not a recorded snapshot.
const overview = {
  repo: "knadh/listmonk", url: "https://github.com/knadh/listmonk", description: "High performance, self-hosted newsletter and mailing list manager.",
  default_branch: "master", head_sha: repos[0].head_sha, ingested_at_iso: repos[0].ingested_at_iso, languages: ["Go", "Vue"],
  counts: { files: 410, dependencies: 2, documents: 1, features: 1, commits: 2270, prs: 896, issues: 2284, decisions: 2546, people: 120 },
  dependencies: [{ id: "dep:knadh/listmonk:github.com/lib/pq", name: "github.com/lib/pq", ecosystem: "go", version: "1.10.9", path: "go.mod" }],
  documents: [{ id: "doc:knadh/listmonk:README.md", path: "README.md", title: "listmonk" }],
  features: [{ id: "feature:knadh/listmonk:campaigns", name: "Campaigns", source: "routes", entrypoints: ["cmd/campaigns.go"] }],
  suggested_questions: ["why is app.concurrency set the way it is?"],
  coverage: { commits: 2270, max_commits: null, max_prs: null, max_issues: null, map_scanned_files: 410, unresolved_imports: 0 },
  warnings: ["Dependencies are capped at 50 in this list."],
};
const importLimits = { max_repository_size_kb: 100000, max_commits: 1000, max_prs: 50, max_issues: 100, imports_per_day: 20 };
const importJob = (status: "queued" | "running" | "complete" | "failed", extra: Record<string, unknown> = {}) => ({
  id: "imp_1", repo: "octo-org/hello-world", url: "https://github.com/octo-org/hello-world", status,
  stage: { queued: "queued", running: "history", complete: "complete", failed: "failed" }[status],
  progress: { queued: 0, running: 45, complete: 100, failed: 30 }[status], message: `Import ${status}`,
  created_at_iso: "2026-11-01T10:00:00Z", updated_at_iso: "2026-11-01T10:05:00Z", started_at_iso: status === "queued" ? null : "2026-11-01T10:02:00Z",
  finished_at_iso: status === "complete" || status === "failed" ? "2026-11-01T10:09:00Z" : null,
  error: status === "failed" ? "GitHub returned 404: the repository is private or does not exist." : null,
  summary: status === "complete" ? { commits: 42, decisions: 7 } : null, warnings: [], ...extra,
});

const concurrencyKey = { id: "cfg:knadh/listmonk:schema.sql::app.concurrency", label: "ConfigKey", name: "app.concurrency", path: "schema.sql", key: "app.concurrency", score: 1 };

test.beforeEach(async ({ page }) => {
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const path = decodeURIComponent(url.pathname.slice(4));
    let body: unknown;
    if (path === "/health") body = health;
    else if (path === "/repos") body = repos;
    else if (path === "/pulse") body = pulse;
    else if (path === "/repository-map") body = repositoryMap;
    else if (path === "/repository-overview") body = overview;
    else if (path === "/repository-imports") body = { enabled: true, limits: importLimits, worker: { last_seen_at_iso: null, scheduling: "every 5 minutes" }, jobs: [] };
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
  await page.getByRole("link", { name: "Open dashboard", exact: true }).first().click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { level: 1, name: "Dashboard" })).toBeVisible();
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
  await page.route("**/api/meetings/*", route => route.fulfill({ json: { ...meeting, source: "sarvam-batch" } }));
  await page.goto("/meetings");
  await page.getByLabel("Meeting title", { exact: true }).fill("Test handover");
  await page.getByLabel("Recording or transcript", { exact: true }).setInputFiles({ name: "handover.txt", mimeType: "text/plain", buffer: Buffer.from("Sam: We use Neo4j for decision history.") });
  await page.getByRole("button", { name: "Upload handover", exact: true }).click();
  await page.getByRole("link", { name: "View transcript and decisions" }).click();
  await expect(page.getByRole("list", { name: "Transcript", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Decisions from this call/ })).toBeVisible();
  await expect(page.getByText(/Audio transcript/)).toBeVisible();
  await expect(page.getByText("sarvam-batch", { exact: false })).toHaveCount(0);
});

test("API errors show the server message and recover on retry", async ({ page }) => {
  await page.route("**/api/repos", route => route.fulfill({ status: 503, json: { error: "The graph is waking up" } }));
  await page.goto("/ask");
  await expect(page.getByRole("alert").filter({ hasText: "The graph is waking up" })).toBeVisible();
  await page.unroute("**/api/repos");
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page.getByLabel("Repository", { exact: true })).toHaveValue("knadh/listmonk");
});

test("phone layout stays within the viewport", async ({ page }, testInfo) => {
  const longRepo = "example-organization/a-repository-with-a-long-name";
  await page.route("**/api/repos", route => route.fulfill({ json: [{ ...repos[0], full_name: longRepo }] }));
  await page.setViewportSize({ width: 390, height: 844 });
  for (const path of ["/dashboard", "/ask", "/pulse", "/meetings", "/timeline", "/map", "/repositories"]) {
    await page.goto(path);
    if (path === "/repositories") await expect(page.getByRole("heading", { level: 2, name: longRepo })).toBeVisible();
    else await expect(page.getByLabel("Repository", { exact: true })).toHaveValue(longRepo);
    if (path === "/timeline") await expect(page.getByRole("region", { name: "Selected decision" })).toBeVisible();
    if (path === "/pulse") await expect(page.locator("article[data-risk]").first()).toBeVisible();
    if (path === "/map") await expect(page.getByRole("group", { name: "Repository graph", exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), path).toBe(true);
    if (["/dashboard", "/timeline", "/pulse", "/repositories"].includes(path)) await page.screenshot({ path: testInfo.outputPath(`${path.slice(1)}-phone.png`), fullPage: true });
  }
});

test("dashboard search opens an entity page and asks about it", async ({ page }) => {
  await page.goto("/explore");
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("list", { name: "Nodes by type" })).toContainText("decisions");
  await page.getByLabel(/Search knadh\/listmonk|Search PDGamerSG\/Untangle/).fill("concurrency");
  await page.getByRole("link", { name: /ConfigKey\s*app\.concurrency/ }).click();
  await expect(page).toHaveURL(/\/entities\//);
  await expect(page.getByRole("heading", { level: 1, name: "app.concurrency" })).toBeVisible();
  await expect(page.getByText("Declared in")).toBeVisible();
  await page.getByRole("link", { name: /Ask why/ }).click();
  await expect(page.getByLabel("Your question", { exact: true })).toHaveValue("why is app.concurrency like this?");
  await expect(page.getByText(/Answer from the graph/i)).toBeVisible();
});

test("landing call-to-action at the end of the story opens the dashboard", async ({ page }) => {
  await page.goto("/");
  const cta = page.getByRole("link", { name: "Open dashboard", exact: true }).last();
  await cta.scrollIntoViewIfNeeded();
  await cta.click();
  await expect(page).toHaveURL(/\/dashboard$/);
});

test("dashboard shows live status and its example questions answer straight away", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: "System status" })).toBeVisible();
  await expect(page.getByRole("region", { name: "System status" }).getByText(/Neo4j/)).toBeVisible();
  await page.getByRole("button", { name: "why is app.concurrency set the way it is?", exact: true }).click();
  await expect(page).toHaveURL(/\/ask/);
  await expect(page.getByText(/Answer from the graph/i)).toBeVisible();
});

test("every nav link opens its page", async ({ page }) => {
  await page.goto("/dashboard");
  const nav = page.getByRole("navigation", { name: "Primary" });
  for (const [label, url, heading] of [
    ["Ask", /\/ask$/, /Find the reason/],
    ["Timeline", /\/timeline$/, null],
    ["Pulse", /\/pulse$/, /What is the team about to forget/],
    ["Map", /\/map$/, /How the repository fits together/],
    ["Meetings", /\/meetings$/, null],
    ["Dashboard", /\/dashboard$/, /^Dashboard$/],
  ] as const) {
    await nav.getByRole("link", { name: label, exact: true }).click();
    await expect(page).toHaveURL(url);
    if (heading) await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
  }
});

test("decision workbench filters, inspects and exports the historical evidence", async ({ page }, testInfo) => {
  const old = { ...pulse.risks[0].decision, id: "dec:knadh/listmonk:old-limit", subject: "app.concurrency", status: "superseded", valid_from_iso: "2020-01-01T00:00:00Z", valid_to_iso: "2021-01-01T00:00:00Z" };
  const dependency = { ...old, id: "dec:knadh/listmonk:dependency", subject: "neo4j", kind: "dependency", text: "Use Neo4j for decision history", rationale: null, object: "5.28", status: "active", valid_to_iso: null, about: [{ id: "dep:knadh/listmonk:neo4j", name: "neo4j", label: "Dependency" }] };
  await page.route("**/api/timeline?**", async route => {
    const at = new URL(route.request().url()).searchParams.get("at")!;
    await route.fulfill({ json: { at_iso: at, earliest_iso: "2020-01-01T00:00:00Z", active: [old, dependency], superseded_since: [old] } });
  });
  await page.goto("/timeline");
  await page.getByLabel("Jump to", { exact: true }).fill("2020-07-10");
  await expect(page.getByRole("region", { name: "Decision workbench" })).toContainText("10 Jul 2020");
  await page.screenshot({ path: testInfo.outputPath("workbench-desktop.png"), fullPage: true });
  await page.getByLabel("Filter decisions", { exact: true }).fill("app.concurrency");
  await expect(page.getByRole("list", { name: "Matching decisions" }).getByRole("button")).toHaveCount(1);
  await page.getByRole("button", { name: "Inspect app.concurrency", exact: true }).click();
  const detail = page.getByRole("region", { name: "Selected decision" });
  await expect(detail).toContainText("In force on 10 Jul 2020");
  await expect(detail).toContainText("Superseded");
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export view", exact: true }).click();
  const download = await downloadPromise;
  const stream = await download.createReadStream();
  const parts: Buffer[] = [];
  for await (const part of stream!) parts.push(Buffer.from(part));
  const markdown = Buffer.concat(parts).toString();
  expect(markdown).toContain(old.id);
  expect(markdown).toContain(old.decided_in.url);
  expect(markdown).toContain("2020-07-10");
  expect(markdown).not.toContain(dependency.id);
  await page.getByLabel("Filter decisions", { exact: true }).fill("nothing-matches-this");
  await expect(page.getByText("No decisions match these filters.", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Clear decision filters", exact: true }).click();
  await page.getByRole("button", { name: "Inspect neo4j", exact: true }).focus();
  await page.keyboard.press("Enter");
  await expect(detail.getByRole("heading", { name: "neo4j", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Replaced since 1", exact: true }).click();
  await expect(page.getByRole("list", { name: "Matching decisions" }).getByRole("button")).toHaveCount(1);
  await expect(detail.getByRole("heading", { name: "app.concurrency", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "All loaded 2", exact: true }).click();
  await page.getByLabel("Decision type", { exact: true }).selectOption("dependency");
  await expect(page.getByRole("list", { name: "Matching decisions" }).getByRole("button")).toHaveCount(1);
  await expect(detail).toContainText("No reason recorded.");
  const request = page.waitForRequest(req => req.url().endsWith("/api/ask") && req.method() === "POST");
  await detail.getByRole("link", { name: "Ask about this date", exact: true }).click();
  expect((await request).postDataJSON().at).toBe("2020-07-10T23:59:59Z");
});

test("Pulse triage filters risks and exports only the visible evidence", async ({ page }, testInfo) => {
  await page.goto("/pulse");
  await expect(page.locator("article[data-risk]")).toHaveCount(3);
  await page.screenshot({ path: testInfo.outputPath("pulse-desktop.png"), fullPage: true });
  await page.getByLabel("Filter risks", { exact: true }).fill("nothing-matches-this");
  await expect(page.getByText("No risks match these filters.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Export risks", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Clear risk filters", exact: true }).click();
  await page.getByRole("button", { name: /Ownership gaps \(1\)/ }).click();
  await expect(page.locator("article[data-risk]")).toHaveCount(1);
  await expect(page.locator("article[data-risk]")).toHaveAttribute("data-risk", "ownership_gap");
  await page.getByLabel("Critical only", { exact: true }).check();
  await expect(page.getByText("No risks match these filters.", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Clear risk filters", exact: true }).click();
  await expect(page.locator("article[data-risk]")).toHaveCount(3);
  await page.getByRole("button", { name: /Conflicts \(1\)/ }).click();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export risks", exact: true }).click();
  const stream = await (await downloadPromise).createReadStream();
  const parts: Buffer[] = [];
  for await (const part of stream!) parts.push(Buffer.from(part));
  const markdown = Buffer.concat(parts).toString();
  expect(markdown).toContain(pulse.risks[0].id);
  expect(markdown).not.toContain(pulse.risks[1].id);
  expect(markdown).toContain(pulse.risks[0].reasons[0]);
  expect(markdown).toContain(pulse.risks[0].contradictions[0].id);
});

test("invalid historical URL dates do not reach the answer API", async ({ page }) => {
  const request = page.waitForRequest(req => req.url().endsWith("/api/ask") && req.method() === "POST");
  await page.goto("/ask?question=why%20is%20app.concurrency%20like%20this&at=2020-02-31");
  expect((await request).postDataJSON().at).toBeNull();
});

test("an empty timeline explains the snapshot and disables export", async ({ page }) => {
  await page.route("**/api/timeline?**", route => route.fulfill({ json: { at_iso: new Date().toISOString(), active: [], superseded_since: [] } }));
  await page.goto("/timeline");
  await expect(page.getByText("No decisions recorded for this snapshot.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Export view", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Clear decision filters", exact: true })).toHaveCount(0);
});

test("feature map explores dependencies and commit impact with evidence", async ({ page }, testInfo) => {
  await page.goto("/map");
  const graph = page.getByRole("group", { name: "Repository graph", exact: true });
  await expect(graph).toBeVisible();
  await graph.getByRole("button", { name: "Feature Ask", exact: true }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("region", { name: "Graph inspector" })).toContainText("ask.ts");
  await page.getByRole("button", { name: "Inspect commit bbbbbbb", exact: true }).click();
  const inspector = page.getByRole("region", { name: "Graph inspector" });
  await expect(inspector).toContainText("2 potentially affected features");
  await expect(inspector).toContainText("ask.ts → shared.ts");
  await expect(inspector).not.toContainText("Independent");
  await expect(inspector).toContainText("No revert has been run");
  await page.getByRole("button", { name: "Zoom in", exact: true }).click();
  await page.getByRole("button", { name: "Reset graph view", exact: true }).click();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: testInfo.outputPath("commit-impact-desktop.png"), fullPage: true });
  await page.getByRole("button", { name: "Commit history", exact: true }).click();
  await expect(graph.getByRole("button", { name: "Commit aaaaaaa", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Export to Obsidian", exact: true })).toHaveAttribute("href", /repository-map\/obsidian\?.*limit=200/);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("commit-history-phone.png"), fullPage: true });
});

test("feature map handles repositories that have not been indexed", async ({ page }) => {
  await page.route("**/api/repository-map?**", route => route.fulfill({ json: { ...repositoryMap, head_sha: null, features: [], imports: [] } }));
  await page.goto("/map");
  await expect(page.getByText("This repository needs a map index.", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Export to Obsidian", exact: true })).toHaveCount(0);
});

test("connected features remain readable beside an isolated feature on desktop and phone", async ({ page }, testInfo) => {
  const names = ["Ask & evidence", "Decision history", "Feature map", "Handover calls", "History ingestion", "Knowledge risks", "Landing experience", "Repository discovery"];
  const features = names.map((name, i) => ({ ...repositoryMap.features[0], id: `feature:${i}`, name, entrypoints: [`entry-${i}.ts`] }));
  const imports = features.filter((_, i) => i !== 6).map(feature => ({ source: feature.entrypoints[0], target: "shared.ts", line: 1, specifier: "./shared" }));
  await page.route("**/api/repository-map?**", route => route.fulfill({ json: { ...repositoryMap, features, imports } }));
  for (const width of [1280, 390]) {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/map");
    const graph = page.getByRole("group", { name: "Repository graph", exact: true });
    await expect(graph.getByRole("button")).toHaveCount(8);
    await expect.poll(async () => graph.getByRole("button").evaluateAll(nodes => {
      const bounds = nodes.map(node => ({ name: node.getAttribute("aria-label"), rect: node.getBoundingClientRect() }));
      return bounds.flatMap((a, i) => bounds.slice(i + 1).filter(b => a.rect.left < b.rect.right && a.rect.right > b.rect.left && a.rect.top < b.rect.bottom && a.rect.bottom > b.rect.top).map(b => `${a.name} / ${b.name}`));
    })).toEqual([]);
    await page.screenshot({ path: testInfo.outputPath(`connected-features-${width}.png`), fullPage: true });
  }
});

test("dense graphs reveal source names on keyboard focus and keep selected files inspectable", async ({ page }) => {
  const files = Array.from({ length: 20 }, (_, i) => ({ path: `dependency-${i}.ts`, alive: true }));
  const imports = files.map(file => ({ source: "ask.ts", target: file.path, line: 1, specifier: `./${file.path}` }));
  await page.route("**/api/repository-map?**", route => route.fulfill({ json: { ...repositoryMap, files: [...repositoryMap.files, ...files], imports } }));
  await page.goto("/map");
  const graph = page.getByRole("group", { name: "Repository graph", exact: true });
  await graph.getByRole("button", { name: "Feature Ask", exact: true }).click();
  const file = graph.getByRole("button", { name: "File dependency-0.ts", exact: true });
  await file.focus();
  await expect(file.locator("text")).toHaveText("dependency-0.ts");
  await expect(file.locator("text")).toBeVisible();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("region", { name: "Graph inspector" })).toContainText("dependency-0.ts");
  await page.getByRole("button", { name: "Zoom in", exact: true }).focus();
  await expect(file.locator("text")).toBeVisible();
});

test("commit history pagination loads older records and clears the selection", async ({ page }) => {
  await page.route("**/api/repository-map?**", route => {
    const offset = Number(new URL(route.request().url()).searchParams.get("offset"));
    return route.fulfill({ json: { ...repositoryMap, offset, total_commits: 41, has_more: offset === 0, commits: [repositoryMap.commits[offset === 0 ? 0 : 1]] } });
  });
  await page.goto("/map");
  await page.getByRole("button", { name: "Inspect commit bbbbbbb", exact: true }).click();
  await page.getByRole("button", { name: "Older commits", exact: true }).click();
  await expect(page.getByRole("button", { name: "Inspect commit aaaaaaa", exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Graph inspector" })).not.toContainText("Change shared retrieval");
  await expect(page.getByRole("button", { name: "Older commits", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Newer commits", exact: true }).click();
  await expect(page.getByRole("button", { name: "Inspect commit bbbbbbb", exact: true })).toBeVisible();
});

test("adding a public repository follows the import across a reload and selects it when complete", async ({ page }) => {
  let polls = 0;
  let indexed = false;
  await page.route("**/api/repos", route => route.fulfill({ json: indexed ? [...repos, { ...repos[0], full_name: "octo-org/hello-world" }] : repos }));
  await page.route("**/api/repository-imports", async route => {
    if (route.request().method() !== "POST") return route.fallback();
    expect(route.request().postDataJSON()).toEqual({ repository: "https://github.com/octo-org/hello-world" });
    await route.fulfill({ status: 202, json: importJob("queued") });
  });
  await page.route("**/api/repository-imports/imp_1", route => {
    polls += 1;
    const status = polls < 3 ? "running" : "complete";
    if (status === "complete") indexed = true;
    return route.fulfill({ json: importJob(status) });
  });
  await page.goto("/dashboard");
  await page.getByRole("link", { name: "Add repository" }).first().click();
  await expect(page).toHaveURL(/\/repositories$/);
  await expect(page.getByRole("heading", { level: 1, name: "Repositories" })).toBeVisible();
  const input = page.getByLabel("GitHub repository", { exact: true });
  await input.fill("not a repository");
  await page.getByRole("button", { name: "Add repository", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "owner/name" })).toBeVisible();
  await input.fill("http://www.github.com/octo-org/hello-world.git");
  await page.getByRole("button", { name: "Add repository", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "full https://github.com/owner/name link" })).toBeVisible();
  await input.fill("https://github.com/octo-org/hello-world");
  await page.getByRole("button", { name: "Add repository", exact: true }).click();
  await expect(page.getByRole("heading", { level: 2, name: "octo-org/hello-world" })).toBeVisible();
  await expect(page.getByRole("progressbar", { name: "Indexing octo-org/hello-world" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { level: 2, name: "octo-org/hello-world" })).toBeVisible();
  await expect(page.getByText("is indexed and now selected")).toBeVisible({ timeout: 30000 });
  await expect(page.getByRole("progressbar", { name: "Indexing octo-org/hello-world" })).toHaveAttribute("aria-valuenow", "100");
  await page.getByRole("button", { name: "Open octo-org/hello-world" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByLabel("Repository", { exact: true })).toHaveValue("octo-org/hello-world");
});

test("a failed import explains why and can be retried", async ({ page }) => {
  let posts = 0;
  await page.addInitScript(() => window.localStorage.setItem("untangle.import", "imp_1"));
  await page.route("**/api/repository-imports", async route => {
    if (route.request().method() !== "POST") return route.fallback();
    posts += 1;
    await route.fulfill({ status: 202, json: importJob("queued") });
  });
  await page.route("**/api/repository-imports/imp_1", route => route.fulfill({ json: importJob(posts ? "queued" : "failed") }));
  await page.goto("/repositories");
  await expect(page.getByRole("alert").filter({ hasText: "private or does not exist" })).toBeVisible();
  await page.getByRole("button", { name: "Try again", exact: true }).click();
  await expect(page.getByText("Waiting for the indexing worker")).toBeVisible();
  expect(posts).toBe(1);
});

test("import errors from the API are shown beside the form", async ({ page }) => {
  await page.route("**/api/repository-imports", route =>
    route.request().method() === "POST" ? route.fulfill({ status: 429, json: { error: "The shared import limit for today has been reached." } }) : route.fallback());
  await page.goto("/repositories");
  await page.getByLabel("GitHub repository", { exact: true }).fill("octo-org/hello-world");
  await page.getByRole("button", { name: "Add repository", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "shared import limit" })).toBeVisible();
});

test("the repositories page shows the indexed inventory of the selected repository", async ({ page }) => {
  await page.goto("/repositories");
  await expect(page.getByRole("heading", { level: 2, name: "knadh/listmonk" })).toBeVisible();
  await expect(page.getByLabel("Indexed records")).toContainText("2,546");
  await expect(page.getByText("github.com/lib/pq")).toBeVisible();
  await expect(page.getByText("Dependencies are capped at 50")).toBeVisible();
  await page.getByRole("link", { name: "why is app.concurrency set the way it is?" }).click();
  await expect(page).toHaveURL(/\/ask/);
  await expect(page.getByLabel("Your question", { exact: true })).toHaveValue("why is app.concurrency set the way it is?");
});
