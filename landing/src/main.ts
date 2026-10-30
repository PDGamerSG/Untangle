import "@fontsource-variable/mona-sans/standard.css";
import "@fontsource-variable/martian-mono/wght.css";
import "./style.css";

import Lenis from "lenis";
import { Plane, Quaternion, Raycaster, Vector2, Vector3 } from "three";
import { Stage } from "./gl/stage";
import { laneOf } from "./gl/threads";
import { Director } from "./story";
import { Labels } from "./ui/labels";
import { startRoller } from "./ui/roller";
import { bindRisks, Headings, makeChrome, makeReadout, makeTranscript, makeTyper, renderContent } from "./ui/sections";
import { settle, splitLetters, tangle } from "./ui/text";

const $ = <T extends HTMLElement = HTMLElement>(sel: string) => document.querySelector<T>(sel)!;
const clamp01 = (v: number) => Math.min(1, Math.max(0, v));
const easeInOut = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const easeOutBack = (t: number) => 1 + 2.2 * Math.pow(t - 1, 3) + 1.2 * Math.pow(t - 1, 2);

const root = document.documentElement;
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
const finePointer = matchMedia("(pointer: fine)").matches;
root.classList.add("is-loading");

renderContent();
const heroLetters = splitLetters($(".hero__rest"));
tangle(heroLetters, 3, 1);
startRoller($(".roller"), reduced);
const headings = new Headings();
const typer = makeTyper(reduced);
const readout = makeReadout();
const transcript = makeTranscript();
const answer = $(".answer");

function webglAvailable() {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch {
    return false;
  }
}

const director = new Director(document);
const chrome = makeChrome(() => director.sections);
const small = matchMedia("(max-width: 900px)").matches;
const modest = small || (navigator.hardwareConcurrency ?? 8) <= 4;

let stage: Stage | null = null;
let labels: Labels | null = null;
if (webglAvailable()) {
  stage = new Stage($<HTMLCanvasElement>("#gl"), {
    strands: modest ? 210 : 380,
    segments: modest ? 170 : 240,
    maxPixelRatio: modest ? 1.5 : 2,
  });
  stage.loadNeedle(`${import.meta.env.BASE_URL}models/needle.glb`).catch(() => {
    // The page reads fine without the needle; the thread simply ends in the air.
  });
  labels = new Labels($("#labels"));
} else {
  root.classList.add("no-webgl");
}

// ---------- Risk lanes ----------
let laneIds: [number, number] = [-1, -1];
const laneYs: [number, number, number] = [0, 0, 0];
function pickLanes() {
  if (!stage) return;
  const W = director.world;
  const seeds = stage.threads.seeds;
  const targets = [0.95, -1.1];
  laneIds = targets.map((target) => {
    let best = -1;
    let score = Infinity;
    for (let id = 0; id < stage!.threads.strands; id++) {
      const y = laneOf(id, W.combSize.y);
      const z = (seeds[id * 4 + 2] - 0.5) * 2 * W.combSize.z;
      const s = Math.abs(y - target) + Math.abs(z) * 0.4 + (seeds[id * 4] >= 0.68 ? 1 : 0);
      if (s < score) {
        score = s;
        best = id;
      }
    }
    return best;
  }) as [number, number];
  laneYs[0] = W.combCenter.y;
  laneYs[1] = W.combCenter.y + laneOf(laneIds[0], W.combSize.y);
  laneYs[2] = W.combCenter.y + laneOf(laneIds[1], W.combSize.y);
}

const pluck = [0, 0, 0];
bindRisks((i) => {
  pluck[i] = i === 0 ? 0.13 : 0.1;
});

// ---------- Layout ----------
function measure() {
  director.measure();
  if (stage) {
    stage.resize();
    labels!.build(director.world);
    pickLanes();
  }
}
measure();
document.fonts?.ready.then(measure);
let resizeTimer = 0;
window.addEventListener("resize", () => {
  window.clearTimeout(resizeTimer);
  resizeTimer = window.setTimeout(measure, 120);
});

