// Every thread on the page is a parametric curve evaluated on the GPU.
// A vertex knows only (t along the strand, which side of the ribbon, strand id)
// plus four random seeds; its position comes from blending three layouts:
//   ball  – a wound ball of yarn (the tangled repository)
//   comb  – parallel warp lanes (history laid out in time)
//   weave – a plain-weave cloth (knowledge put in order)
// The ribbon is extruded in screen space so line width stays crisp at any depth.

const noise = /* glsl */ `
vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 permute(vec4 x) { return mod289(((x * 34.0) + 1.0) * x); }
vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }
float snoise(vec3 v) {
  const vec2 C = vec2(1.0 / 6.0, 1.0 / 3.0);
  const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
  vec3 i = floor(v + dot(v, C.yyy));
  vec3 x0 = v - i + dot(i, C.xxx);
  vec3 g = step(x0.yzx, x0.xyz);
  vec3 l = 1.0 - g;
  vec3 i1 = min(g.xyz, l.zxy);
  vec3 i2 = max(g.xyz, l.zxy);
  vec3 x1 = x0 - i1 + C.xxx;
  vec3 x2 = x0 - i2 + C.yyy;
  vec3 x3 = x0 - D.yyy;
  i = mod289(i);
  vec4 p = permute(permute(permute(i.z + vec4(0.0, i1.z, i2.z, 1.0)) + i.y + vec4(0.0, i1.y, i2.y, 1.0)) + i.x + vec4(0.0, i1.x, i2.x, 1.0));
  float n_ = 0.142857142857;
  vec3 ns = n_ * D.wyz - D.xzx;
  vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
  vec4 x_ = floor(j * ns.z);
  vec4 y_ = floor(j - 7.0 * x_);
  vec4 x = x_ * ns.x + ns.yyyy;
  vec4 y = y_ * ns.x + ns.yyyy;
  vec4 h = 1.0 - abs(x) - abs(y);
  vec4 b0 = vec4(x.xy, y.xy);
  vec4 b1 = vec4(x.zw, y.zw);
  vec4 s0 = floor(b0) * 2.0 + 1.0;
  vec4 s1 = floor(b1) * 2.0 + 1.0;
  vec4 sh = -step(h, vec4(0.0));
  vec4 a0 = b0.xzyw + s0.xzyw * sh.xxyy;
  vec4 a1 = b1.xzyw + s1.xzyw * sh.zzww;
  vec3 p0 = vec3(a0.xy, h.x);
  vec3 p1 = vec3(a0.zw, h.y);
  vec3 p2 = vec3(a1.xy, h.z);
  vec3 p3 = vec3(a1.zw, h.w);
  vec4 norm = taylorInvSqrt(vec4(dot(p0, p0), dot(p1, p1), dot(p2, p2), dot(p3, p3)));
  p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
  vec4 m = max(0.6 - vec4(dot(x0, x0), dot(x1, x1), dot(x2, x2), dot(x3, x3)), 0.0);
  m = m * m;
  return 42.0 * dot(m * m, vec4(dot(p0, x0), dot(p1, x1), dot(p2, x2), dot(p3, x3)));
}
`;

