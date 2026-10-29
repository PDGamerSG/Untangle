import { expect, test } from "@playwright/test";
import { api, hrefFor } from "../src/lib/api";

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