// ---------- Smooth scroll and anchors ----------
const lenis = reduced ? null : new Lenis({ lerp: 0.085, wheelMultiplier: 0.9 });
document.querySelectorAll<HTMLAnchorElement>('a[href^="#"]').forEach((a) => {
  a.addEventListener("click", (e) => {
    const id = a.getAttribute("href")!;
    const target = id === "#top" ? document.body : document.querySelector<HTMLElement>(id);
    if (!target) return;
    e.preventDefault();
    if (lenis) lenis.scrollTo(id === "#top" ? 0 : target, { duration: 2.4 });
    else window.scrollTo({ top: id === "#top" ? 0 : target.offsetTop });
    history.replaceState(null, "", id);
  });
});

// ---------- Pointer ----------
const pointer = new Vector2(0, 0);
let pointerForce = 0;
let lastMove = -10;
const smoothPointer = new Vector2();
window.addEventListener("pointermove", (e) => {
  pointer.set((e.clientX / window.innerWidth) * 2 - 1, -(e.clientY / window.innerHeight) * 2 + 1);
  lastMove = performance.now() / 1000;
});
const ray = new Raycaster();
const plane = new Plane(new Vector3(0, 0, 1), 0);
const hit = new Vector3();

// ---------- Loop ----------
const needlePos = new Vector3();
const needleQuat = new Quaternion();
const eye = new Vector3();
let time = 0;
let last = performance.now();
const introStart = performance.now();
let introDone = reduced;
let heroTangled = false;
let voicePulse = 0;
let lastLine = -1;

if (reduced) {
  root.classList.remove("is-loading");
  settle(heroLetters);
}

