import { hrefFor } from "./api";
import type { DecisionCard, PulseRisk, Ref, Timeline } from "./types";

export interface SnapshotDecision {
  decision: DecisionCard;
  inForce: boolean;
  replacedSince: boolean;
}

/** A historical decision can appear in both groups. Keep one row and both facts. */
export function snapshotDecisions(snapshot: Timeline): SnapshotDecision[] {
  const entries = new Map<string, SnapshotDecision>();
  for (const decision of snapshot.active) entries.set(decision.id, { decision, inForce: true, replacedSince: false });
  for (const decision of snapshot.superseded_since) {
    const existing = entries.get(decision.id);
    if (existing) existing.replacedSince = true;
    else entries.set(decision.id, { decision, inForce: false, replacedSince: true });
  }
  return [...entries.values()];
}

export function matchesDecision(decision: DecisionCard, query: string): boolean {
  const text = [decision.subject, decision.object, decision.text, decision.rationale, decision.stated_by?.name,
    decision.stated_by?.login, decision.decided_in?.title, ...decision.about.flatMap(e => [e.name, e.path])].join(" ").toLowerCase();
  return query.toLowerCase().trim().split(/\s+/).every(term => text.includes(term));
}

// Repository text is data, even when someone opens the export in a Markdown renderer.
function plain(text: string | null | undefined): string {
  return (text ?? "").replace(/\s+/g, " ").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/([\\`*_[\]#|])/g, "\\$1");
}

function link(title: string, href: string, origin: string): string {
  try {
    const url = new URL(href, origin);
    if (!["https:", "http:"].includes(url.protocol)) return plain(title);
    return `[${plain(title)}](${url.href.replace(/\(/g, "%28").replace(/\)/g, "%29")})`;
  } catch { return plain(title); }
}

function reference(ref: Ref, origin: string): string {
  const target = hrefFor(ref.id, ref.kind, ref.url);
  return `${target ? link(ref.title || ref.id, target.href, origin) : plain(ref.title || ref.id)} — ${plain(ref.id)}`;
}

function decisionLines(decision: DecisionCard, origin: string): string[] {
  return [
    `### ${plain(decision.subject)}`,
    "",
    `- Decision: ${link(decision.id, `/decisions/${encodeURIComponent(decision.id)}`, origin)}`,
    `- Value: ${plain(decision.object)}`,
    `- Current status: ${plain(decision.status)}`,
    `- Valid from: ${plain(decision.valid_from_iso)}; valid until: ${plain(decision.valid_to_iso) || "no end recorded"}`,
    `- Stated by: ${plain(decision.stated_by?.name || decision.stated_by?.login) || "no person recorded"}`,
    `- Rationale: ${plain(decision.rationale) || "No reason recorded."}`,
    `- Record: ${plain(decision.text)}`,
    `- Source: ${decision.decided_in ? reference(decision.decided_in, origin) : "No source linked."}`,
    ...decision.about.map(e => `- About: ${plain(e.name)}${e.path ? ` in ${plain(e.path)}` : ""} (${plain(e.id)})`),
    "",
  ];
}

export function decisionBrief(repo: string, atIso: string, entries: SnapshotDecision[], origin: string): string {
  return [
    "# Untangle decision brief", "", `Repository: ${plain(repo)}`, `Snapshot: ${plain(atIso)}`, "",
    `Scope: ${entries.length} filtered decisions from the loaded snapshot (up to 100 records). This is not a complete repository audit.`, "",
    ...entries.flatMap(entry => [
      ...decisionLines(entry.decision, origin),
      `In force at the snapshot: ${entry.inForce ? "yes" : "no"}. Replaced after the snapshot: ${entry.replacedSince ? "yes" : "no"}.`, "",
    ]),
  ].join("\n");
}

export function riskBrief(repo: string, generatedAt: string, risks: PulseRisk[], origin: string): string {
  return [
    "# Untangle risk brief", "", `Repository: ${plain(repo)}`, `Generated: ${plain(generatedAt)}`, "",
    `Scope: ${risks.length} filtered risks from the returned priority queue. Scores are heuristic signals, not probabilities or a complete repository audit.`, "",
    ...risks.flatMap(risk => [
      ...decisionLines(risk.decision, origin),
      `- Risk: ${plain(risk.id)} (${plain(risk.category)})`,
      `- Score: ${Math.round(risk.score * 100)}/100`,
      `- Recent owner: ${plain(risk.owner?.name || risk.owner?.login) || "No recent owner recorded."}`,
      ...risk.reasons.map(reason => `- Signal: ${plain(reason)}`),
      ...risk.evidence.map(ref => `- Evidence: ${reference(ref, origin)}`),
      ...risk.contradictions.map(ref => `- Conflicting evidence: ${reference(ref, origin)}`), "",
    ]),
  ].join("\n");
}

export function briefFilename(repo: string, suffix: string): string {
  return `untangle-${repo.replace(/[^a-z0-9_-]/gi, "-")}-${suffix}.md`;
}
