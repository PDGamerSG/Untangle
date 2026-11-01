"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { forceCenter, forceCollide, forceLink, forceManyBody, forceSimulation, forceX, forceY, type SimulationLinkDatum, type SimulationNodeDatum } from "d3-force";
import { Minus, Plus, RotateCcw } from "lucide-react";
import type { MapEdge, MapNode } from "@/lib/repository-map";

interface Node extends MapNode, SimulationNodeDatum {}
interface Edge extends SimulationLinkDatum<Node> { kind: MapEdge["kind"]; label?: string }
const colors = { feature: "var(--accent)", file: "var(--ink-3)", commit: "var(--warn)" };

function nodeLabel(node: MapNode): string[] {
  if (node.kind !== "feature") return [node.name.length > 28 ? `${node.name.slice(0, 25)}…` : node.name];
  const words = node.name.split(/\s+/);
  const lines = [words.shift() ?? ""];
  for (const word of words) {
    if (`${lines[lines.length - 1]} ${word}`.length > 18 && lines.length < 2) lines.push(word);
    else lines[lines.length - 1] += ` ${word}`;
  }
  return lines.map(line => line.length > 18 ? `${line.slice(0, 17)}…` : line);
}

const nodeRadius = (node: MapNode) => node.kind === "feature" ? 25 : node.kind === "commit" ? 15 : 9;

function layout(nodesIn: MapNode[], edgesIn: MapEdge[], W: number, H: number) {
  const nodes: Node[] = nodesIn.map(n => ({ ...n }));
  const edges: Edge[] = edgesIn.map(e => ({ ...e }));
  let seed = 21;
  const simulation = forceSimulation(nodes).randomSource(() => ((seed = seed * 16807 % 2147483647) - 1) / 2147483646)
    .force("link", forceLink<Node, Edge>(edges).id(n => n.id).distance(e => e.kind === "shared" ? 190 : 100).strength(0.35))
    .force("charge", forceManyBody().strength(-800)).force("collide", forceCollide(48))
    .force("center", forceCenter(W / 2, H / 2))
    // Keep isolated components near the graph so fitting cannot crush connected nodes.
    .force("x", forceX(W / 2).strength(0.12)).force("y", forceY(H / 2).strength(0.12)).stop();
  for (let i = 0; i < 240; i++) simulation.tick();
  // Fit the initial graph into the viewport; zoom and drag preserve the calculated geometry.
  const minX = Math.min(...nodes.map(n => n.x!)), maxX = Math.max(...nodes.map(n => n.x!));
  const minY = Math.min(...nodes.map(n => n.y!)), maxY = Math.max(...nodes.map(n => n.y!));
  const scale = Math.min(1.6, (W - 140) / Math.max(1, maxX - minX), (H - 120) / Math.max(1, maxY - minY));
  for (const n of nodes) { n.x = W / 2 + (n.x! - (minX + maxX) / 2) * scale; n.y = H / 2 + (n.y! - (minY + maxY) / 2) * scale; }
  // Fitting changes distances, but labels stay at readable CSS sizes. Resolve their
  // screen-space bounds after fitting, including space below each feature's circle.
  const boxes = nodes.map(node => {
    const labels = nodeLabel(node), radius = nodeRadius(node);
    const showLabel = node.kind === "feature" || nodes.length <= 12;
    return { node, width: Math.max((radius + 7) * 2, showLabel ? Math.max(...labels.map(label => label.length)) * (node.kind === "feature" ? 8 : 6) : 0) + 12,
      top: radius + 13, bottom: showLabel ? radius + 27 + (labels.length - 1) * 16 : radius + 13 };
  });
  for (let tick = 0; tick < 180; tick++) {
    for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
      const a = boxes[i], b = boxes[j];
      const dx = a.node.x! - b.node.x!, dy = (a.node.y! + (a.bottom - a.top) / 2) - (b.node.y! + (b.bottom - b.top) / 2);
      const overlapX = (a.width + b.width) / 2 - Math.abs(dx), overlapY = (a.top + a.bottom + b.top + b.bottom) / 2 - Math.abs(dy);
      if (overlapX <= 0 || overlapY <= 0) continue;
      if (overlapX < overlapY) { const shift = (overlapX + 0.5) * (dx < 0 ? -0.5 : 0.5); a.node.x! += shift; b.node.x! -= shift; }
      else { const shift = (overlapY + 0.5) * (dy < 0 ? -0.5 : 0.5); a.node.y! += shift; b.node.y! -= shift; }
    }
    for (const box of boxes) {
      box.node.x = Math.max(box.width / 2 + 8, Math.min(W - box.width / 2 - 8, box.node.x!));
      box.node.y = Math.max(box.top + 58, Math.min(H - box.bottom - 12, box.node.y!));
    }
  }
  return { nodes, edges };
}