function step(now: number) {
  const dt = Math.min(0.05, (now - last) / 1000);
  last = now;
  if (!reduced) time += dt;
  lenis?.raf(now);
  const y = lenis ? lenis.animatedScroll : window.scrollY;
  const f = director.update(y);
  const W = director.world;
  chrome(y);

  // Intro: the ball winds itself, then the needle drops in.
  const since = (now - introStart) / 1000;
  const draw = reduced ? 1 : easeInOut(clamp01((since - 0.15) / 2.6));
  if (!introDone && since > 0.7) {
    introDone = true;
    root.classList.remove("is-loading");
    settle(heroLetters);
  }
  const heroOut = y > window.innerHeight * 0.4;
  if (introDone && heroOut !== heroTangled) {
    heroTangled = heroOut;
    if (heroOut) tangle(heroLetters, 5, 0.8);
    else settle(heroLetters);
  }

  headings.update((id) => {
    const p = f.progress[id] ?? -9;
    return p > -0.45 && p < 1.04;
  });
  typer((f.progress.pull ?? -9) > -0.15);
  answer.classList.toggle("is-shown", (f.progress.pull ?? 0) > 0.9 && (f.progress.pull ?? 0) < 1.25);

  // The camera moves linearly through History, so the date under the hairline follows progress.
  const year = 2018.45 + clamp01(f.progress.time ?? 0) * (2026.85 - 2018.45);
  if ((f.progress.time ?? -9) > -0.4 && (f.progress.handover ?? -9) < 0.6) readout(year);

  const lineNow = transcript(f.progress.handover ?? -1);
  if (lineNow !== lastLine) {
    lastLine = lineNow;
    if (lineNow >= 0) voicePulse = 1;
  }
  voicePulse *= Math.exp(-dt * 0.9);

  for (let i = 0; i < 3; i++) pluck[i] *= Math.exp(-dt * 2.4);

  if (stage && labels) {
    const u = stage.shared;
    const cotton = stage.threads.cotton.material.uniforms;
    const red = stage.threads.red.material.uniforms;

    // Pointer: threads part around it, and the camera leans a little.
    const moving = finePointer && now / 1000 - lastMove < 1.6;
    pointerForce += ((moving ? 1 : 0) - pointerForce) * Math.min(1, dt * 3);
    smoothPointer.lerp(pointer, Math.min(1, dt * 4));

    u.uTime.value = time;
    u.uDraw.value = draw;
    u.uBallCenter.value.copy(W.ball);
    u.uBallRadius.value = W.ballR;
    u.uLoosen.value = f.loosen;
    u.uSpin.value = f.spin + (reduced ? 0 : smoothPointer.x * 0.12);
    u.uComb.value = f.comb;
    u.uCombCenter.value.copy(W.combCenter);
    u.uCombSize.value.copy(W.combSize);
    u.uVoice.value = f.voice * (0.3 + 0.7 * voicePulse);
    u.uWeave.value = f.weave;
    u.uWeaveCenter.value.copy(W.weaveCenter);
    const half = Math.floor(stage.threads.strands / 4);
    u.uWeaveHalf.value = half;
    u.uWeaveGap.value = W.portrait ? 0.15 : 0.13;
    u.uWeaveTilt.value = -1.02;

    // Skip the ball while the camera is far down the thread and nothing is combing it in.
    stage.threads.cotton.visible = f.comb > 0.001 || Math.abs(f.look.x - W.ball.x) < 9;
    cotton.uDim.value = f.dim;
    cotton.uTension.value = f.tension;
    cotton.uRiskIds.value.set(-1, laneIds[0], laneIds[1]);
    cotton.uPluck.value.set(0, pluck[1], pluck[2]);
    red.uPull.value = f.pull;
    red.uFray.value = f.fray;
    red.uPluckRed.value = pluck[0];
    // Weave the red thread a few rows back so it clears the closing line of text.
    red.uRedRow.value = half + (W.portrait ? 6 : 8);
    red.uLineStart.value.set(W.ball.x, W.lineY, 0);

    // Camera.
    const cam = stage.camera;
    cam.position.copy(f.cam);
    if (!reduced) {
      cam.position.x += smoothPointer.x * 0.18;
      cam.position.y += smoothPointer.y * 0.12;
    }
    stage.look.copy(f.look);
    cam.lookAt(stage.look);
    cam.updateMatrixWorld();

    // Needle: drops in after the ball winds, then leads the thread.
    director.needlePose(time, needlePos, needleQuat);
    const drop = reduced ? 1 : clamp01((since - 1.9) / 0.8);
    needlePos.y += (1 - easeOutBack(drop)) * 3.2;
    stage.eyeOf(needlePos, needleQuat, eye);
    red.uEye.value.copy(eye);
    // Fray only the last stretch of the lane, whatever its length.
    red.uFrayLen.value = Math.min(0.2, 1.8 / Math.max(eye.x - (W.combCenter.x - W.combSize.x), 1));
    const fly = f.detach;
    stage.needle.position.copy(needlePos).add(new Vector3(fly * 5, fly * 3.2, fly * 1.5));
    stage.needle.quaternion.copy(needleQuat);
    stage.needle.scale.setScalar(1 - fly * 0.9);

    // Pointer onto the plane through the look target.
    ray.setFromCamera(smoothPointer, cam);
    plane.constant = -stage.look.z;
    if (ray.ray.intersectPlane(plane, hit)) u.uMouse.value.copy(hit);
    u.uMouseForce.value = reduced ? 0 : pointerForce * (0.55 + 0.45 * (1 - f.comb));

    labels.update(f, W, stage, laneYs, year, dt);
    stage.render();
    watchFrameRate(dt, since);
  }
}

// If frames stay slow, drop to one device pixel per CSS pixel. Fill rate is
// the cost that grows fastest on high-density screens.
let slowFrames = 0;
let downgraded = false;
let frameEma = 1 / 60;
function watchFrameRate(dt: number, since: number) {
  if (downgraded || !stage || since < 4 || document.hidden) return;
  frameEma += (dt - frameEma) * 0.05;
  slowFrames = frameEma > 1 / 38 ? slowFrames + 1 : 0;
  if (slowFrames > 90 && stage.renderer.getPixelRatio() > 1) {
    downgraded = true;
    stage.setMaxPixelRatio(1);
  }
}

function loop(now: number) {
  step(now);
  requestAnimationFrame(loop);
}
requestAnimationFrame(loop);

if (import.meta.env.DEV) {
  // Lets a test harness render a given moment even when the tab is in the background.
  Object.assign(window, { __untangle: { step, director, stage, lenis } });
}
