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

const account = { id: "user:asha", email: "asha@example.com", name: "Asha Verma", role: "member", created_at_iso: "2026-11-01T00:00:00Z" };

const githubRepos = {
  owner: "asha", connected: true, self: true,
  repositories: [
    { full_name: "asha/notes-api", description: "Notes service", language: "Go", stars: 12, fork: false, archived: false, size_kb: 900, default_branch: "main",
      pushed_at: "2026-11-20T10:00:00Z", url: "https://github.com/asha/notes-api", imported: false, saved: false, ingested_at_iso: null, job: null },
    { full_name: "knadh/listmonk", description: "Newsletter manager", language: "Go", stars: 15000, fork: true, archived: false, size_kb: 9000, default_branch: "master",
      pushed_at: "2026-11-19T10:00:00Z", url: "https://github.com/knadh/listmonk", imported: true, saved: true, ingested_at_iso: "2026-11-01T00:00:00Z", job: null },
  ],
};

const savedRepos = {
  max: 30,
  repositories: [{ repo: "knadh/listmonk", saved_at_iso: "2026-11-02T00:00:00Z", imported: true, ingested_at_iso: "2026-11-01T00:00:00Z", indexed_sha: "abc1234def",
    commit_count: 1000, job: null, changes: { available: true, ahead_by: 2 }, unseen: true }],
};

const changes = {
  repo: "knadh/listmonk", indexed_sha: "abc1234def", ingested_at_iso: "2026-11-01T00:00:00Z", default_branch: "master", available: true, ahead_by: 2, behind_by: 0,
  compare_url: "https://github.com/knadh/listmonk/compare/abc1234...master", files_changed: 1,
  commits: [
    { sha: "fff0001", short: "fff0001", message: "Raise default concurrency", author: "knadh", date: "2026-11-20T09:00:00Z", url: "https://github.com/knadh/listmonk/commit/fff0001" },
    { sha: "eee0002", short: "eee0002", message: "Fix campaign retry", author: "asha", date: "2026-11-19T09:00:00Z", url: "https://github.com/knadh/listmonk/commit/eee0002" },
  ],
  files: [{ path: "internal/manager/manager.go", status: "modified", additions: 4, deletions: 2 }],
  indexed_recent: [{ sha: "abc1234def", short: "abc1234", message: "Release v5", date: "2026-10-30T00:00:00Z" }],
};

