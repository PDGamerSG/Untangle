import { Quaternion, Vector3 } from "three";

/**
 * The story is a set of tracks keyed to scroll positions. A key's position is
 * written as at(section, f): f in [0, 1] runs across the section's pinned
 * stretch; negative f counts viewport heights before the pin starts.
 */
type Ease = "smooth" | "linear";
type Key = { y: number; v: number; ease: Ease };

export class Track {
  private keys: Key[];
  constructor(keys: Key[]) {
    this.keys = keys.sort((a, b) => a.y - b.y);
  }
  value(y: number) {
    const k = this.keys;
    if (y <= k[0].y) return k[0].v;
    const last = k[k.length - 1];
    if (y >= last.y) return last.v;
    let i = 0;
    while (i < k.length - 1 && y > k[i + 1].y) i++;
    const a = k[i];
    const b = k[i + 1];
    let t = (y - a.y) / Math.max(b.y - a.y, 1e-6);
    if (a.ease === "smooth") t = t * t * (3 - 2 * t);
    return a.v + (b.v - a.v) * t;
  }
}

export interface Section {
  id: string;
  el: HTMLElement;
  top: number;
  height: number;
}

/** World layout. Desktop and portrait screens frame the same story differently. */
export function worldFor(aspect: number) {
  const portrait = aspect < 1;
  const zoom = portrait ? 1 + (1 - aspect) * 1.15 : aspect < 1.35 ? 1.12 : 1;
  const ball = portrait ? new Vector3(0, 1.95, 0) : new Vector3(1.85, 0.15, 0);
  const ballR = portrait ? 1.05 : 1.5;
  const lineY = -0.3;
  const tagX = [5.6, 9.4, 13.2, 17, 20.8, 24.6];
  const timeX0 = 31; // x at 1 Jan 2018
  const perYear = 3.2;
  const xOfYear = (y: number) => timeX0 + (y - 2018) * perYear;
  const endX = xOfYear(2026.85);
  return {
    portrait,
    zoom,
    ball,
    ballR,
    lineY,
    tagX,
    pullStartX: ball.x + 1.7,
    pullEndX: 27.2,
    timeX0,
    perYear,
    xOfYear,
    timeStartX: xOfYear(2018.45),
    timeEndX: endX,
    needleLead: portrait ? 3.4 : 6,
    combCenter: new Vector3(42, lineY, -0.4),
    combSize: new Vector3(32, portrait ? 2.5 : 1.95, 1.4),
    weaveCenter: new Vector3(endX + 0.5, lineY - 0.1, -1.8),
    pulseX: endX - 1.2,
  };
}

export type World = ReturnType<typeof worldFor>;

export interface Frame {
  loosen: number;
  spin: number;
  comb: number;
  weave: number;
  voice: number;
  pull: number;
  fray: number;
  tension: number;
  dim: number;
  needleOut: number;
  needleX: number;
  detach: number;
  cam: Vector3;
  look: Vector3;
  groups: Record<"fragments" | "tags" | "timeline" | "lanes", number>;
  progress: Record<string, number>;
}

const pinnedHero = new Quaternion();
const freeQuat = new Quaternion().setFromAxisAngle(new Vector3(0, 0, 1), Math.PI / 2);

export class Director {
  sections: Section[] = [];
  world: World = worldFor(16 / 9);
  private vh = 1;
  private tracks: Record<string, Track> = {};
  private camTracks: Track[] = [];
  readonly frame: Frame = {
    loosen: 0,
    spin: 0,
    comb: 0,
    weave: 0,
    voice: 0,
    pull: 0,
    fray: 0,
    tension: 0,
    dim: 1,
    needleOut: 0,
    needleX: 0,
    detach: 0,
    cam: new Vector3(0, 0, 9.5),
    look: new Vector3(),
    groups: { fragments: 0, tags: 0, timeline: 0, lanes: 0 },
    progress: {},
  };

  constructor(private root: Document) {}

  measure() {
    this.vh = window.innerHeight;
    this.world = worldFor(window.innerWidth / window.innerHeight);
    this.sections = [...this.root.querySelectorAll<HTMLElement>("[data-section]")].map((el) => {
      const r = el.getBoundingClientRect();
      return { id: el.dataset.section!, el, top: r.top + window.scrollY, height: el.offsetHeight };
    });
    this.build();
  }

  private sec(id: string) {
    const s = this.sections.find((x) => x.id === id);
    if (!s) throw new Error(`missing section ${id}`);
    return s;
  }

  /** Scroll position for a point in a section's story. */
  at(id: string, f: number) {
    const s = this.sec(id);
    const run = Math.max(s.height - this.vh, 1);
    return f >= 0 ? s.top + f * run : s.top + f * this.vh;
  }

  /** Progress through a section's pinned stretch, unclamped. */
  progressOf(id: string, y: number) {
    const s = this.sec(id);
    return (y - s.top) / Math.max(s.height - this.vh, 1);
  }

