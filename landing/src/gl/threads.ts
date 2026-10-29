import {
  AdditiveBlending,
  BufferAttribute,
  BufferGeometry,
  DoubleSide,
  Mesh,
  NormalBlending,
  ShaderMaterial,
  Sphere,
  Vector2,
  Vector3,
} from "three";
import { redVertex, threadFragment, threadVertex } from "./shaders";

/** Seeded PRNG so the yarn ball is the same on every visit. */
export function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** sRGB hex to a vec3 the shaders use as-is (they write straight to the canvas). */
export function hexToVec3(hex: string) {
  const n = parseInt(hex.slice(1), 16);
  return new Vector3(((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255);
}

export const COLORS = {
  cotton: "#F2EBDC",
  faded: "#7C8AD0",
  red: "#FF4B3A",
};

/**
 * One ribbon per strand: (segments + 1) pairs of vertices.
 * position = (t, side, id) and aSeed = four random numbers per strand.
 */
function ribbon(strands: number, segments: number, seeds: Float32Array) {
  const perStrand = (segments + 1) * 2;
  const position = new Float32Array(strands * perStrand * 3);
  const seed = new Float32Array(strands * perStrand * 4);
  const index = new Uint32Array(strands * segments * 6);
  let v = 0;
  let i = 0;
  for (let s = 0; s < strands; s++) {
    const base = s * perStrand;
    for (let k = 0; k <= segments; k++) {
      const t = k / segments;
      for (const side of [-1, 1]) {
        position.set([t, side, s], v * 3);
        seed.set(seeds.subarray(s * 4, s * 4 + 4), v * 4);
        v++;
      }
      if (k < segments) {
        const a = base + k * 2;
        index.set([a, a + 1, a + 2, a + 1, a + 3, a + 2], i);
        i += 6;
      }
    }
  }
  const geo = new BufferGeometry();
  geo.setAttribute("position", new BufferAttribute(position, 3));
  geo.setAttribute("aSeed", new BufferAttribute(seed, 4));
  geo.setIndex(new BufferAttribute(index, 1));
  // Positions are computed on the GPU, so give three.js a generous bound.
  geo.boundingSphere = new Sphere(new Vector3(30, 0, 0), 200);
  return geo;
}

export type Uniforms = ReturnType<typeof makeSharedUniforms>;

export function makeSharedUniforms() {
  return {
    uTime: { value: 0 },
    uResolution: { value: new Vector2(1, 1) },
    uPixelRatio: { value: 1 },
    uDraw: { value: 0 },
    uBallCenter: { value: new Vector3() },
    uBallRadius: { value: 1.5 },
    uLoosen: { value: 0 },
    uSpin: { value: 0 },
    uComb: { value: 0 },
    uCombCenter: { value: new Vector3() },
    uCombSize: { value: new Vector3(24, 2.6, 1.6) },
    uVoice: { value: 0 },
    uWeave: { value: 0 },
    uWeaveCenter: { value: new Vector3() },
    uWeaveGap: { value: 0.12 },
    uWeaveTilt: { value: -0.9 },
    uWeaveHalf: { value: 80 },
    uMouse: { value: new Vector3(999, 999, 0) },
    uMouseForce: { value: 0 },
  };
}

export interface ThreadSet {
  cotton: Mesh<BufferGeometry, ShaderMaterial>;
  red: Mesh<BufferGeometry, ShaderMaterial>;
  halo: Mesh<BufferGeometry, ShaderMaterial>;
  seeds: Float32Array;
  strands: number;
}

export function createThreads(shared: Uniforms, strands: number, segments: number): ThreadSet {
  const rand = mulberry32(20200708);
  const seeds = new Float32Array(strands * 4);
  for (let k = 0; k < seeds.length; k++) seeds[k] = rand();

  const cottonMat = new ShaderMaterial({
    vertexShader: threadVertex,
    fragmentShader: threadFragment,
    transparent: true,
    depthWrite: false,
    side: DoubleSide,
    blending: AdditiveBlending,
    uniforms: {
      ...shared,
      uWidth: { value: 1.1 },
      uAlpha: { value: 0.26 },
      uDim: { value: 1 },
      uTension: { value: 0 },
      uRiskIds: { value: new Vector3(-1, -1, -1) },
      uPluck: { value: new Vector3() },
      uCotton: { value: hexToVec3(COLORS.cotton) },
      uFaded: { value: hexToVec3(COLORS.faded) },
    },
  });
  const cotton = new Mesh(ribbon(strands, segments, seeds), cottonMat);
  cotton.frustumCulled = false;

  const fibers = 5;
  const redSeeds = new Float32Array(fibers * 4).fill(0.5);
  const redGeo = ribbon(fibers, 420, redSeeds);
  const redUniforms = {
    uPull: { value: 0 },
    uEye: { value: new Vector3() },
    uLineStart: { value: new Vector3() },
    uFray: { value: 0 },
    uFrayLen: { value: 0.04 },
    uFibers: { value: fibers },
    uFiberR: { value: 0.006 },
    uPluckRed: { value: 0 },
    uRedRow: { value: 80 },
    uRed: { value: hexToVec3(COLORS.red) },
  };
  const redMat = new ShaderMaterial({
    vertexShader: redVertex,
    fragmentShader: threadFragment,
    transparent: true,
    depthWrite: false,
    side: DoubleSide,
    blending: NormalBlending,
    uniforms: { ...shared, ...redUniforms, uWidth: { value: 1.7 }, uAlpha: { value: 1 }, uHalo: { value: 0 } },
  });
  const red = new Mesh(redGeo, redMat);
  red.frustumCulled = false;
  // Drawn before the cotton so the additive cotton sits over it inside the ball.
  red.renderOrder = -1;

  // A soft wide pass under the core makes the red thread glow without post-processing.
  const haloMat = new ShaderMaterial({
    vertexShader: redVertex,
    fragmentShader: threadFragment,
    transparent: true,
    depthWrite: false,
    side: DoubleSide,
    blending: AdditiveBlending,
    uniforms: { ...shared, ...redUniforms, uWidth: { value: 14 }, uAlpha: { value: 0.16 }, uHalo: { value: 1 } },
  });
  // Only the first fibre's ribbon is needed for the halo.
  const haloGeo = redGeo.clone();
  haloGeo.setDrawRange(0, 420 * 6);
  const halo = new Mesh(haloGeo, haloMat);
  halo.frustumCulled = false;
  halo.renderOrder = -2;

  return { cotton, red, halo, seeds, strands };
}

/** Lane height (before the clear channel) that the comb layout gives a strand. */
export function laneOf(id: number, halfHeight: number) {
  const lane = (((id * 0.6180339 + 0.13) % 1) + 1) % 1;
  const y = (lane - 0.5) * 2 * halfHeight;
  return y + Math.sign(y) * 0.16;
}
