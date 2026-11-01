import { expect, test } from "@playwright/test";
import { api, hrefFor } from "../src/lib/api";
import { decisionBrief, matchesDecision, snapshotDecisions } from "../src/lib/evidence-brief";
import type { DecisionCard } from "../src/lib/types";
import pulse from "../sample/pulse.json";
import mapFixture from "../sample/repository-map.json";
import { commitImpact, featureFiles, type RepositoryMap } from "../src/lib/repository-map";

test("backend errors retain the actionable message", async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({ error: "The graph is unavailable", request_id: "test" }), { status: 503 });
  try {
    await expect(api.repos()).rejects.toThrow("The graph is unavailable");
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