  private track(points: [string, number, number, Ease?][]) {
    return new Track(points.map(([id, f, v, ease]) => ({ y: this.at(id, f), v, ease: ease ?? "smooth" })));
  }

  private build() {
    const W = this.world;
    const z = W.zoom;
    const lead = W.needleLead;

    this.tracks = {
      loosen: this.track([
        ["hero", 0, 0],
        ["knot", 0, 0.1],
        ["knot", 1, 0.7],
        ["pull", 0.2, 0.3],
      ]),
      spin: this.track([
        ["hero", 0, 0],
        ["knot", 1, 0.9],
      ]),
      comb: this.track([
        ["time", -0.9, 0],
        ["time", 0.22, 1],
      ]),
      weave: this.track([
        ["run", -0.4, 0],
        ["end", -0.2, 1],
      ]),
      voice: this.track([
        ["handover", -0.2, 0],
        ["handover", 0.08, 1],
        ["handover", 0.92, 1],
        ["handover", 1, 0],
      ]),
      pull: this.track([
        ["pull", -0.45, 0],
        ["pull", 0.16, 1],
      ]),
      needleOut: this.track([
        ["pull", -0.6, 0],
        ["pull", 0.0, 1],
      ]),
      needleX: this.track([
        ["pull", 0, W.pullStartX, "linear"],
        ["pull", 0.88, W.pullEndX],
        ["time", 0, W.timeStartX + lead, "linear"],
        ["time", 1, W.timeEndX + lead],
      ]),
      detach: this.track([
        ["refuse", -0.25, 0],
        ["refuse", 0.3, 1],
      ]),
      fray: this.track([
        ["refuse", 0.05, 0],
        ["refuse", 0.6, 1],
        ["run", 0.2, 1],
        ["end", -0.3, 0],
      ]),
      tension: this.track([
        ["pulse", -0.35, 0],
        ["pulse", 0.12, 1],
        ["pulse", 1, 1],
        ["run", -0.3, 0],
      ]),
      dim: this.track([
        ["hero", 0, 1],
        ["knot", 0, 0.9],
        ["knot", 0.35, 0.55],
        ["knot", 0.75, 0.8],
        ["knot", 1, 0.9],
        ["pull", -0.6, 0.5],
        ["pull", 0.1, 0.42],
        ["time", -0.5, 0.42],
        ["time", 0.2, 0.95],
        ["handover", 0.1, 0.8],
        ["refuse", 0, 0.3],
        ["pulse", 0, 0.55],
        ["run", 0, 0.4],
        ["end", -0.4, 0.4],
        ["end", 0.2, 1],
      ]),
      fragments: this.track([
        ["knot", -0.4, 0],
        ["knot", 0, 1],
        ["knot", 0.9, 1],
        ["pull", -0.6, 0],
      ]),
      tags: this.track([
        ["pull", -0.15, 0],
        ["pull", 0.02, 1],
        ["pull", 0.86, 1],
        ["pull", 0.94, 0.22],
        ["time", -0.5, 0],
      ]),
      timeline: this.track([
        ["time", -0.25, 0],
        ["time", 0.08, 1],
        ["handover", -0.15, 1],
        ["handover", 0.06, 0],
      ]),
      lanes: this.track([
        ["pulse", -0.2, 0],
        ["pulse", 0.1, 1],
        ["pulse", 1, 1],
        ["run", -0.6, 0],
      ]),
    };

    // Camera keys: [section, f, pos xyz, look xyz, ease]
    const b = W.ball;
    const pullCam = (x: number) => [x - 2.3, 0.55 * z, 7.2 * z, x - 2.3, W.lineY + 0.1, 0] as const;
    const timeCam = (x: number) => [x, 0.75, 9.6 * z, x, W.lineY + 0.05, 0] as const;
    const handoverX = W.xOfYear(2026.8);
    const endX = W.timeEndX + lead;
    type CamKey = [string, number, readonly number[], Ease?];
    const keys: CamKey[] = [
      ["hero", 0, W.portrait ? [0, 0.25, 12.4 * (z / 1.5), 0, 0.25, 0] : [0, 0, 9.5, 0, 0, 0]],
      ["knot", 0, W.portrait ? [b.x, b.y - 0.3, 8.6, b.x, b.y - 0.6, 0] : [b.x - 0.5, b.y + 0.05, 7.2, b.x - 1.7, b.y, 0]],
      ["knot", 0.55, W.portrait ? [b.x, b.y, 2.6, b.x, b.y, 0] : [b.x - 0.2, b.y + 0.15, 2.8, b.x - 0.6, b.y, 0]],
      ["knot", 1, [b.x + 0.1, b.y + 0.05, 0.45, b.x + 0.5, b.y - 0.1, -3]],
      ["pull", -0.5, [b.x + 0.9, b.y + 0.2, 4.2, b.x + 1.5, W.lineY, 0]],
      ["pull", 0, pullCam(W.pullStartX), "linear"],
      ["pull", 0.88, pullCam(W.pullEndX)],
      ["pull", 1, [W.pullEndX - 3.2, 0.9, 10.8 * z, W.pullEndX - 3.2, W.lineY, 0]],
      ["time", 0, timeCam(W.timeStartX), "linear"],
      ["time", 1, timeCam(W.timeEndX)],
      ["handover", 0, [handoverX - 0.4, 0.2, 8.4 * z, handoverX - 0.4, W.lineY, 0]],
      ["handover", 1, [handoverX + 0.4, 0.1, 8.0 * z, handoverX + 0.4, W.lineY, 0]],
      ["refuse", 0.1, W.portrait ? [endX - 0.3, 0.6, 4.4 * z, endX - 0.3, W.lineY + 0.5, 0] : [endX - 1.6, 0.15, 4.6 * z, endX - 1.1, W.lineY - 0.05, 0]],
      ["refuse", 1, W.portrait ? [endX - 0.2, 0.6, 4.2 * z, endX - 0.2, W.lineY + 0.5, 0] : [endX - 1.4, 0.25, 4.3 * z, endX - 1.0, W.lineY - 0.05, 0]],
      ["pulse", 0, [W.pulseX, 1.5, 9.8 * z, W.pulseX, W.lineY - 0.05, 0]],
      ["pulse", 1, [W.pulseX + 0.8, 1.3, 9.4 * z, W.pulseX + 0.8, W.lineY - 0.05, 0]],
      ["run", 0, [W.weaveCenter.x, 0.9, 9.4 * z, W.weaveCenter.x, W.lineY, -1]],
      ["end", 0, [W.weaveCenter.x, 0.4, 6.8 * z, W.weaveCenter.x, W.lineY - 0.5, -1.8]],
      ["end", 1, [W.weaveCenter.x + 0.3, 0.1, 6.2 * z, W.weaveCenter.x + 0.3, W.lineY - 0.6, -1.8]],
    ];
    this.camTracks = [0, 1, 2, 3, 4, 5].map(
      (i) => new Track(keys.map(([id, f, v, ease]) => ({ y: this.at(id, f), v: v[i], ease: ease ?? "smooth" }))),
    );
  }

