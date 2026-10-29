import {
  ACESFilmicToneMapping,
  BackSide,
  DirectionalLight,
  Group,
  Mesh,
  MeshBasicMaterial,
  MeshStandardMaterial,
  PerspectiveCamera,
  PlaneGeometry,
  PMREMGenerator,
  Quaternion,
  Scene,
  ShaderMaterial,
  SphereGeometry,
  SRGBColorSpace,
  Vector3,
  WebGLRenderer,
} from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { createThreads, makeSharedUniforms, type ThreadSet, type Uniforms } from "./threads";

/** Where the thread leaves the needle, in the model's own units (see blender/needle.py). */
const EYE_LOCAL = new Vector3(0, 0.86, 0);
export const NEEDLE_SCALE = 0.82;

export interface StageOptions {
  strands: number;
  segments: number;
  maxPixelRatio: number;
}

export class Stage {
  readonly renderer: WebGLRenderer;
  readonly scene = new Scene();
  readonly camera = new PerspectiveCamera(35, 1, 0.05, 220);
  readonly shared: Uniforms = makeSharedUniforms();
  readonly threads: ThreadSet;
  readonly needle = new Group();
  readonly look = new Vector3();
  private maxPixelRatio: number;

  constructor(canvas: HTMLCanvasElement, opts: StageOptions) {
    this.maxPixelRatio = opts.maxPixelRatio;
    this.renderer = new WebGLRenderer({
      canvas,
      antialias: true,
      alpha: true,
      powerPreference: "high-performance",
    });
    this.renderer.setClearColor(0x000000, 0);
    this.renderer.outputColorSpace = SRGBColorSpace;
    this.renderer.toneMapping = ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.05;

    this.threads = createThreads(this.shared, opts.strands, opts.segments);
    this.scene.add(this.threads.cotton, this.threads.halo, this.threads.red);

    this.scene.environment = this.buildEnvironment();
    const key = new DirectionalLight(0xffffff, 1.4);
    key.position.set(3, 4, 5);
    this.scene.add(key);

    this.needle.visible = false;
    this.scene.add(this.needle);
    this.resize();
  }

  /** An indigo room with two soft boxes, so the steel reflects the page, not a grey studio. */
  private buildEnvironment() {
    const env = new Scene();
    const room = new Mesh(
      new SphereGeometry(10, 48, 24),
      new ShaderMaterial({
        side: BackSide,
        vertexShader: /* glsl */ `
          varying vec3 vDir;
          void main() {
            vDir = normalize(position);
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
          }`,
        fragmentShader: /* glsl */ `
          varying vec3 vDir;
          void main() {
            vec3 vat = vec3(0.02, 0.03, 0.1);
            vec3 dye = vec3(0.12, 0.17, 0.48);
            vec3 c = mix(vat, dye, smoothstep(-0.6, 0.9, vDir.y));
            gl_FragColor = vec4(c, 1.0);
          }`,
      }),
    );
    env.add(room);
    const box = (w: number, h: number, color: number, intensity: number) => {
      const m = new Mesh(new PlaneGeometry(w, h), new MeshBasicMaterial({ color }));
      (m.material as MeshBasicMaterial).color.multiplyScalar(intensity);
      return m;
    };
    const top = box(8, 2.4, 0xfff4e6, 3.2);
    top.position.set(0, 6, 2);
    top.lookAt(0, 0, 0);
    const side = box(2.2, 7, 0xbfc8ff, 1.6);
    side.position.set(-6.5, 0.5, 3);
    side.lookAt(0, 0, 0);
    const warm = box(1.4, 4, 0xff6b4a, 1.2);
    warm.position.set(6.5, -1, -2);
    warm.lookAt(0, 0, 0);
    env.add(top, side, warm);
    const pmrem = new PMREMGenerator(this.renderer);
    const tex = pmrem.fromScene(env, 0.03).texture;
    pmrem.dispose();
    return tex;
  }

  async loadNeedle(url: string) {
    const gltf = await new GLTFLoader().loadAsync(url);
    gltf.scene.traverse((o) => {
      const mesh = o as Mesh;
      if (!mesh.isMesh) return;
      const mat = mesh.material as MeshStandardMaterial;
      mat.envMapIntensity = 1.35;
    });
    gltf.scene.scale.setScalar(NEEDLE_SCALE);
    this.needle.add(gltf.scene);
    this.needle.visible = true;
  }

  /** World position of the needle's eye for a given pose. */
  eyeOf(pos: Vector3, quat: Quaternion, out: Vector3) {
    return out.copy(EYE_LOCAL).multiplyScalar(NEEDLE_SCALE).applyQuaternion(quat).add(pos);
  }

  resize() {
    const w = window.innerWidth;
    const h = window.innerHeight;
    const dpr = Math.min(window.devicePixelRatio || 1, this.maxPixelRatio);
    this.renderer.setPixelRatio(dpr);
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.shared.uResolution.value.set(w * dpr, h * dpr);
    this.shared.uPixelRatio.value = dpr;
  }

  render() {
    this.camera.lookAt(this.look);
    this.renderer.render(this.scene, this.camera);
  }

  /** Project a world point to CSS pixels. z > 1 means behind the camera or clipped. */
  project(p: Vector3, out: Vector3) {
    out.copy(p).project(this.camera);
    const behind = out.z > 1;
    out.x = (out.x * 0.5 + 0.5) * window.innerWidth;
    out.y = (-out.y * 0.5 + 0.5) * window.innerHeight;
    if (behind) out.z = 2;
    return out;
  }
}
