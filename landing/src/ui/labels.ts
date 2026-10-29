import { Vector3 } from "three";
import { EVIDENCE, FRAGMENTS, HISTORY, RISKS } from "../data";
import type { Stage } from "../gl/stage";
import { mulberry32 } from "../gl/threads";
import type { Frame, World } from "../story";

const tmp = new Vector3();
const scr = new Vector3();

function el<K extends keyof HTMLElementTagNameMap>(tag: K, cls: string, html?: string) {
  const e = document.createElement(tag);
  e.className = cls;
  if (html !== undefined) e.innerHTML = html;
  return e;
}

function escapeHtml(s: string) {
  return s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);
}

export function yearFraction(iso: string) {
  const d = new Date(`${iso}T00:00:00Z`);
  const start = Date.UTC(d.getUTCFullYear(), 0, 1);
  const end = Date.UTC(d.getUTCFullYear() + 1, 0, 1);
  return d.getUTCFullYear() + (d.getTime() - start) / (end - start);
}

interface Placed {
  node: HTMLElement;
  world: Vector3;
}

/** DOM labels that ride on positions in the 3D scene. */
export class Labels {
  private fragments: (Placed & { seed: number })[] = [];
  private tags: (Placed & { x: number; sway: number; vel: number })[] = [];
  private ticks: Placed[] = [];
  private knots: (Placed & { date: number })[] = [];
  private lanes: Placed[] = [];
  private groups: Record<string, HTMLElement> = {};
  private lastCamX = 0;

  constructor(layer: HTMLElement) {
    for (const g of ["fragments", "tags", "timeline", "lanes"]) {
      const d = el("div", `group group--${g}`);
      d.style.cssText = "position:absolute;inset:0;opacity:0;";
      this.groups[g] = d;
      layer.append(d);
    }
  }

  build(world: World) {
    for (const g of Object.values(this.groups)) g.textContent = "";
    this.fragments = [];
    this.tags = [];
    this.ticks = [];
    this.knots = [];
    this.lanes = [];

    // Fragments float inside the ball, around the path the camera dives along.
    const rand = mulberry32(942);
    const b = world.ball;
    FRAGMENTS.forEach((text, i) => {
      const code = /[=_]|^#|^\d{3}/.test(text);
      const node = el("span", code ? "fragment fragment--code" : "fragment", escapeHtml(text));
      const a = rand() * Math.PI * 2;
      const r = 0.35 + rand() * 1.1;
      const z = 1.9 - (i / FRAGMENTS.length) * 3.6 + (rand() - 0.5) * 0.4;
      const pos = new Vector3(b.x + Math.cos(a) * r * 1.35, b.y + Math.sin(a) * r * 0.85, z);
      this.groups.fragments.append(node);
      this.fragments.push({ node, world: pos, seed: rand() });
    });

    // Evidence tags hang from the red thread.
    EVIDENCE.forEach((t, i) => {
      const title = t.titleIsCode ? `<code>${escapeHtml(t.title)}</code>` : escapeHtml(t.title);
      const note = t.href
        ? `<a href="${t.href}" tabindex="-1">${escapeHtml(t.note)}</a>`
        : escapeHtml(t.note);
      const node = el(
        "div",
        "tag",
        `<span class="tag__string"></span><span class="tag__bead"></span>
         <div class="tag__body" style="--drop-i:${i}">
           <span class="tag__kind">${escapeHtml(t.kind)}</span>
           <span class="tag__title"${t.titleLang ? ` lang="${t.titleLang}"` : ""}>${title}</span>
           <span class="tag__note">${note}</span>
         </div>`,
      );
      // Alternate drop lengths so neighbouring labels don't line up like cards.
      node.style.setProperty("--drop", `${[3.2, 5.6, 3.8, 6.4, 3.4, 5.2][i]}rem`);
      this.groups.tags.append(node);
      this.tags.push({ node, world: new Vector3(world.tagX[i], world.lineY, 0), x: world.tagX[i], sway: 0, vel: 0 });
    });

    // Years along the red lane.
    for (let y = 2018; y <= 2027; y++) {
      const node = el("span", "tick", String(y));
      this.groups.timeline.append(node);
      this.ticks.push({ node, world: new Vector3(world.xOfYear(y), world.lineY - 0.32, 0.3) });
    }
    for (const [i, h] of HISTORY.entries()) {
      const date = yearFraction(h.date);
      const nice = new Date(`${h.date}T00:00:00Z`).toLocaleDateString("en-GB", {
        day: "numeric",
        month: "short",
        year: "numeric",
        timeZone: "UTC",
      });
      const node = el(
        "div",
        i % 2 ? "knotmark knotmark--below" : "knotmark",
        `<span class="knotmark__dot"></span>
         <span class="knotmark__text">
           <span class="knotmark__value">${h.call ? "Call" : escapeHtml(h.value)}</span>
           <span class="knotmark__label">${escapeHtml(h.label)}</span>
           <span class="knotmark__date">${nice}, <code>${escapeHtml(h.where)}</code></span>
         </span>`,
      );
      this.groups.timeline.append(node);
      this.knots.push({ node, world: new Vector3(world.xOfYear(date), world.lineY, 0.3), date });
    }

    // Labels that ride on the risk lanes in Pulse.
    RISKS.forEach((r, i) => {
      const node = el("span", "tick lane-tag", `${escapeHtml(r.category)} <strong>${r.score.toFixed(2)}</strong>`);
      node.style.color = i === 0 ? "var(--madder)" : "var(--cotton)";
      this.groups.lanes.append(node);
      this.lanes.push({ node, world: new Vector3() });
    });
  }