  update(y: number) {
    const f = this.frame;
    const t = this.tracks;
    f.loosen = t.loosen.value(y);
    f.spin = t.spin.value(y);
    f.comb = t.comb.value(y);
    f.weave = t.weave.value(y);
    f.voice = t.voice.value(y);
    f.pull = t.pull.value(y);
    f.fray = t.fray.value(y);
    f.tension = t.tension.value(y);
    f.dim = t.dim.value(y);
    f.needleOut = t.needleOut.value(y);
    f.needleX = t.needleX.value(y);
    f.detach = t.detach.value(y);
    f.groups.fragments = t.fragments.value(y);
    f.groups.tags = t.tags.value(y);
    f.groups.timeline = t.timeline.value(y);
    f.groups.lanes = t.lanes.value(y);
    const c = this.camTracks.map((tr) => tr.value(y));
    f.cam.set(c[0], c[1], c[2]);
    f.look.set(c[3], c[4], c[5]);
    for (const s of this.sections) f.progress[s.id] = this.progressOf(s.id, y);
    return f;
  }

  /** Needle pose: pinned in the ball, or leading the red thread along the line. */
  needlePose(time: number, pos: Vector3, quat: Quaternion) {
    const W = this.world;
    const f = this.frame;
    const spin = f.spin;
    const dir = new Vector3(-0.55, 0.76, 0.34).normalize();
    dir.applyAxisAngle(new Vector3(0, 1, 0), spin);
    const inward = dir.clone().negate();
    pinnedHero.setFromUnitVectors(new Vector3(0, -1, 0), inward);
    const wobble = new Quaternion().setFromAxisAngle(new Vector3(0, 0, 1), Math.sin(time * 0.7) * 0.025);
    pinnedHero.premultiply(wobble);
    const pinnedPos = W.ball.clone().addScaledVector(dir, W.ballR * 1.08);

    // The needle dips at each label it passes, as if stitching it on.
    let dip = 0;
    for (const x of W.tagX) dip += Math.exp(-((f.needleX - x - 0.25) ** 2) / 0.12);
    const freePos = new Vector3(f.needleX + 0.68, W.lineY - 0.12 * dip + Math.sin(time * 1.3) * 0.02, 0);
    const freeQ = freeQuat.clone().multiply(new Quaternion().setFromAxisAngle(new Vector3(1, 0, 0), Math.sin(time * 0.9) * 0.15));
    freeQ.premultiply(new Quaternion().setFromAxisAngle(new Vector3(0, 0, 1), -0.35 * dip));

    const k = f.needleOut;
    pos.lerpVectors(pinnedPos, freePos, k);
    // Lift the needle up out of the ball before it swings level.
    pos.y += Math.sin(Math.PI * k) * 0.9;
    quat.slerpQuaternions(pinnedHero, freeQ, k);
  }
}