test.beforeEach(async ({ page, baseURL }) => {
  // Browser tests run as a signed-in member; the API's session checks are covered by the backend suite.
  await page.context().addCookies([{ name: "untangle_session", value: "browser-test-session", url: baseURL ?? "http://127.0.0.1:3100" }]);
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const path = decodeURIComponent(url.pathname.slice(4));
    let body: unknown;
    if (path === "/auth/me") body = { user: account };
    else if (path === "/auth/providers") body = { github: true };
    else if (path === "/auth/github") body = { github: { login: "asha", avatar_url: "" } };
    else if (path === "/github/repositories") body = githubRepos;
    else if (path === "/my/repositories" && route.request().method() === "GET") body = savedRepos;
    else if (path === "/my/repositories" && route.request().method() === "POST") body = { repo: route.request().postDataJSON().repository, saved: true };
    else if (path === "/my/repositories") return route.fulfill({ status: 204, body: "" });
    else if (path === "/my/repositories/changes") body = changes;
    else if (path === "/auth/tokens" && route.request().method() === "GET") body = { tokens: [], max: 10 };
    else if (path === "/agent-notes") body = { repo: url.searchParams.get("repo"), notes: [] };
    else if (path === "/auth/logout") return route.fulfill({ status: 204, body: "" });
    else if (path === "/health") body = health;
    else if (path === "/repos") body = repos;
    else if (path === "/pulse") body = pulse;
    else if (path === "/repository-map") body = repositoryMap;
    else if (path === "/repository-overview") body = overview;
    else if (path === "/repository-imports") body = { enabled: true, limits: importLimits, worker: { last_seen_at_iso: null, scheduling: "every 5 minutes" }, jobs: [] };
    else if (path === "/meetings") body = meetings;
    else if (path.startsWith("/meetings/")) body = meeting;
    else if (path === "/ask") {
      const request = route.request().postDataJSON();
      body = request.question.includes("MongoDB") ? refusal : { ...answer, baseline: request.mode !== "graph" ? answer.baseline : null };
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

test("dashboard inventory shows a wait estimate and replaces it with records", async ({ page }) => {
  let finish!: () => void;
  const pending = new Promise<void>(resolve => { finish = resolve; });
  await page.route("**/api/repository-overview?**", async route => {
    await pending;
    await route.fulfill({ json: overview });
  });
  await page.goto("/dashboard");
  await expect(page.getByText("Loading inventory for knadh/listmonk.", { exact: true })).toBeVisible();
  await expect(page.getByText(/Estimated wait: 1–5 seconds/)).toBeVisible();
  finish();
  await expect(page.getByLabel("Indexed records", { exact: true })).toBeVisible();
  await expect(page.getByText("Loading inventory for knadh/listmonk.", { exact: true })).toHaveCount(0);
});

test("large maps load every page and retain all nodes without freezing navigation", async ({ page }) => {
  const files = Array.from({ length: 2101 }, (_, i) => ({ path: `area-${i % 85}/file-${i}.py`, alive: true }));
  const imports = files.slice(0, -1).map(file => ({ source: file.path, target: files[2100].path, line: 1, specifier: "helper" }));
  const features = Array.from({ length: 85 }, (_, i) => ({ id: `area-${i}`, name: `area-${i}`, source: "directory", entrypoints: files.filter(f => f.path.startsWith(`area-${i}/`)).map(f => f.path), description: "Code area" }));
  await page.route("**/api/repository-map?**", route => {
    const n = Number(new URL(route.request().url()).searchParams.get("structure_page"));
    return route.fulfill({ json: { ...repositoryMap, index_status: "ready", total_files: 2101, total_imports: 2100, total_features: 85,
      structure_page: n, structure_has_more: n < 4, files: files.slice(n * 500, (n + 1) * 500), imports: imports.slice(n * 2000, (n + 1) * 2000),
      features: features.slice(n * 100, (n + 1) * 100) } });
  });
  await page.goto("/map");
  await page.getByRole("button", { name: "All files", exact: true }).click();
  const graph = page.getByRole("group", { name: "Repository graph", exact: true });
  await expect(graph.getByRole("button")).toHaveCount(2101);
  expect(await graph.evaluate(svg => {
    const frame = svg.getBoundingClientRect();
    return [...svg.querySelectorAll("[data-node] circle.map-node-dot")].every(node => {
      const rect = node.getBoundingClientRect();
      return rect.left >= frame.left && rect.right <= frame.right && rect.top >= frame.top && rect.bottom <= frame.bottom;
    });
  })).toBe(true);
  await expect(page.getByText("Map loaded · 2,101 nodes in this view · 2,100 connections", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Zoom in", exact: true }).click();
  await page.getByRole("button", { name: "Feature connections", exact: true }).click();
  await expect(graph.getByRole("button")).toHaveCount(85);
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

test("slow comparison never hides the cited answer and can be cancelled", async ({ page }) => {
  await page.route("**/api/ask", async route => {
    const req = route.request().postDataJSON();
    if (req.mode === "graph") await route.fulfill({ json: { ...answer, baseline: null } });
    else await new Promise<void>(resolve => { page.once("close", () => resolve()); });
  });
  await page.goto("/ask");
  await page.getByLabel("Your question", { exact: true }).fill("why is app.concurrency set the way it is?");
  await page.getByLabel("Compare with vector-only search").check();
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByRole("article", { name: "Answer", exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Sources", exact: true })).toBeVisible();
  await expect(page.getByText(/Estimated wait:.*seconds/)).toBeVisible();
  await page.getByRole("button", { name: "Cancel comparison", exact: true }).click();
  await expect(page.getByRole("article", { name: "Answer", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Cancel comparison", exact: true })).toHaveCount(0);
});

test("answer progress shows an estimate and repository changes discard stale answers", async ({ page }) => {
  await page.route("**/api/repos", route => route.fulfill({ json: [...repos, { ...repos[0], full_name: "other/project" }] }));
  await page.route("**/api/ask", async route => {
    await new Promise(resolve => setTimeout(resolve, 1500));
    await route.fulfill({ json: answer }).catch(() => {});
  });
  await page.goto("/ask");
  await page.getByLabel("Your question", { exact: true }).fill("why is app.concurrency set the way it is?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByText(/Estimated wait:.*seconds/)).toBeVisible();
  await page.getByRole("button", { name: "Cancel answer", exact: true }).click();
  await expect(page.getByRole("button", { name: "Ask", exact: true })).toBeEnabled();
  await page.getByLabel("Repository", { exact: true }).selectOption("other/project");
  await expect(page.getByRole("article", { name: "Answer", exact: true })).toHaveCount(0);
});

test("legacy map remains interactive and explains missing import connections", async ({ page }) => {
  await page.route("**/api/repository-map?*", route => route.fulfill({ json: {
    ...repositoryMap, index_status: "basic", imports: [],
  } }));
  await page.goto("/map");
  await expect(page.getByText("File and commit map ready", { exact: true })).toBeVisible();
  await expect(page.getByRole("group", { name: "Repository graph", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Export to Obsidian", exact: true })).toBeVisible();
});

test("repository onboarding accepts clone URLs and shows an import estimate", async ({ page }) => {
  await page.route("**/api/repository-imports", async route => {
    if (route.request().method() === "POST") {
      expect(route.request().postDataJSON().repository).toBe("octo-org/hello-world");
      await route.fulfill({ status: 202, json: importJob("queued") });
    } else await route.fallback();
  });
  await page.route("**/api/repository-imports/imp_1", route => route.fulfill({ json: importJob("queued", {
    estimate: { elapsed_seconds: 10, remaining_min_seconds: 120, remaining_max_seconds: 900, overdue: false },
  }) }));
  await page.goto("/repositories");
  await page.getByLabel("GitHub repository", { exact: true }).fill("https://github.com/octo-org/hello-world.git/");
  await page.getByRole("button", { name: "Add repository", exact: true }).click();
  await expect(page.getByRole("progressbar", { name: "Indexing octo-org/hello-world" })).toBeVisible();
  await expect(page.getByText(/Estimated time remaining/)).toBeVisible();
});

test("missing decisions and pages return to Ask", async ({ page }) => {
  await page.route("**/api/decisions/missing", route => route.fulfill({ status: 404, json: { error: "No such decision" } }));
  await page.goto("/decisions/missing");
  await page.getByRole("link", { name: "Ask a question", exact: true }).click();
  await expect(page).toHaveURL(/\/ask$/);
  await page.goto("/missing-page");
  await page.getByRole("link", { name: "ask a question", exact: true }).click();
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
  await page.getByLabel(/Everyone in this conversation agreed/).check();
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

test("invalid historical URL dates do not reach the answer API", async ({ page, baseURL }) => {
  const request = page.waitForRequest(req => req.url().endsWith("/api/ask") && req.method() === "POST");
  await page.goto("/ask?question=why%20is%20app.concurrency%20like%20this&at=2020-02-31", { referer: `${baseURL}/dashboard` });
  expect((await request).postDataJSON().at).toBeNull();
});

test("a question linked from another site is filled in but waits for a click", async ({ page }) => {
  let asked = 0;
  page.on("request", req => { if (req.url().endsWith("/api/ask") && req.method() === "POST") asked += 1; });
  await page.goto("/ask?question=why%20is%20app.concurrency%20like%20this", { referer: "https://elsewhere.example/post" });
  await expect(page.getByRole("textbox", { name: /question/i })).toHaveValue("why is app.concurrency like this");
  await page.waitForTimeout(1000);
  expect(asked).toBe(0);
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect.poll(() => asked).toBe(1);
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
  await page.route("**/api/repository-map?**", route => route.fulfill({ json: { ...repositoryMap, total_files: 0, total_commits: 0, head_sha: null, files: [], commits: [], features: [], imports: [] } }));
  await page.goto("/map");
  await expect(page.getByText("No files or commits have been indexed yet.", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Export to Obsidian", exact: true })).toHaveCount(0);
});

test("connected features remain readable beside an isolated feature on desktop and phone", async ({ page }, testInfo) => {
  const names = ["Ask & evidence", "Decision history", "Feature map", "Handover calls", "History ingestion", "Knowledge risks", "Landing experience", "Repository discovery"];
  const features = names.map((name, i) => ({ ...repositoryMap.features[0], id: `feature:${i}`, name, entrypoints: [`entry-${i}.ts`] }));
  const imports = features.filter((_, i) => i !== 6).map(feature => ({ source: feature.entrypoints[0], target: "shared.ts", line: 1, specifier: "./shared" }));
  const files = [...features.flatMap(f => f.entrypoints), "shared.ts"].map(path => ({ path, alive: true }));
  await page.route("**/api/repository-map?**", route => route.fulfill({ json: { ...repositoryMap, total_files: files.length, files, features, imports } }));
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
  await page.route("**/api/repository-map?**", route => route.fulfill({ json: { ...repositoryMap, total_files: repositoryMap.files.length + files.length, files: [...repositoryMap.files, ...files], imports } }));
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
    expect(route.request().postDataJSON()).toEqual({ repository: "octo-org/hello-world" });
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

test("a connected GitHub account lists its repositories and saved ones show commits since import", async ({ page }) => {
  await page.goto("/repositories");
  const saved = page.getByRole("region", { name: "Your repositories" });
  await expect(saved.getByText("2 new commits on GitHub")).toBeVisible();
  await saved.getByRole("button", { name: "What changed" }).click();
  await expect(saved.getByText("Raise default concurrency")).toBeVisible();
  await expect(saved.getByRole("link", { name: "Compare on GitHub" })).toHaveAttribute("href", /compare\/abc1234\.\.\.master/);
  await expect(saved.getByRole("button", { name: "Update import" })).toBeVisible();

  const fromGitHub = page.getByRole("region", { name: "From GitHub" });
  await expect(fromGitHub.getByText("Connected as @asha")).toBeVisible();
  await expect(fromGitHub.getByText("asha/notes-api")).toBeVisible();
  await expect(fromGitHub.getByText("In your list")).toBeVisible();
  await expect(fromGitHub.getByRole("button", { name: "Import" })).toBeEnabled();
});

test("sign-in offers GitHub and keeps the requested page", async ({ page, context }) => {
  await context.clearCookies();
  await page.route("**/api/auth/me", (route) => route.fulfill({ status: 401, json: { detail: "Sign in to use Untangle." } }));
  await page.goto("/login?next=/pulse");
  await expect(page.getByRole("link", { name: "Continue with GitHub" })).toHaveAttribute("href", "/api/auth/github/start?next=%2Fpulse");
  await page.goto("/login?error=github-conflict");
  await expect(page.getByRole("alert").filter({ hasText: "already connected to a different Untangle account" })).toBeVisible();
});

test("signed-out visitors are sent to sign-in and return to the page they asked for", async ({ page }) => {
  await page.context().clearCookies();
  await page.route("**/api/auth/me", route => route.fulfill({ status: 401, json: { detail: "Sign in to use Untangle." } }));
  await page.route("**/api/auth/login", async route => {
    const body = route.request().postDataJSON();
    if (body.password !== "correct horse battery staple") return route.fulfill({ status: 401, json: { detail: "Email or password is incorrect." } });
    await page.context().addCookies([{ name: "untangle_session", value: "fresh", url: page.url() }]);
    return route.fulfill({ json: { user: account } });
  });
  await page.goto("/pulse");
  await expect(page).toHaveURL(/\/login\?next=%2Fpulse$/);
  await expect(page.getByRole("heading", { level: 1, name: "Sign in" })).toBeVisible();
  await page.getByLabel("Email").fill("asha@example.com");
  await page.getByLabel("Password", { exact: true }).fill("wrong password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "incorrect" })).toHaveText("Email or password is incorrect.");
  await page.unroute("**/api/auth/me");
  await page.getByLabel("Password", { exact: true }).fill("correct horse battery staple");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/pulse$/);
});

test("sign-up checks the password before sending it and links to sign-in", async ({ page }) => {
  await page.context().clearCookies();
  await page.route("**/api/auth/me", route => route.fulfill({ status: 401, json: { detail: "Sign in to use Untangle." } }));
  let sent = false;
  await page.route("**/api/auth/register", route => { sent = true; return route.fulfill({ status: 201, json: { user: account } }); });
  await page.goto("/signup");
  await page.getByLabel("Email").fill("asha@example.com");
  await page.getByLabel("Password", { exact: true }).fill("short");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "characters" })).toContainText("at least 10 characters");
  expect(sent).toBe(false);
  await page.getByRole("link", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/login$/);
});

test("a crafted next link cannot send people to another site after sign-in", async ({ page }) => {
  await page.context().clearCookies();
  await page.route("**/api/auth/me", route => route.fulfill({ status: 401, json: { detail: "Sign in to use Untangle." } }));
  await page.route("**/api/auth/login", async route => {
    await page.context().addCookies([{ name: "untangle_session", value: "fresh", url: page.url() }]);
    return route.fulfill({ json: { user: account } });
  });
  await page.goto("/login?next=//evil.example/steal");
  await page.getByLabel("Email").fill("asha@example.com");
  await page.getByLabel("Password", { exact: true }).fill("correct horse battery staple");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/127\.0\.0\.1:3100\/dashboard$/);
});

test("signing out ends the session from the sidebar", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  let signedOut = false;
  await page.route("**/api/auth/logout", route => { signedOut = true; return route.fulfill({ status: 204, body: "" }); });
  await page.goto("/dashboard");
  await expect(page.getByText("asha@example.com")).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page).toHaveURL(/\/login/);
  expect(signedOut).toBe(true);
});

test("pages and the landing page send security headers", async ({ request }) => {
  for (const path of ["/", "/login"]) {
    const response = await request.get(path, { maxRedirects: 0 });
    const headers = response.headers();
    expect(headers["x-frame-options"], path).toBe("DENY");
    expect(headers["x-content-type-options"], path).toBe("nosniff");
    expect(headers["content-security-policy"], path).toContain("frame-ancestors 'none'");
    expect(headers["referrer-policy"], path).toBe("strict-origin-when-cross-origin");
    expect(headers["x-powered-by"], path).toBeUndefined();
  }
  expect((await request.get("/")).headers()["content-security-policy"]).toContain("script-src 'self';");
  expect((await request.get("/.well-known/security.txt")).ok()).toBe(true);
});

test("a member creates an agent token, copies the connection command and revokes it", async ({ page }) => {
  let tokens: Record<string, unknown>[] = [];
  await page.route("**/api/auth/tokens**", async route => {
    const method = route.request().method();
    if (method === "POST") {
      const created = { id: "0123456789abcdef", name: route.request().postDataJSON().name, prefix: "utg_abcd", created_at_iso: "2026-11-21T10:00:00Z", token: "utg_abcdEXAMPLEONLY" };
      tokens = [{ ...created, token: undefined, last_used_at_iso: null }];
      return route.fulfill({ status: 201, json: created });
    }
    if (method === "DELETE") { tokens = []; return route.fulfill({ status: 204, body: "" }); }
    return route.fulfill({ json: { tokens, max: 10 } });
  });
  await page.route("**/api/agent-notes?**", route => route.fulfill({ json: { repo: "knadh/listmonk", notes: [{
    id: "dec:knadh/listmonk:agent:1", subject: "schema.sql::app.concurrency", topic: "retry-policy", decision: "Keep concurrency at 10 until the SES quota is raised.",
    rationale: "Higher values hit the provider's rate limit.", status: "active", recorded_by: "Asha Verma", source_url: "javascript:alert(1)",
    about: ["schema.sql::app.concurrency"], recorded_at_iso: "2026-11-21T10:05:00Z" }] } }));
  await page.goto("/agents");
  await expect(page.getByRole("heading", { level: 1, name: "Connect a coding agent" })).toBeVisible();
  await expect(page.getByText("remember_decision", { exact: true })).toBeVisible();
  await page.getByLabel("Token name").fill("Claude Code laptop");
  await page.getByRole("button", { name: "Create token" }).click();
  await expect(page.getByLabel("New token")).toHaveText("utg_abcdEXAMPLEONLY");
  await expect(page.getByText(/claude mcp add --transport http untangle http:\/\/127\.0\.0\.1:3100\/api\/mcp/)).toBeVisible();
  await expect(page.getByRole("list", { name: "Agent notes" })).toContainText("Keep concurrency at 10");
  // A note's link is only followed when it is a web address.
  await expect(page.getByRole("list", { name: "Agent notes" }).getByRole("link", { name: "Source" })).toHaveCount(0);
  page.once("dialog", dialog => dialog.accept());
  await page.getByRole("button", { name: "Revoke Claude Code laptop" }).click();
  await expect(page.getByText("No tokens yet.", { exact: false })).toBeVisible();
});

test("public pages meet WCAG AA in an automated check and publish sharing metadata", async ({ page, request }) => {
  const { default: AxeBuilder } = await import("@axe-core/playwright");
  await page.route("**/api/auth/me", route => route.fulfill({ status: 401, json: { detail: "Sign in to use Untangle." } }));
  // Desktop width: the landing page's progress rail only appears on wide screens.
  await page.setViewportSize({ width: 1280, height: 800 });
  for (const path of ["/", "/login", "/signup"]) {
    await page.context().clearCookies();
    await page.goto(path);
    await page.waitForTimeout(1000);
    const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
    const serious = result.violations.filter(v => v.impact === "serious" || v.impact === "critical");
    expect(serious.map(v => `${path} ${v.id}: ${v.nodes.map(n => n.target.join(" ")).slice(0, 3).join(", ")}`)).toEqual([]);
    await expect(page.locator('link[rel="canonical"]')).toHaveCount(1);
    await expect(page.locator('meta[property="og:image"]')).toHaveCount(1);
  }
  expect((await request.get("/sitemap.xml")).ok()).toBe(true);
  expect((await request.get("/og.png")).headers()["content-type"]).toBe("image/png");
});

test("every chapter of the landing story keeps WCAG AA contrast and marks the current chapter", async ({ page }) => {
  test.setTimeout(120_000);
  const { default: AxeBuilder } = await import("@axe-core/playwright");
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/", { waitUntil: "load" });
  // Checked immediately too: the intro animation must not leave text at low contrast while the page loads.
  const early = await new AxeBuilder({ page }).withRules(["color-contrast"]).analyze();
  expect(early.violations.flatMap(v => v.nodes.map(n => `t=0 ${n.target.join(" ")}`))).toEqual([]);
  await page.waitForTimeout(1200);
  const height = await page.evaluate(() => document.documentElement.scrollHeight);
  const failures = new Set<string>();
  for (let y = 0; y <= height; y += 700) {
    await page.evaluate(top => window.scrollTo(0, top), y);
    await page.waitForTimeout(600);
    const result = await new AxeBuilder({ page }).withRules(["color-contrast"]).analyze();
    for (const v of result.violations) for (const n of v.nodes) failures.add(`y=${y} ${n.target.join(" ")}`);
  }
  expect([...failures]).toEqual([]);
  await page.evaluate(() => window.scrollTo(0, document.querySelector<HTMLElement>("#refuse")!.offsetTop + 10));
  await expect(page.locator('[data-rail="refuse"]')).toHaveAttribute("aria-current", "location");
  await expect(page.locator('[aria-current="location"]')).toHaveCount(1);
  // Clicking a chapter marks it at once, before the scroll it starts has finished.
  await page.locator('[data-rail="time"]').click();
  await expect(page.locator('[data-rail="time"]')).toHaveAttribute("aria-current", "location", { timeout: 300 });
  await expect(page.locator('[aria-current="location"]')).toHaveCount(1);
});
