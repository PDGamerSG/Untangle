import type { BriefingResponse, PreflightResponse } from "./types";

/** Example changes built from the repository's own history: values a later decision replaced make the clearest demo
 * (setting one back is exactly what a pre-flight check should catch), then files guarded by recorded decisions. */
export function preflightExamples(briefing: BriefingResponse | undefined, fallback: string[]): string[] {
  const out: string[] = [];
  for (const change of briefing?.changes ?? []) {
    const older = change.older;
    if (!older.object || older.object.toLowerCase() === "removed" || older.object.length > 40) continue;
    if (older.kind !== "config_value" && older.kind !== "dependency") continue;
    const subject = older.subject.includes("::") ? older.subject.split("::")[1] : older.subject;
    const line = older.kind === "dependency" ? `Downgrade ${subject} to ${older.object}` : `Set ${subject} back to ${older.object}`;
    if (!out.includes(line)) out.push(line);
    if (out.length >= 2) break;
  }
  for (const g of briefing?.guarded ?? []) {
    const path = g.decision.about.find((a) => a.path)?.path;
    if (path && !out.some((x) => x.includes(path))) out.push(`Refactor ${path}`);
    if (out.length >= 4) break;
  }
  return out.length ? out : fallback;
}

/** Paths typed into the files box: commas, spaces or new lines separate them. */
export function splitPaths(value: string): string[] {
  return [...new Set(value.split(/[\s,]+/).map((p) => p.trim()).filter(Boolean))].slice(0, 50);
}

/** The check as a Markdown note to paste into a pull request description or a review thread. */
export function preflightMarkdown(res: PreflightResponse, change: string, origin: string): string {
  const lines = [`# Pre-flight check: ${res.repo}`, "", `Review level: **${res.review.level}** (${res.review.score}/100)`, ""];
  if (change.trim()) lines.push("```", change.trim().slice(0, 4000), "```", "");
  if (res.review.reasons.length) lines.push("## Why", "", ...res.review.reasons.map((r) => `- +${r.points} ${r.text}`), "");
  if (res.revivals.length) {
    lines.push("## Brings back a replaced value", "");
    for (const r of res.revivals) {
      lines.push(`- \`${r.target}\` = \`${r.proposed}\`: replaced by "${r.replaced_by.text}" (${origin}/decisions/${encodeURIComponent(r.replaced_by.id)}).${r.reason ? ` ${r.reason}` : ""}`);
    }
    lines.push("");
  }
  if (res.advisories.introduced.length) {
    lines.push("## Public advisories", "");
    for (const a of res.advisories.introduced) lines.push(`- ${a.package}@${a.version}: [${a.advisory.id}](${a.advisory.url ?? ""}) ${a.advisory.summary ?? ""}`.trimEnd());
    lines.push("");
  }
  if (res.decisions.length) {
    lines.push("## Decisions to read first", "");
    for (const g of res.decisions) lines.push(`- [${g.decision.text}](${origin}/decisions/${encodeURIComponent(g.decision.id)})${g.guards.length ? `: ${g.guards.join("; ")}` : ""}`);
    lines.push("");
  }
  if (res.reach.reached.length || res.reach.tests.length || res.reach.cochanged.length) {
    lines.push("## Reach", "");
    for (const r of res.reach.reached) lines.push(`- ${r.path} (hop ${r.hop}${r.via.length > 2 ? ` via ${r.via.slice(1, -1).join(" → ")}` : ""})`);
    if (res.reach.tests.length) lines.push(`- Tests: ${res.reach.tests.join(", ")}`);
    for (const c of res.reach.cochanged) lines.push(`- Usually changed together: ${c.path} (${c.together} of ${c.total} commits)`);
    lines.push("");
  }
  if (res.people.length) lines.push("## Who to ask", "", ...res.people.map((p) => `- ${p.name}${p.why ? `: ${p.why}` : ""}`), "");
  lines.push("## Next steps", "", ...res.next_steps.map((s) => `- ${s.text}`), "", "## Limits", "", ...res.limits.map((l) => `- ${l}`), "");
  return lines.join("\n");
}
