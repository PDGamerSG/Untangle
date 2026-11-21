import { expect, test } from "@playwright/test";
import { api, hrefFor } from "../src/lib/api";
import { decisionBrief, matchesDecision, snapshotDecisions } from "../src/lib/evidence-brief";
import type { DecisionCard } from "../src/lib/types";
import pulse from "../sample/pulse.json";
import mapFixture from "../sample/repository-map.json";
import { commitImpact, featureFiles, mapGraph, type RepositoryMap } from "../src/lib/repository-map";
import { createElement, useLayoutEffect } from "react";
import { act, create, type ReactTestRenderer } from "react-test-renderer";
import { invalidateRepositoryResources, primeResource, useResource } from "../src/lib/hooks";

test("inventory resolves when shared data arrives between render and effects", async () => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  function Panel() {
    const resource = useResource("cache-race-test", async () => "loaded");
    // A sibling's request or a primed response can finish before passive effects run.
    useLayoutEffect(() => primeResource("cache-race-test", "loaded"), []);
    return createElement("output", null, resource.loading ? "loading" : resource.data);
  }
  let root!: ReactTestRenderer;
  try {
    await act(async () => { root = create(createElement(Panel)); });
    expect(root.toJSON()).toMatchObject({ children: ["loaded"] });
  } finally { await act(async () => root?.unmount()); }
});

test("completing an import refreshes an already mounted inventory", async () => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  primeResource("overview:refresh/repo", "old counts");
  function Panel() {
    const resource = useResource("overview:refresh/repo", async () => "complete counts");
    return createElement("output", null, resource.data);
  }
  let root!: ReactTestRenderer;
  try {
    await act(async () => { root = create(createElement(Panel)); });
    expect(root.toJSON()).toMatchObject({ children: ["old counts"] });
    await act(async () => invalidateRepositoryResources("refresh/repo"));
    expect(root.toJSON()).toMatchObject({ children: ["complete counts"] });
  } finally { await act(async () => root?.unmount()); }
});

test("expanded maps retain every file beyond the old drawing limit", () => {
  const files = Array.from({ length: 201 }, (_, i) => ({ path: `file-${i}.ts`, alive: true }));
  const data = { ...mapFixture, files, features: [{ ...mapFixture.features[0], entrypoints: files.map(f => f.path) }], imports: [] } as RepositoryMap;
  const graph = mapGraph(data, data.features[0].id, null, false);
  expect(graph.nodes.filter(n => n.kind === "file")).toHaveLength(201);
  expect(graph.omitted).toBe(0);
});

test("map loading assembles all pages before exposing a complete graph", async () => {
  const original = globalThis.fetch;
  const base = { ...mapFixture, total_files: 3, total_imports: 1, total_features: 0, features: [], index_status: "ready" };
  globalThis.fetch = async url => {
    const page = new URL(String(url), "http://localhost").searchParams.get("structure_page");
    return Response.json(page === "0" ? { ...base, structure_page: 0, structure_has_more: true, files: [{ path: "a.ts", alive: true }], imports: [{ source: "a.ts", target: "c.ts", line: 1, specifier: "./c" }] } :
      { ...base, structure_page: 1, structure_has_more: false, files: [{ path: "b.ts", alive: true }, { path: "c.ts", alive: true }], imports: [], commits: [] });
  };
  try {
    const result = await api.repositoryMap("o/r", 0);
    expect(result.files.map(f => f.path)).toEqual(["a.ts", "b.ts", "c.ts"]);
    expect(result.imports[0].target).toBe("c.ts");
    expect(result.structure_has_more).toBe(false);
  } finally { globalThis.fetch = original; }
});

test("map loading rejects missing nodes and changing snapshots", async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async () => Response.json({ ...mapFixture, total_files: 100 });
    await expect(api.repositoryMap("o/r", 0)).rejects.toThrow("incomplete");
    globalThis.fetch = async url => Response.json({ ...mapFixture, structure_page: 0, structure_has_more: true,
      head_sha: String(url).includes("structure_page=1") ? "new-version" : mapFixture.head_sha });
    await expect(api.repositoryMap("o/r", 0)).rejects.toThrow("changed while");
  } finally { globalThis.fetch = original; }
});

test("backend errors retain the actionable message", async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({ error: "The graph is unavailable", request_id: "test" }), { status: 503 });
  try {
    await expect(api.repos()).rejects.toThrow("The graph is unavailable");
  } finally { globalThis.fetch = original; }
});

test("stalled response bodies time out with a retry message", async () => {
  const originalFetch = globalThis.fetch;
  const originalTimeout = AbortSignal.timeout;
  const deadline = new AbortController();
  AbortSignal.timeout = () => deadline.signal;
  globalThis.fetch = async (_url, init) => ({ text: () => new Promise((_resolve, reject) => {
    init!.signal!.addEventListener("abort", () => reject(init!.signal!.reason), { once: true });
    queueMicrotask(() => deadline.abort(new DOMException("Timed out", "TimeoutError")));
  }) }) as Response;
  try {
    await expect(api.repos()).rejects.toThrow("taking longer than expected");
  } finally { globalThis.fetch = originalFetch; AbortSignal.timeout = originalTimeout; }
});

