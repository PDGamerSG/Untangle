import { WHYS } from "../data";

/**
 * Rolls the first word of the headline through "why" in other languages.
 * The roller's width eases to each word so the rest of the line slides with it.
 */
export function startRoller(root: HTMLElement, reduced: boolean) {
  const first = root.querySelector<HTMLElement>(".roller__word")!;
  let index = 0;
  let current = first;

  const measure = (word: HTMLElement) => {
    const probe = word.cloneNode(true) as HTMLElement;
    probe.style.cssText = "position:absolute;visibility:hidden;white-space:nowrap;";
    root.append(probe);
    const w = probe.getBoundingClientRect().width;
    probe.remove();
    return w;
  };

  const make = (i: number) => {
    const w = document.createElement("span");
    w.className = "roller__word";
    w.textContent = WHYS[i].text;
    w.lang = WHYS[i].lang;
    return w;
  };

  const fit = () => {
    root.style.width = `${measure(current)}px`;
  };
  fit();
  window.addEventListener("resize", fit);
  document.fonts?.ready.then(fit);

  if (reduced) return;

  const step = () => {
    index = (index + 1) % WHYS.length;
    const next = make(index);
    const old = current;
    old.classList.add("is-leaving");
    root.append(next);
    root.style.width = `${measure(next)}px`;
    const opts: KeyframeAnimationOptions = { duration: 900, easing: "cubic-bezier(0.65, 0, 0.35, 1)", fill: "forwards" };
    old.animate([{ transform: "translateY(0)" }, { transform: "translateY(-105%)" }], opts).onfinish = () => old.remove();
    next.animate([{ transform: "translateY(105%)" }, { transform: "translateY(0)" }], opts);
    current = next;
  };

  let timer = 0;
  const schedule = () => {
    // English "Why" holds a little longer so the sentence can be read first.
    timer = window.setTimeout(() => {
      if (!document.hidden) step();
      schedule();
    }, index === 0 ? 3400 : 2100);
  };
  schedule();
  return () => window.clearTimeout(timer);
}
