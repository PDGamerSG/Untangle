"use client";

import { useMemo, useState } from "react";
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from "d3-force";
import { fmtOffset, kindFromLabel, truncate } from "@/lib/format";
import type { Subgraph as SubgraphT } from "@/lib/types";

interface N extends SimulationNodeDatum {
  id: string;
  label: string;
  props: Record<string, unknown>;
}
interface L extends SimulationLinkDatum<N> {
  type: string;
}

const W = 760;
const H = 460;
const R = 17;

function clamp(v: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, v));
}

/** Deterministic layout: a seeded random source and a fixed number of ticks, so the picture is stable across renders. */
function layout(sub: SubgraphT): { nodes: N[]; links: L[] } {
  const nodes: N[] = sub.nodes.map((n) => ({ id: n.id, label: n.label, props: n.props ?? {} }));
  const ids = new Set(nodes.map((n) => n.id));
  const links: L[] = sub.edges.filter((e) => ids.has(e.from) && ids.has(e.to)).map((e) => ({ source: e.from, target: e.to, type: e.type }));
  let seed = 7;
  const random = () => {
    seed = (seed * 16807) % 2147483647;
    return (seed - 1) / 2147483646;
  };
  const sim = forceSimulation<N>(nodes)
    .randomSource(random)
    .force(
      "link",
      forceLink<N, L>(links)
        .id((d) => d.id)
        .distance((l) => (l.type === "SUPERSEDES" ? 150 : 118))
        .strength(0.7),
    )
    .force("charge", forceManyBody().strength(-900))
    .force("center", forceCenter(W / 2, H / 2))
    .force("collide", forceCollide(R + 34))
    .force("x", forceX(W / 2).strength(0.03))
    .force("y", forceY(H / 2).strength(0.06))
    .stop();
  for (let i = 0; i < 320; i++) sim.tick();
  for (const n of nodes) {
    n.x = clamp(n.x ?? W / 2, R + 44, W - R - 44);
    n.y = clamp(n.y ?? H / 2, R + 14, H - R - 24);
  }
  return { nodes, links };
}

function str(v: unknown): string {
  if (v == null) return "";
  if (typeof v === "string") return v;
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  return JSON.stringify(v);
}

/** The short text under a node. */
function nodeName(n: N): string {
  const p = n.props;
  switch (n.label) {
    case "Decision":
      return truncate(str(p.object) || n.id, 22);
    case "PullRequest":
      return p.number != null ? `PR #${str(p.number)}` : truncate(str(p.title) || n.id, 18);
    case "Issue":
    case "Incident":
      return p.number != null ? `#${str(p.number)}` : truncate(str(p.title) || n.id, 18);
    case "Commit":
      return str(p.sha).slice(0, 7) || truncate(n.id.split(":").pop() ?? n.id, 10);
    case "Person":
      return truncate(str(p.name) || str(p.login) || n.id, 18);
    case "ConfigKey":
      return truncate(str(p.key) || n.id, 22);
    case "File":
      return truncate((str(p.path) || n.id).split("/").pop() ?? n.id, 22);
    case "Module":
      return truncate(str(p.path) || str(p.name) || n.id, 22);
    case "Dependency":
      return truncate((str(p.name) || n.id).split("/").pop() ?? n.id, 20);
    case "Utterance":
      return typeof p.start_ms === "number" ? `said @${fmtOffset(p.start_ms)}` : "utterance";
    case "Meeting":
      return truncate(str(p.title) || "meeting", 20);
    case "Document":
      return truncate(str(p.title) || n.id.split("/").pop() || n.id, 20);
    case "Comment":
      return p.author_login ? `@${str(p.author_login)}` : "comment";
    default:
      return truncate(str(p.name) || n.id, 18);
  }
}

const GLYPH: Record<string, string> = {
  Decision: "D",
  PullRequest: "PR",
  Issue: "I",
  Incident: "I",
  Commit: "C",
  Comment: "Cm",
  Document: "Doc",
  Utterance: "U",
  Person: "P",
  Meeting: "M",
  ConfigKey: "K",
  File: "F",
  Module: "Mod",
  Dependency: "Dep",
  Symbol: "S",
  Repo: "R",
};