test("cancelling an answer aborts the network request", async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async (_url, init) => new Promise((_resolve, reject) => {
    init!.signal!.addEventListener("abort", () => reject(init!.signal!.reason), { once: true });
  });
  try {
    const controller = new AbortController();
    const result = api.ask({ repo: "o/r", question: "why?", mode: "graph", at: null }, controller.signal);
    controller.abort();
    await expect(result).rejects.toMatchObject({ name: "AbortError" });
  } finally { globalThis.fetch = original; }
});

test("utterance citations link to the actual meeting and numbered utterance", () => {
  expect(hrefFor("utt:mtg:PDGamerSG/Untangle:handover#0007", "utterance")).toEqual({
    href: "/meetings/mtg%3APDGamerSG%2FUntangle%3Ahandover#utt-7", external: false,
  });
  expect(hrefFor("mtg:PDGamerSG/Untangle:handover", "meeting")?.href).toContain("mtg%3A");
});

test("handover uploads preserve browser multipart boundaries", async () => {
  const original = globalThis.fetch;
  let sent: RequestInit | undefined;
  globalThis.fetch = async (_url, init) => { sent = init; return Response.json({ meeting_id: "mtg:o/r:call" }); };
  try {
    const body = new FormData(); body.set("repo", "o/r");
    await api.ingestMeeting(body);
    expect(sent?.body).toBe(body);
    expect(new Headers(sent?.headers).has("Content-Type")).toBe(false);
  } finally { globalThis.fetch = original; }
});

const decision = pulse.risks[0].decision as DecisionCard;

test("commit impact follows consumers, excludes unrelated features and terminates on cycles", () => {
  const data = mapFixture as RepositoryMap;
  const impact = commitImpact(data, data.commits[0]);
  expect(impact.features.map(f => f.feature.name)).toEqual(["Ask", "Pulse"]);
  expect(impact.features[0].path).toEqual(["ask.ts", "shared.ts"]);
  const leaf = { ...data.commits[0], files: [{ path: "ask.ts", change: "M" }] };
  expect(commitImpact(data, leaf).features.map(f => f.feature.name)).toEqual(["Ask"]);
  const cyclic = { ...data, imports: [...data.imports, { source: "shared.ts", target: "ask.ts", line: 3, specifier: "./ask" }] };
  expect(commitImpact(cyclic, data.commits[0]).features).toHaveLength(2);
  expect([...featureFiles(cyclic, data.features[0])].sort()).toEqual(["ask.ts", "shared.ts"]);
  expect(commitImpact(data, { ...leaf, files: [{ path: "deleted.ts", change: "D" }] }).unindexed).toEqual(["deleted.ts"]);
});

test("historical membership survives deduplication without treating a later record as in force", () => {
  const later = { ...decision, id: "dec:o/r:later", valid_from_iso: "2021-01-01T00:00:00Z" };
  const entries = snapshotDecisions({ at_iso: "2020-07-10T23:59:59Z", active: [decision], superseded_since: [decision, later] });
  expect(entries.map(entry => ({ id: entry.decision.id, inForce: entry.inForce, replacedSince: entry.replacedSince }))).toEqual([
    { id: decision.id, inForce: true, replacedSince: true },
    { id: later.id, inForce: false, replacedSince: true },
  ]);
});

test("decision search combines person, path and rationale terms", () => {
  const entry = { ...decision, stated_by: { id: "person:gh:sam", name: "Sam" }, rationale: "Prevent connection exhaustion", about: [{ id: "cfg:o/r:pool", name: "pool_size", label: "ConfigKey", path: "settings/database.yaml" }] };
  expect(matchesDecision(entry, "  SAM database.yaml exhaustion ")).toBe(true);
  expect(matchesDecision(entry, "sam missing-file.ts")).toBe(false);
});

test("downloaded briefs escape source text, reject executable URLs and keep internal evidence links", () => {
  const untrusted = { ...decision, subject: "<script>alert(1)</script>", text: "[click](javascript:alert(1))", decided_in: { id: "doc:o/r:source", kind: "document", title: "[unsafe]", url: "javascript:alert(1)" } };
  const markdown = decisionBrief("o/r", "2020-07-10", [{ decision: untrusted, inForce: true, replacedSince: false }], "https://untangle.example");
  expect(markdown).not.toContain("<script>");
  expect(markdown).toContain("&lt;script&gt;");
  expect(markdown).toContain("\\[click\\]");
  expect(markdown).toContain("Source: \\[unsafe\\] — doc:o/r:source");
  expect(markdown).toContain(`https://untangle.example/decisions/${encodeURIComponent(decision.id)}`);
  const meetingSource = { ...decision, decided_in: { id: "utt:mtg:o/r:handover#0007", kind: "utterance", title: "Handover" } };
  expect(decisionBrief("o/r", "2020-07-10", [{ decision: meetingSource, inForce: true, replacedSince: false }], "https://untangle.example"))
    .toContain("https://untangle.example/meetings/mtg%3Ao%2Fr%3Ahandover#utt-7");
});
