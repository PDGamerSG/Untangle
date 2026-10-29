import { COMMANDS, CONFIDENCE, HISTORY, QUESTION, REFUSAL, RISKS, TRANSCRIPT } from "../data";
import { splitLetters, settle, tangle } from "./text";

const $ = <T extends HTMLElement = HTMLElement>(sel: string, root: ParentNode = document) =>
  root.querySelector<T>(sel)!;

function esc(s: string) {
  return s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);
}

/** Fill the static parts of each chapter from the sample data. */
export function renderContent() {
  $(".answer__reasons").innerHTML = CONFIDENCE.reasons.map((r) => `<li>${esc(r)}</li>`).join("");

  $(".transcript").innerHTML = TRANSCRIPT.map((line) => {
    let text = esc(line.text);
    for (const m of line.links) {
      const cls = m === "app.concurrency" ? "mention mention--red" : "mention";
      text = text.replace(esc(m), `<span class="${cls}">${esc(m)}</span>`);
    }
    return `<li class="line">
      <span class="line__meta"><span>${line.at}</span><span>${esc(line.speaker)}</span></span>
      <span class="line__text" lang="hi">${text}</span>
      <span class="line__en">${esc(line.en)}</span>
    </li>`;
  }).join("");

  $(".closest__list").innerHTML = REFUSAL.closest
    .map((c) => `<span class="closest__item"><code>${esc(c.name)}</code><small>${esc(c.kind)}</small></span>`)
    .join("");

  $(".risks").innerHTML =
    RISKS.map(
      (r, i) => `<li><button class="risk${i === 0 ? " risk--critical" : ""}" type="button" data-risk="${i}">
        <span class="risk__score">${r.score.toFixed(2)}</span>
        <span class="risk__category">${esc(r.category)}</span>
        <code class="risk__entity">${esc(r.entity)}</code>
        <span class="risk__reason">${esc(r.reason)}</span>
      </button></li>`,
    ).join("") + `<li class="pulse__hint">Hover or tap a risk to pluck its thread.</li>`;

  $(".terminal__body code").innerHTML = COMMANDS.map((c) => `<span class="p">$ </span>${esc(c)}`).join("\n");
  const copy = $<HTMLButtonElement>(".terminal__copy");
  copy.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(COMMANDS.join("\n"));
      copy.textContent = "Copied";
    } catch {
      copy.textContent = "Select the text to copy";
    }
    window.setTimeout(() => (copy.textContent = "Copy commands"), 2200);
  });
}

/** Headings tangle while their chapter is off stage and settle when it arrives. */
export class Headings {
  private items: { section: HTMLElement; letters: HTMLElement[]; seed: number; active: boolean | null }[] = [];

  constructor() {
    document.querySelectorAll<HTMLElement>(".chapter .h2").forEach((h, i) => {
      const section = h.closest<HTMLElement>("[data-section]")!;
      const letters = splitLetters(h);
      this.items.push({ section, letters, seed: 31 + i * 17, active: null });
    });
    const mark = $(".wordmark");
    const letters = splitLetters(mark);
    this.items.push({ section: $("#end"), letters, seed: 7, active: null });
  }

  update(active: (id: string) => boolean) {
    for (const it of this.items) {
      const on = active(it.section.dataset.section!);
      if (on === it.active) continue;
      it.active = on;
      it.section.classList.toggle("is-active", on);
      if (on) settle(it.letters);
      else tangle(it.letters, it.seed, 1, [300, 860]);
    }
  }
}

/** Types the question into the query bar once, when the chapter arrives. */
export function makeTyper(reduced: boolean) {
  const target = $(".chapter--pull .query__text");
  let started = false;
  return (active: boolean) => {
    if (!active || started) return;
    started = true;
    if (reduced) {
      target.textContent = QUESTION;
      return;
    }
    let i = 0;
    const tick = () => {
      i += 1;
      target.textContent = QUESTION.slice(0, i);
      if (i < QUESTION.length) window.setTimeout(tick, 26 + Math.random() * 40);
    };
    tick();
  };
}

