# Untangle landing — design notes

## Concept: the red thread

A codebase's history is a ball of tangled cotton threads. One red thread runs
through it: the answer to a question. The page follows that thread from start
to end.

| Scroll beat | What the threads do | What the page says |
|---|---|---|
| Hero | A ball of yarn, a needle pinned in it, red thread trailing out | Why is the code like this? (the word "why" rolls through languages) |
| Knot | Camera enters the ball, fragments of tribal knowledge float past | The reasons are scattered across commits, reviews, tickets, calls |
| Pull | The needle pulls the red thread out; evidence tags hang from it | One question, followed end to end through real listmonk evidence |
| Time | Cotton threads comb into warp lanes; the red lane carries value changes | Nothing is deleted. A date scrubber shows what was true when |
| Handover | Lanes vibrate like an oscilloscope of the call | Hinglish handover lines linked to the code they mention |
| Refusal | The red thread frays at its end | When the graph does not know, it says so |
| Pulse | Three lanes go taut; hover plucks them | Ranked knowledge risks |
| Run it | Lanes start weaving | Three steps, terminal commands |
| Finale | A woven cloth, the red thread woven in | Untangle wordmark, GitHub |

## Tokens

| Name | Hex | Role |
|---|---|---|
| Vat | `#0B1230` | Deepest background |
| Dye | `#1A2868` | Indigo mid-tone, gradients, panels |
| Faded | `#7C8AD0` | Secondary text, rules, faded threads |
| Cotton | `#F2EBDC` | Primary text, cotton threads, labels |
| Madder | `#FF4B3A` | The red thread only: the answer, the path, the primary action |

Type: Mona Sans (variable width and weight) for everything; its width axis is
animated so the hero headline starts tangled (random widths) and settles.
Anek Devanagari (also variable width) for Hindi. Martian Mono only for real code
tokens: commit hashes, config keys, shell commands.

## Rules we hold ourselves to

- Red means "the thread you followed". Never decorative.
- Evidence is shown as woven garment labels tied to the thread, not cards.
- Numbers appear only for the three-step setup, because that is a sequence.
- One orchestrated load moment (the ball winds itself). Other motion answers scroll or pointer.
- Reduced motion: no smooth scroll, threads hold still, every section stays readable.
- No WebGL: the page still reads top to bottom on an indigo gradient.

## Model

`blender/needle.py` builds the sewing needle in Blender (headless) and exports
`public/models/needle.glb`. Run it with:

```bash
blender -b -P blender/needle.py
```
