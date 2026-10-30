import Link from "next/link";
import { ExternalLink } from "lucide-react";
import { hrefFor } from "@/lib/api";
import { KIND_LABEL, normaliseKind, truncate } from "@/lib/format";
import type { Citation, CitationKind, EntityRef } from "@/lib/types";

/** "app.concurrency in config.toml.sample is 10 (set in …)" -> "app.concurrency = 10"; otherwise the title without its parenthetical. */
function decisionShort(title: string, max: number): string {
  const plain = title.replace(/`/g, "");
  const m = /^(\S+) in \S+ is (.+?)(?: \(|$)/.exec(plain);
  if (m) return truncate(`${m[1]} = ${m[2]}`, max);
  const removed = /^(\S+) was removed from (\S+)/.exec(plain);
  if (removed) return truncate(`${removed[1]} removed`, max);
  const kt = /^(?:\S+::)?(\S+) is (.+?) \(said by/.exec(plain);
  if (kt) return truncate(`call: ${kt[1]} = ${kt[2]}`, max);
  return truncate(plain.replace(/\s*\(.*$/, ""), max);
}

/** Short display id for a citation: "PR #812", "#790", "3f9c2a1", "ADR-0002"… */
export function shortId(id: string, kind: CitationKind, title?: string): string {
  const num = /#(\d+)$/.exec(id)?.[1];
  switch (kind) {
    case "pr":
      return num ? `PR #${num}` : "PR";
    case "issue":
      return num ? `#${num}` : "Issue";
    case "commit": {
      // commit:owner/name@3fa2c1d9e8b7 -> 3fa2c1d
      const sha = id.includes("@") ? id.slice(id.lastIndexOf("@") + 1) : (id.split(":").pop() ?? id);
      return sha.slice(0, 7);
    }
    case "document": {
      const adr = /adr[-/]?0*(\d+)/i.exec(id)?.[1];
      return adr ? `ADR-${adr.padStart(4, "0")}` : truncate(title ?? id.split(":").pop() ?? id, 22);
    }
    case "utterance": {
      // utt:mtg:owner/name:slug#0034 -> call #34
      const seq = /[#:](\d+)$/.exec(id)?.[1];
      return seq ? `call #${Number(seq)}` : "call";
    }
    case "person":
      return title ? truncate(title.replace(/\s*\(@.*$/, ""), 20) : id.split(":").pop() ?? id;
    case "decision":
      return title ? decisionShort(title, 26) : id;
    case "comment":
      return title ? truncate(title, 26) : "comment";
    case "meeting":
      return title ? truncate(title, 26) : "meeting";
    default:
      return truncate(title ?? id, 24);
  }
}

export function CitationChip({
  id,
  citation,
  inline = false,
  index,
}: {
  id: string;
  citation?: Citation;
  inline?: boolean;
  index?: number;
}) {
  const kind = normaliseKind(citation?.kind, id);
  const label = shortId(id, kind, citation?.title);
  const link = hrefFor(id, kind, citation?.url);
  const title = citation ? `${KIND_LABEL[kind]}: ${citation.title}${citation.excerpt ? `\n${citation.excerpt}` : ""}` : id;
  const cls = `chip ${inline ? "chip-inline" : ""}`;
  const body = (
    <>
      {!inline ? <span className="chip-kind">{KIND_LABEL[kind]}</span> : null}
      {index != null && inline ? <span className="t-num opacity-70">{index}</span> : null}
      <span className="truncate">{label}</span>
      {link?.external && !inline ? <ExternalLink size={11} aria-hidden /> : null}
    </>
  );
  if (!link)
    return (
      <span className={cls} data-kind={kind} title={title}>
        {body}
      </span>
    );
  if (link.external)
    return (
      <a className={cls} data-kind={kind} href={link.href} target="_blank" rel="noreferrer" title={title} aria-label={`${KIND_LABEL[kind]} ${label}, opens in a new tab`}>
        {body}
      </a>
    );
  return (
    <Link className={cls} data-kind={kind} href={link.href} title={title}>
      {body}
    </Link>
  );
}

/** An entity tag. It links to the entity's page unless it already sits inside a link. */
export function EntityChip({ entity, link = true }: { entity: EntityRef; link?: boolean }) {
  const kind =
    entity.label === "ConfigKey"
      ? "config"
      : entity.label === "File"
        ? "file"
        : entity.label === "Module"
          ? "module"
          : entity.label === "Dependency"
            ? "dependency"
            : entity.label === "Symbol"
              ? "symbol"
              : "entity";
  const body = (
    <>
      <span className="chip-kind">{entity.label}</span>
      <span className="truncate">{entity.name}</span>
      {/* the same key or symbol can live in several files: name the file so the chips can be told apart */}
      {(entity.label === "ConfigKey" || entity.label === "Symbol") && entity.path ? (
        <span className="truncate text-ink-3">· {entity.path.split("/").pop()}</span>
      ) : null}
    </>
  );
  const title = `${entity.label}: ${entity.name}${entity.path ? ` (${entity.path})` : ""}`;
  if (!link) {
    return (
      <span className="chip" data-kind={kind} title={title}>
        {body}
      </span>
    );
  }
  return (
    <Link href={`/entities/${encodeURIComponent(entity.id)}`} className="chip" data-kind={kind} title={`Open ${title}`}>
      {body}
    </Link>
  );
}

export function KindTag({ kind, children }: { kind: string; children: React.ReactNode }) {
  return (
    <span className="chip" data-kind={kind}>
      {children}
    </span>
  );
}
