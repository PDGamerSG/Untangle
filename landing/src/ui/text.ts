import { mulberry32 } from "../gl/threads";

/**
 * Split an element's text into per-letter spans so each letter can carry its
 * own width and weight. "Tangled" text has scattered widths; "settled" text
 * returns to the family's normal width.
 */
export function splitLetters(el: HTMLElement) {
  const text = el.textContent ?? "";
  el.textContent = "";
  const letters: HTMLSpanElement[] = [];
  // Keep words together so a line never breaks inside one.
  for (const [i, word] of text.split(" ").entries()) {
    if (i > 0) el.append(" ");
    const w = document.createElement("span");
    w.style.display = "inline-block";
    w.style.whiteSpace = "nowrap";
    for (const ch of word) {
      const s = document.createElement("span");
      s.className = "ch";
      s.textContent = ch;
      w.append(s);
      letters.push(s);
    }
    el.append(w);
  }
  return letters;
}

export function tangle(letters: HTMLElement[], seed: number, amount = 1, weights: [number, number] = [260, 900]) {
  const rand = mulberry32(seed);
  for (const s of letters) {
    const w = 100 + (rand() * 2 - 1) * 25 * amount;
    s.style.setProperty("--w", `${w.toFixed(1)}%`);
    s.style.setProperty("--wt", `${Math.round(weights[0] + rand() * (weights[1] - weights[0]))}`);
    s.style.setProperty("--dy", `${((rand() * 2 - 1) * 0.06 * amount).toFixed(3)}em`);
  }
}

export function settle(letters: HTMLElement[]) {
  for (const s of letters) {
    s.style.removeProperty("--w");
    s.style.removeProperty("--wt");
    s.style.removeProperty("--dy");
  }
}
