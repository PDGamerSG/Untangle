import { Fragment } from "react";
import { CitationChip } from "@/components/Chip";
import type { Citation } from "@/lib/types";

/** Matches "[dec:…]" style citations: ids may contain ":", "/", "#", ".", "-", "_", "@". */
const CITE = /(\[[A-Za-z][A-Za-z0-9_:/#@.\-]*\])/g;
const CITE_ONE = /^\[([A-Za-z][A-Za-z0-9_:/#@.\-]*)\]$/;
/** `identifier` spans the answer uses for keys, files and values. */
const CODE = /(`[^`\n]+`)/g;

/** Plain text with `code` spans rendered as inline code. */
export function InlineCode({ text }: { text: string }) {
  return (
    <>
      {text.split(CODE).map((piece, i) =>
        piece.length > 2 && piece.startsWith("`") && piece.endsWith("`") ? (
          <code key={i} className="t-code rounded bg-surface-2 px-1 py-px text-[0.92em]">
            {piece.slice(1, -1)}
          </code>
        ) : (
          <Fragment key={i}>{piece}</Fragment>
        ),
      )}
    </>
  );
}

/** Renders the answer text, turning every [id] into a kind-coloured chip that opens the source. */
export function AnswerText({ text, citations, className = "" }: { text: string; citations: Record<string, Citation>; className?: string }) {
  const parts = text.split(CITE);
  const order: string[] = [];
  return (
    <p className={`whitespace-pre-line ${className}`}>
      {parts.map((part, i) => {
        const m = CITE_ONE.exec(part);
        if (!m) return <InlineCode key={i} text={part} />;
        const id = m[1];
        if (!order.includes(id)) order.push(id);
        return <CitationChip key={i} id={id} citation={citations[id]} inline index={order.indexOf(id) + 1} />;
      })}
    </p>
  );
}