const dateFmt = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });

/** "On 14 Mar 2019, app.concurrency was 100." */
export function makeReadout() {
  const date = $(".readout__date");
  const num = $(".readout__num");
  const where = $(".readout__where");
  let last = "";
  const changes = HISTORY.map((h) => ({ ...h, t: Date.parse(`${h.date}T00:00:00Z`) }));

  return (year: number) => {
    const y = Math.max(2018, Math.min(2026.99, year));
    const whole = Math.floor(y);
    const ms = Date.UTC(whole, 0, 1) + (y - whole) * (Date.UTC(whole + 1, 0, 1) - Date.UTC(whole, 0, 1));
    date.textContent = `On ${dateFmt.format(ms)}`;
    let value = "not set";
    let place = "No decision recorded yet.";
    let current = -1;
    changes.forEach((c, i) => {
      if (c.t <= ms) current = i;
    });
    if (current >= 0) {
      const c = changes[current];
      value = c.value;
      const next = changes.slice(current + 1).find((n) => n.value !== c.value || n.where !== c.where);
      place = next
        ? `in ${c.where}, until ${dateFmt.format(next.t)}`
        : c.call
          ? `in ${c.where}, and a handover call says why`
          : `in ${c.where}, the current decision`;
    }
    where.textContent = place;
    if (value !== last) {
      last = value;
      num.classList.add("is-changing");
      window.setTimeout(() => {
        num.textContent = value;
        num.classList.remove("is-changing");
      }, 180);
    }
  };
}

/** Lights transcript lines as the call plays through the chapter. */
export function makeTranscript() {
  const lines = [...document.querySelectorAll<HTMLElement>(".transcript .line")];
  let lastNow = -2;
  return (p: number) => {
    const n = lines.length;
    const now = Math.min(n - 1, Math.floor(((p - 0.04) / 0.86) * n));
    if (now === lastNow) return now;
    lastNow = now;
    lines.forEach((l, i) => {
      l.classList.toggle("is-heard", i < now);
      l.classList.toggle("is-now", i === now);
      l.classList.toggle("is-next", i === now + 1);
    });
    return now;
  };
}

export function bindRisks(onPluck: (i: number) => void) {
  document.querySelectorAll<HTMLButtonElement>(".risk").forEach((b) => {
    const i = Number(b.dataset.risk);
    b.addEventListener("pointerenter", () => onPluck(i));
    b.addEventListener("focus", () => onPluck(i));
    b.addEventListener("click", () => onPluck(i));
  });
}

/** Progress rail and nav state. */
export function makeChrome(sections: () => { id: string; top: number }[]) {
  const nav = $(".nav");
  const rail = $(".rail");
  const knots = [...document.querySelectorAll<HTMLAnchorElement>("[data-rail]")];
  const links = [...document.querySelectorAll<HTMLAnchorElement>(".nav__links a")];
  let lastY = 0;
  return (y: number) => {
    const max = document.documentElement.scrollHeight - window.innerHeight;
    rail.style.setProperty("--progress", (y / Math.max(max, 1)).toFixed(4));
    const secs = sections();
    let current = secs[0]?.id;
    for (const s of secs) if (y >= s.top - window.innerHeight * 0.5) current = s.id;
    for (const k of knots) {
      const s = secs.find((x) => x.id === k.dataset.rail);
      k.classList.toggle("is-past", !!s && y >= s.top - window.innerHeight * 0.5);
      k.toggleAttribute("aria-current", k.dataset.rail === current);
    }
    for (const l of links) l.setAttribute("aria-current", String(l.getAttribute("href") === `#${current}`));
    const down = y > lastY + 2;
    const up = y < lastY - 2;
    if (y < window.innerHeight * 0.5) nav.classList.remove("is-hidden");
    else if (down) nav.classList.add("is-hidden");
    else if (up) nav.classList.remove("is-hidden");
    nav.classList.toggle("is-solid", y > window.innerHeight * 0.6);
    lastY = y;
  };
}