const common = /* glsl */ `
uniform float uTime;
uniform vec2 uResolution;
uniform float uPixelRatio;
uniform float uWidth;
uniform float uAlpha;
uniform float uDraw;

uniform vec3 uBallCenter;
uniform float uBallRadius;
uniform float uLoosen;
uniform float uSpin;

uniform float uComb;
uniform vec3 uCombCenter;
uniform vec3 uCombSize;
uniform float uVoice;

uniform float uWeave;
uniform vec3 uWeaveCenter;
uniform float uWeaveGap;
uniform float uWeaveTilt;
uniform float uWeaveHalf;

uniform vec3 uMouse;
uniform float uMouseForce;

${noise}

vec3 rotateAround(vec3 v, vec3 axis, float a) {
  float c = cos(a);
  float s = sin(a);
  return v * c + cross(axis, v) * s + axis * dot(axis, v) * (1.0 - c);
}

// Smooth per-strand progress: strands leave in a staggered wave, and each
// strand starts moving from one end, so the motion reads as pulling.
float staged(float u, float seed, float t) {
  float k = clamp(u * 2.2 - seed * 0.8 - t * 0.4, 0.0, 1.0);
  return k * k * (3.0 - 2.0 * k);
}

vec3 ballPos(float t, vec4 s) {
  vec3 axis = normalize(s.xyz * 2.0 - 1.0 + vec3(1e-3, 2e-3, 3e-3));
  vec3 helper = abs(axis.y) < 0.9 ? vec3(0.0, 1.0, 0.0) : vec3(1.0, 0.0, 0.0);
  vec3 u = normalize(cross(axis, helper));
  vec3 v = cross(axis, u);
  float turns = 2.0 + s.w * 2.6;
  float th = t * turns * 6.28318 + s.x * 6.28318;
  vec3 d = cos(th) * u + sin(th) * v;
  vec3 axis2 = normalize(s.zwx * 2.0 - 1.0 + vec3(3e-3, 1e-3, 2e-3));
  d = rotateAround(d, axis2, t * (1.2 + s.y * 2.2));

  float r = uBallRadius * (0.74 + 0.26 * fract(s.w * 7.13 + s.z));
  vec3 p = d * r;
  float n = snoise(p * 1.4 + s.xyz * 9.0 + vec3(0.0, 0.0, uTime * 0.04));
  p += d * n * 0.1 * uBallRadius;

  // A few strands leave the ball as loose ends.
  float loose = smoothstep(0.9, 1.0, t) * step(0.86, s.y);
  p += (d * 0.8 + vec3(0.15, -0.6, 0.25)) * loose * uBallRadius * (0.3 + 0.45 * s.z);

  // Loosening opens the ball up from the inside.
  if (uLoosen > 0.001) {
    p *= 1.0 + uLoosen * (0.35 + 0.9 * s.z);
    p += uLoosen * uBallRadius * 0.35 * vec3(
      snoise(vec3(t * 2.0, s.x * 8.0, uTime * 0.05)),
      snoise(vec3(s.y * 8.0, t * 2.0, uTime * 0.05 + 3.0)),
      snoise(vec3(t * 2.0 + 5.0, s.z * 8.0, uTime * 0.05))
    );
  }

  float c = cos(uSpin);
  float sn = sin(uSpin);
  p.xz = mat2(c, -sn, sn, c) * p.xz;
  return uBallCenter + p;
}

vec3 combPos(float t, vec4 s, float id, float laneOverride) {
  float x = (t * 2.0 - 1.0) * uCombSize.x;
  float lane = laneOverride >= 0.0 ? laneOverride : fract(id * 0.6180339 + 0.13);
  float y = (lane - 0.5) * 2.0 * uCombSize.y;
  // Keep a clear channel around the red lane.
  y += sign(y) * 0.16;
  float z = (s.z - 0.5) * 2.0 * uCombSize.z;
  y += sin(x * 0.55 + s.x * 6.28 + uTime * 0.45) * 0.03;

  // While the handover call plays, lanes trace its waveform.
  float env = 0.5 + 0.5 * snoise(vec3(x * 0.25 - uTime * 0.9, lane * 3.0, 0.0));
  float talk = pow(env, 1.6) * exp(-abs(y) * 0.45);
  y += uVoice * talk * 0.55 * sin(x * 2.4 - uTime * 7.0 + lane * 19.0);
  return uCombCenter + vec3(x, y, z);
}

vec3 weavePos(float t, vec4 s, float id, float rowOverride) {
  float warp = mod(id, 2.0);
  float k = rowOverride >= 0.0 ? rowOverride : floor(id * 0.5);
  float off = (k - uWeaveHalf) * uWeaveGap;
  float run = (t * 2.0 - 1.0) * uWeaveHalf * uWeaveGap * 1.25;
  float amp = uWeaveGap * 0.32;
  vec3 p;
  if (warp < 0.5) {
    p = vec3(run, off, amp * cos(3.14159 * run / uWeaveGap + 3.14159 * k));
  } else {
    p = vec3(off, run, -amp * cos(3.14159 * run / uWeaveGap + 3.14159 * k));
  }
  // The cloth billows gently.
  p.z += 0.28 * sin(p.x * 0.42 + uTime * 0.5) * cos(p.y * 0.36 + uTime * 0.38);
  float c = cos(uWeaveTilt);
  float sn = sin(uWeaveTilt);
  p.yz = mat2(c, -sn, sn, c) * p.yz;
  return uWeaveCenter + p;
}

vec3 mouseDisplace(vec3 p) {
  vec2 d = p.xy - uMouse.xy;
  float f = exp(-dot(d, d) / 0.45) * uMouseForce;
  return p + vec3(normalize(d + 1e-4) * f * 0.38, 0.0);
}

// Screen-space ribbon extrusion. Ribbons thinner than two pixels are drawn at
// two pixels with lower alpha, so fine threads stay continuous instead of
// breaking into dashes.
vec4 extrude(vec3 p, vec3 prev, vec3 next, float side, float widthPx, out float viewDepth, out float coverage) {
  mat4 vp = projectionMatrix * viewMatrix;
  vec4 c = vp * vec4(p, 1.0);
  vec4 cp = vp * vec4(prev, 1.0);
  vec4 cn = vp * vec4(next, 1.0);
  float aspect = uResolution.x / uResolution.y;
  vec2 sp = cp.xy / max(cp.w, 1e-3);
  vec2 sn = cn.xy / max(cn.w, 1e-3);
  vec2 dir = sn - sp;
  dir.x *= aspect;
  dir = length(dir) < 1e-6 ? vec2(1.0, 0.0) : normalize(dir);
  vec2 nrm = vec2(-dir.y, dir.x);
  nrm.x /= aspect;
  viewDepth = c.w;
  // Nearer threads read thicker, like real fibres passing the lens.
  float persp = clamp(8.5 / max(c.w, 0.2), 0.6, 6.0);
  float w = widthPx * persp * uPixelRatio;
  float minW = 2.0 * uPixelRatio;
  coverage = clamp(w / minW, 0.0, 1.0);
  w = max(w, minW);
  c.xy += nrm * side * (w / uResolution.y) * c.w;
  return c;
}
`;

