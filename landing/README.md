# Untangle landing page

A scroll-driven landing page for Untangle. It is a static site: it never calls
the Untangle API or Neo4j, and every answer, transcript line and risk it shows
comes from the checked-in `knadh/listmonk` sample fixtures in `web/sample/`.

The page follows one red thread out of a tangled ball of yarn: a question is
pulled out of the repository's history, evidence labels are sewn onto it, the
threads comb into a timeline, a handover call makes them vibrate, the thread
frays where the record runs out, and everything ends as woven cloth. The design
notes are in [DESIGN.md](DESIGN.md).

## Run locally

```bash
cd landing
pnpm install
pnpm dev            # http://localhost:5180
```

```bash
pnpm build          # type-checks, then writes dist/
pnpm preview        # serves dist/
```

`dist/` is plain static files and can be hosted anywhere (Vercel, Netlify,
GitHub Pages, S3).

## How it is built

| Path | Contents |
|---|---|
| `src/gl/shaders.ts` | Every thread is a parametric curve evaluated on the GPU and blended between three layouts: ball, comb (timeline lanes) and weave. Ribbons are extruded in screen space. |
| `src/gl/threads.ts` | Ribbon geometry, the cotton strands, and the five-fibre red thread with its glow pass. |
| `src/gl/stage.ts` | Renderer, camera, an indigo environment map for the needle, and the GLB loader. |
| `src/story.ts` | Scroll tracks: each value (camera, loosen, comb, pull, fray…) is keyed to a point in a chapter. |
| `src/ui/` | DOM that rides on the 3D scene (evidence labels, timeline knots, floating fragments) and the chapter UI. |
| `src/data.ts` | All page content, taken from the sample fixtures. |
| `blender/needle.py` | Builds the sewing needle in Blender and exports `public/models/needle.glb`. |

Chapters are tall sections with a `position: sticky` stage, so the page scrolls
natively. Lenis smooths the scroll; with `prefers-reduced-motion` it is off, the
threads hold still and the intro is skipped. Without WebGL the page still reads
top to bottom, and the evidence chain is shown as a list.

## Rebuild the needle model

Requires Blender 4.2 or newer.

```bash
cd landing
pnpm model          # blender -b -P blender/needle.py
```

Add `-- --preview out.png` to the Blender command to render a look-dev image.