  private place(node: HTMLElement, world: Vector3, stage: Stage, dx = 0, dy = 0) {
    stage.project(world, scr);
    const off = scr.z > 1 || scr.x < -400 || scr.x > window.innerWidth + 400;
    node.style.visibility = off ? "hidden" : "visible";
    if (!off) node.style.transform = `translate3d(${(scr.x + dx).toFixed(1)}px, ${(scr.y + dy).toFixed(1)}px, 0)`;
    return !off;
  }

  update(f: Frame, w: World, stage: Stage, laneYs: [number, number, number], year: number, dt: number) {
    for (const [g, node] of Object.entries(this.groups)) {
      const o = f.groups[g as keyof Frame["groups"]];
      node.style.opacity = o.toFixed(3);
      node.style.display = o > 0.001 ? "block" : "none";
    }

    if (f.groups.fragments > 0) {
      const cam = stage.camera.position;
      for (const fr of this.fragments) {
        const depth = cam.z - fr.world.z;
        const vis = depth > 0.25 ? Math.min(1, (depth - 0.25) / 0.6) * Math.min(1, Math.max(0, (7 - depth) / 3)) : 0;
        if (vis <= 0.01) {
          fr.node.style.visibility = "hidden";
          continue;
        }
        if (this.place(fr.node, fr.world, stage)) {
          const scale = Math.min(2.6, 2.4 / depth);
          fr.node.style.transform += ` scale(${scale.toFixed(3)})`;
          fr.node.style.opacity = (vis * (0.5 + fr.seed * 0.5)).toFixed(3);
        }
      }
    }

    if (f.groups.tags > 0) {
      // Labels swing a little when the thread moves under them.
      const camX = stage.camera.position.x;
      const v = (camX - this.lastCamX) / Math.max(dt, 1 / 120);
      for (const t of this.tags) {
        tmp.set(t.x, w.lineY - Math.sin(Math.PI * Math.min(1, Math.max(0, (t.x - w.ball.x) / (f.needleX - w.ball.x + 1e-3)))) * 0.12, 0);
        const sewn = f.needleX > t.x + 0.15 && f.pull > 0.4;
        t.node.classList.toggle("is-sewn", sewn);
        t.vel += (-t.sway * 40 - t.vel * 6 - v * 0.9) * dt;
        t.sway = Math.max(-9, Math.min(9, t.sway + t.vel * dt));
        t.node.style.setProperty("--sway", `${t.sway.toFixed(2)}deg`);
        this.place(t.node, tmp, stage, -24, 0);
      }
    }
    this.lastCamX = stage.camera.position.x;

    if (f.groups.timeline > 0) {
      for (const t of this.ticks) this.place(t.node, t.world, stage, -2, 0);
      const now = year;
      let current = -1;
      this.knots.forEach((k, i) => {
        if (k.date <= now) current = i;
      });
      this.knots.forEach((k, i) => {
        this.place(k.node, k.world, stage);
        const shown = k.date <= now + 0.08;
        k.node.style.opacity = shown ? "1" : "0.25";
        // The handover call confirms the current value, so the 2020 decision stays current.
        const currentIdx = current === 3 ? 2 : current;
        k.node.classList.toggle("is-current", i === currentIdx || (i === 3 && current === 3));
        k.node.classList.toggle("is-superseded", i < 2 && current >= i + 1);
      });
    }

    if (f.groups.lanes > 0) {
      const x = stage.camera.position.x + (w.portrait ? -1.2 : -0.6);
      this.lanes.forEach((l, i) => {
        l.world.set(x, laneYs[i] + 0.12, i === 0 ? 0.3 : 0);
        this.place(l.node, l.world, stage, 0, -8);
      });
    }
  }
}