export const threadVertex = /* glsl */ `
${common}
attribute vec4 aSeed;

uniform vec3 uRiskIds;
uniform vec3 uPluck;
uniform float uTension;
uniform float uDim;
uniform vec3 uCotton;
uniform vec3 uFaded;

varying float vAlpha;
varying float vSide;
varying vec3 vColor;
varying float vCut;

vec3 strandPos(float t, vec4 s, float id, float pluck) {
  // Only evaluate the layouts a strand is actually between.
  float k1 = staged(uComb, s.y, t);
  float k2 = staged(uWeave, s.x, 1.0 - t);
  vec3 p = vec3(0.0);
  if (k1 < 1.0) p = ballPos(t, s);
  if (k1 > 0.0 && k2 < 1.0) {
    vec3 q = combPos(t, s, id, -1.0);
    q.y += pluck * sin(3.14159 * t) * sin(uTime * 38.0 + s.x * 3.0);
    p = mix(p, q, k1);
  }
  if (k2 > 0.0) p = mix(p, weavePos(t, s, id, -1.0), k2);
  return mouseDisplace(p);
}

void main() {
  float t = position.x;
  float side = position.y;
  float id = position.z;
  vec4 s = aSeed;

  float risk = 0.0;
  float pluck = 0.0;
  if (abs(id - uRiskIds.y) < 0.5) { risk = 1.0; pluck = uPluck.y; }
  if (abs(id - uRiskIds.z) < 0.5) { risk = 1.0; pluck = uPluck.z; }

  float e = 0.004;
  vec3 p = strandPos(t, s, id, pluck);
  vec3 pp = strandPos(max(t - e, 0.0), s, id, pluck);
  vec3 pn = strandPos(min(t + e, 1.0), s, id, pluck);

  float kw = staged(uWeave, s.x, 1.0 - t);
  float width = uWidth * (0.7 + 0.6 * s.w) * (1.0 + risk * uTension * 2.2) * (1.0 + kw * 1.3);
  float depth;
  float coverage;
  gl_Position = extrude(p, pp, pn, side, width, depth, coverage);

  // Back of the ball reads darker, which gives the yarn its volume.
  float k1 = staged(uComb, s.y, t);
  vec3 toCam = normalize(cameraPosition - uBallCenter);
  float facing = dot(normalize(p - uBallCenter), toCam);
  float shade = mix(mix(0.28, 1.0, smoothstep(-0.7, 0.75, facing)), 1.0, k1);

  float fog = (1.0 - smoothstep(6.0, 42.0, depth)) * smoothstep(0.05, 0.7, depth);
  float faded = step(0.68, s.x);
  vColor = mix(uCotton, uFaded, faded * 0.85);
  vColor = mix(vColor, uCotton * 1.15, risk * uTension);
  float dim = mix(uDim, 1.0, risk * uTension);
  vAlpha = uAlpha * coverage * shade * fog * dim * (0.55 + 0.45 * s.z) * (1.0 - faded * 0.35) * (1.0 + risk * uTension * 2.2);
  vSide = side;
  vCut = t - clamp(uDraw * 1.7 - s.y * 0.7, 0.0, 1.0);
}
`;