export function RepositoryGraph({ nodes: inputNodes, edges: inputEdges, selected, onSelect }: {
  nodes: MapNode[]; edges: MapEdge[]; selected: string | null; onSelect: (node: MapNode) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(680);
  const W = width, H = 560;
  useEffect(() => {
    if (!container.current) return;
    const observer = new ResizeObserver(entries => setWidth(Math.max(280, entries[0].contentRect.width)));
    observer.observe(container.current);
    return () => observer.disconnect();
  }, []);
  const { nodes, edges } = useMemo(() => layout(inputNodes, inputEdges, W, H), [inputNodes, inputEdges, W, H]);
  const [view, setView] = useState({ x: 0, y: 0, zoom: 1 });
  const drag = useRef<{ x: number; y: number; startX: number; startY: number } | null>(null);
  const arrow = useId().replace(/:/g, "");
  const zoom = (factor: number) => setView(v => ({ ...v, zoom: Math.max(0.5, Math.min(3, v.zoom * factor)) }));
  return <div className="map-canvas" ref={container}>
    <div className="absolute right-3 top-3 z-10 flex gap-1 rounded-lg border border-rule bg-surface p-1">
      <button className="btn btn-ghost btn-sm" type="button" aria-label="Zoom out" onClick={() => zoom(0.8)}><Minus size={16} /></button>
      <button className="btn btn-ghost btn-sm" type="button" aria-label="Zoom in" onClick={() => zoom(1.25)}><Plus size={16} /></button>
      <button className="btn btn-ghost btn-sm" type="button" aria-label="Reset graph view" onClick={() => setView({ x: 0, y: 0, zoom: 1 })}><RotateCcw size={15} /></button>
    </div>
    <svg viewBox={`0 0 ${W} ${H}`} style={{ height: H }} className="block w-full touch-none" role="group" aria-label="Repository graph"
      onPointerDown={event => { if ((event.target as Element).closest("[data-node]")) return; event.currentTarget.setPointerCapture(event.pointerId); drag.current = { x: event.clientX, y: event.clientY, startX: view.x, startY: view.y }; }}
      onPointerMove={event => { if (!drag.current) return; const factor = W / event.currentTarget.getBoundingClientRect().width; setView(v => ({ ...v, x: drag.current!.startX + (event.clientX - drag.current!.x) * factor, y: drag.current!.startY + (event.clientY - drag.current!.y) * factor })); }}
      onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }}>
      <defs><marker id={arrow} viewBox="0 0 10 10" refX="21" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L10 5L0 10Z" fill="var(--ink-3)" /></marker></defs>
      <g transform={`translate(${W / 2 + view.x}, ${H / 2 + view.y}) scale(${view.zoom}) translate(${-W / 2}, ${-H / 2})`}>
        {edges.map((edge, i) => {
          const a = edge.source as Node, b = edge.target as Node;
          const active = selected === a.id || selected === b.id;
          return <g key={i} opacity={active ? 0.85 : 0.5}>
            <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={edge.kind === "changes" ? "var(--bad)" : active ? "var(--accent)" : "var(--ink-3)"} strokeWidth={active ? 2.3 : 1.2} strokeDasharray={edge.kind === "shared" ? "4 5" : undefined} markerEnd={edge.kind === "shared" ? undefined : `url(#${arrow})`} />
            <title>{edge.kind === "shared" ? edge.label : `${a.name} ${edge.kind} ${b.name}`}</title>
          </g>;
        })}
        {nodes.map(node => {
          const active = selected === node.id;
          const radius = nodeRadius(node);
          const color = node.affected ? "var(--bad)" : colors[node.kind];
          return <g key={node.id} data-node={node.id} role="button" tabIndex={0} aria-label={`${node.kind[0].toUpperCase() + node.kind.slice(1)} ${node.name}`} aria-pressed={active}
            className={`map-node${node.kind !== "feature" && nodes.length > 12 && !active ? " map-node-quiet" : ""}`} transform={`translate(${node.x} ${node.y})`} onClick={() => onSelect(node)} onKeyDown={event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelect(node); } }}>
            <circle r={radius + 7} fill="none" stroke={active ? color : "transparent"} strokeWidth={2} />
            <circle className="map-node-dot" r={radius} fill={node.kind === "file" ? "var(--surface)" : color} stroke={color} strokeWidth={2} />
            {node.kind === "feature" ? <text textAnchor="middle" y={5} fill="white" fontSize={13} fontWeight={700}>{node.name.slice(0, 2)}</text> : null}
            <text className="map-node-label" textAnchor="middle" y={radius + 21} fill="var(--ink)" fontSize={node.kind === "feature" ? 14 : 11} fontWeight={node.kind === "feature" ? 650 : 500} stroke="var(--surface)" strokeWidth={5} paintOrder="stroke">{nodeLabel(node).map((line, i) => <tspan key={i} x={0} dy={i ? 16 : 0}>{line}</tspan>)}</text>
            <title>{node.id}</title>
          </g>;
        })}
      </g>
    </svg>
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-rule bg-surface/90 px-4 py-3 text-[0.76rem] text-ink-2">
      <span className="inline-flex items-center gap-1.5"><i className="h-2.5 w-2.5 rounded-full bg-accent" />Feature</span>
      <span className="inline-flex items-center gap-1.5"><i className="h-2.5 w-2.5 rounded-full border border-ink-3" />File</span>
      <span className="inline-flex items-center gap-1.5"><i className="h-2.5 w-2.5 rounded-full bg-warn" />Commit</span>
      <span className="inline-flex items-center gap-1.5"><i className="h-2.5 w-2.5 rounded-full bg-bad" />Potential impact</span>
      <span className="ml-auto">Drag to pan · select a node{nodes.length > 12 ? " · focus or hover for names" : ""}</span>
    </div>
  </div>;
}
