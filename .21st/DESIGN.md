# Untangle design context

Untangle connects engineering decisions to their source, code, people and date. Preserve the existing blue-and-white sidebar and light palette.

- Tokens: `web/src/app/globals.css` (accent `#1f55e0`, ink `#0c1d3b`, background `#f4f7fc`, surface `#ffffff`).
- Type: system sans-serif for controls and evidence; Fraunces/Georgia for values and page headings; monospace for code.
- Reuse `CitationChip`, `EntityChip`, `StatusMark`, and the existing loading/error/empty states.
- Timeline uses a searchable decision list beside an evidence inspector on wide screens, stacked on mobile.
- Pulse filters the returned priority queue. Counts describe loaded results, never a claim of complete coverage.
- Exports preserve dates, current status, missing reasons, source IDs and links. No extra model generation.
- Keyboard controls, focus outlines, wrapping long identifiers, and result limits are part of the design.

The 21st catalog was unavailable (HTTP 401); these choices use inspected project components, with no imported catalog code.