export const redVertex = /* glsl */ `
${common}
attribute vec4 aSeed;

uniform float uPull;
uniform vec3 uEye;
uniform vec3 uLineStart;
uniform float uFray;
uniform float uFrayLen;
uniform float uFibers;
uniform float uFiberR;
uniform float uHalo;
uniform float uPluckRed;
uniform float uRedLane;
uniform float uRedRow;
uniform vec3 uRed;

varying float vAlpha;
varying float vSide;
varying vec3 vColor;
varying float vCut;

const vec4 SEED = vec4(0.31, 0.62, 0.52, 0.66);

vec3 redCurve(float t) {
  // In the ball: wound for most of its length, then out to the needle eye.
  float wound = 0.8;
  vec3 exitP = ballPos(0.86, SEED);
  vec3 p;
  if (t < wound) {
    p = ballPos(t / wound * 0.86, SEED);
  } else {
    float k = (t - wound) / (1.0 - wound);
    // Surface just under the needle, so the thread leaves the ball where the needle went in.
    vec3 mid = uBallCenter + normalize(uEye - uBallCenter) * uBallRadius * 0.92;
    p = mix(mix(exitP, mid, k), mix(mid, uEye, k), k);
  }

  // Pulled: a straight line that ends at the needle eye, with a slight sag.
  float kp = clamp(uPull * 2.0 - (1.0 - t) * 1.0, 0.0, 1.0);
  kp = kp * kp * (3.0 - 2.0 * kp);
  if (kp > 0.0) {
    vec3 line = mix(uLineStart, uEye, t);
    line.y -= sin(3.14159 * t) * 0.12;
    p = mix(p, line, kp);
  }

  float k1 = clamp(uComb * 1.4 - 0.2, 0.0, 1.0);
  if (k1 > 0.0) {
    vec3 lane = combPos(t, SEED, 0.0, 0.5);
    lane.x = mix(uCombCenter.x - uCombSize.x, uEye.x, t);
    lane.y = uCombCenter.y + sin(lane.x * 0.55 + uTime * 0.45) * 0.03;
    lane.y += uPluckRed * sin(3.14159 * t) * sin(uTime * 34.0);
    lane.z = uCombCenter.z + 0.3;
    p = mix(p, lane, k1 * k1 * (3.0 - 2.0 * k1));
  }

  float k2 = clamp(uWeave * 1.6 - 0.5 - (1.0 - t) * 0.1, 0.0, 1.0);
  if (k2 > 0.0) p = mix(p, weavePos(t, SEED, 0.0, uRedRow) + vec3(0.0, 0.0, 0.012), k2 * k2 * (3.0 - 2.0 * k2));
  return p;
}

float hash(float n) { return fract(sin(n * 91.345) * 47453.5453); }

// The thread is a few plied fibres. They twist around the core and fray apart
// at the end when the record runs out.
vec3 redPos(float t, float fiber) {
  vec3 c = redCurve(t);
  if (uHalo > 0.5) return mouseDisplace(c);
  vec3 a = redCurve(min(t + 0.002, 1.0));
  vec3 b = redCurve(max(t - 0.002, 0.0));
  vec3 T = normalize(a - b + 1e-5);
  vec3 ref = abs(T.z) < 0.9 ? vec3(0.0, 0.0, 1.0) : vec3(0.0, 1.0, 0.0);
  vec3 N = normalize(cross(T, ref));
  vec3 B = cross(T, N);
  float ang = fiber * 6.28318 / uFibers + t * 140.0;
  float fray = uFray * pow(smoothstep(1.0 - uFrayLen, 1.0, t), 1.4);
  float r = uFiberR * (1.0 + fray * 36.0 * (0.5 + hash(fiber)));
  vec3 off = (cos(ang) * N + sin(ang) * B) * r;
  off += fray * 0.22 * vec3(
    snoise(vec3(fiber * 3.1, t * 5.0, uTime * 0.15)),
    snoise(vec3(t * 5.0, fiber * 2.3, uTime * 0.15 + 7.0)) - 0.35,
    snoise(vec3(fiber * 1.7, uTime * 0.15, t * 5.0))
  );
  return mouseDisplace(c + off);
}

void main() {
  float t = position.x;
  float side = position.y;
  float fiber = position.z;

  float e = 0.0025;
  vec3 p = redPos(t, fiber);
  vec3 pp = redPos(max(t - e, 0.0), fiber);
  vec3 pn = redPos(min(t + e, 1.0), fiber);

  // While wound in the ball the red thread is one strand among many: thinner,
  // and darker on the far side.
  float kp = clamp(uPull * 2.0 - (1.0 - t), 0.0, 1.0);
  float inBall = (1.0 - kp * kp * (3.0 - 2.0 * kp)) * (1.0 - smoothstep(0.74, 0.84, t));
  vec3 toCam = normalize(cameraPosition - uBallCenter);
  float facing = dot(normalize(p - uBallCenter), toCam);
  float shade = mix(1.0, 0.25 + 0.5 * smoothstep(-0.5, 0.8, facing), inBall);

  float depth;
  float coverage;
  float width = uWidth * (uHalo > 0.5 ? 1.0 : (0.8 + 0.4 * hash(fiber + 4.0))) * mix(1.0, 0.6, inBall);
  gl_Position = extrude(p, pp, pn, side, width, depth, coverage);

  float fog = (1.0 - smoothstep(6.0, 46.0, depth)) * smoothstep(0.05, 0.6, depth);
  float fray = uFray * smoothstep(1.0 - uFrayLen * 0.6, 1.0, t);
  vColor = uRed * (1.0 - 0.18 * hash(fiber + 1.0));
  vAlpha = uAlpha * coverage * fog * shade * (1.0 - fray * 0.55) * (uHalo > 0.5 ? 1.0 - inBall : 1.0);
  vSide = side;
  vCut = t - clamp(uDraw * 1.25 - 0.25, 0.0, 1.0);
}
`;

export const threadFragment = /* glsl */ `
varying float vAlpha;
varying float vSide;
varying vec3 vColor;
varying float vCut;

void main() {
  if (vCut > 0.0) discard;
  float edge = 1.0 - smoothstep(0.45, 1.0, abs(vSide));
  gl_FragColor = vec4(vColor, vAlpha * edge);
}
`;