export function Subgraph({ subgraph }: { subgraph: SubgraphT }) {
  const { nodes, links } = useMemo(() => layout(subgraph), [subgraph]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const active = nodes.find((n) => n.id === activeId) ?? null;
  const labels = Array.from(new Set(nodes.map((n) => n.label)));

  if (!nodes.length) return <p className="text-[0.85rem] text-ink-3">No subgraph returned for this answer.</p>;

  return (
    <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_16rem]">
      <div className="card overflow-hidden bg-surface">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="block h-auto w-full"
          role="img"
          aria-label={`Subgraph of ${nodes.length} nodes and ${links.length} relationships used for this answer`}
          onMouseLeave={() => setActiveId(null)}
        >
          <defs>
            <marker id="sg-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--rule-strong)" />
            </marker>
            <marker id="sg-arrow-bad" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--bad)" />
            </marker>
          </defs>
          <g>
            {links.map((l, i) => {
              const s = l.source as N;
              const t = l.target as N;
              const sx = s.x ?? 0;
              const sy = s.y ?? 0;
              const tx = t.x ?? 0;
              const ty = t.y ?? 0;
              const dx = tx - sx;
              const dy = ty - sy;
              const len = Math.hypot(dx, dy) || 1;
              const ux = dx / len;
              const uy = dy / len;
              const x1 = sx + ux * (R + 2);
              const y1 = sy + uy * (R + 2);
              const x2 = tx - ux * (R + 4);
              const y2 = ty - uy * (R + 4);
              const bad = l.type === "SUPERSEDES";
              const dim = activeId && activeId !== s.id && activeId !== t.id;
              return (
                <g key={i} opacity={dim ? 0.25 : 1}>
                  <line
                    x1={x1}
                    y1={y1}
                    x2={x2}
                    y2={y2}
                    stroke={bad ? "var(--bad)" : "var(--rule-strong)"}
                    strokeWidth={bad ? 2 : 1.4}
                    strokeDasharray={bad ? "7 5" : undefined}
                    markerEnd={bad ? "url(#sg-arrow-bad)" : "url(#sg-arrow)"}
                  />
                  <text
                    x={(x1 + x2) / 2}
                    y={(y1 + y2) / 2 - 4}
                    textAnchor="middle"
                    fontSize={8.5}
                    fontFamily="var(--font-code)"
                    fill={bad ? "var(--bad)" : "var(--ink-3)"}
                    stroke="var(--surface)"
                    strokeWidth={3}
                    paintOrder="stroke"
                    fontWeight={bad ? 700 : 500}
                  >
                    {l.type}
                  </text>
                </g>
              );
            })}
          </g>
          <g>
            {nodes.map((n) => {
              const kind = kindFromLabel(n.label);
              const dim = activeId && activeId !== n.id && !links.some((l) => ((l.source as N).id === activeId && (l.target as N).id === n.id) || ((l.target as N).id === activeId && (l.source as N).id === n.id));
              const superseded = n.label === "Decision" && str(n.props.status) === "superseded";
              return (
                <g
                  key={n.id}
                  className="sg-node"
                  data-kind={kind}
                  data-active={activeId === n.id}
                  transform={`translate(${n.x ?? 0} ${n.y ?? 0})`}
                  tabIndex={0}
                  role="button"
                  aria-label={`${n.label} ${nodeName(n)}`}
                  opacity={dim ? 0.35 : 1}
                  onMouseEnter={() => setActiveId(n.id)}
                  onFocus={() => setActiveId(n.id)}
                  onBlur={() => setActiveId(null)}
                  onClick={() => setActiveId(n.id)}
                >
                  <circle
                    className="sg-shape"
                    r={R}
                    style={{ fill: "var(--c-bg)", stroke: "var(--c)" }}
                    strokeWidth={1.6}
                    strokeDasharray={superseded ? "4 3" : undefined}
                  />
                  <text y={4} textAnchor="middle" fontSize={n.label === "Decision" ? 12 : 9} fontWeight={700} style={{ fill: "var(--c)" }}>
                    {GLYPH[n.label] ?? n.label.slice(0, 2)}
                  </text>
                  <text
                    y={R + 13}
                    textAnchor="middle"
                    fontSize={10}
                    fill="var(--ink-2)"
                    stroke="var(--surface)"
                    strokeWidth={3}
                    paintOrder="stroke"
                    style={{ textDecoration: superseded ? "line-through" : undefined }}
                  >
                    {nodeName(n)}
                  </text>
                </g>
              );
            })}
          </g>
        </svg>
        <div className="flex flex-wrap gap-x-3 gap-y-1 border-t border-rule px-3 py-2 text-[0.72rem] text-ink-2">
          {labels.map((l) => (
            <span key={l} className="inline-flex items-center gap-1.5" data-kind={kindFromLabel(l)}>
              <span className="inline-block h-2.5 w-2.5 rounded-full border" style={{ background: "var(--c-bg)", borderColor: "var(--c)" }} aria-hidden />
              {l}
            </span>
          ))}
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block h-0 w-4 border-t-2 border-dashed border-bad" aria-hidden /> SUPERSEDES
          </span>
        </div>
      </div>
      <aside className="card min-h-[8rem] p-3 text-[0.82rem]" aria-live="polite">
        {active ? (
          <>
            <p className="flex items-center gap-2" data-kind={kindFromLabel(active.label)}>
              <span className="chip">
                <span className="chip-kind">{active.label}</span>
              </span>
              <span className="truncate font-semibold text-ink">{nodeName(active)}</span>
            </p>
            <p className="t-code mt-1.5 break-all text-ink-3">{active.id}</p>
            <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
              {Object.entries(active.props).map(([k, v]) => (
                <div key={k} className="contents">
                  <dt className="t-code text-ink-3">{k}</dt>
                  <dd className="break-words text-ink-2">{str(v)}</dd>
                </div>
              ))}
            </dl>
          </>
        ) : (
          <p className="text-ink-3">
            Hover or focus a node to see its properties. {nodes.length} nodes, {links.length} relationships.
          </p>
        )}
      </aside>
    </div>
  );
}
