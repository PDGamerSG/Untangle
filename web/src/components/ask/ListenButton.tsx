"use client";

import { Pause, Volume2 } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { api, errorMessage } from "@/lib/api";
import { useResource } from "@/lib/hooks";

const STORE = "untangle.listen-language";

function storedLanguage(): string {
  if (typeof window === "undefined") return "hi-IN";
  try {
    return window.localStorage.getItem(STORE) ?? "hi-IN";
  } catch {
    return "hi-IN";
  }
}

/**
 * Reads a piece of text aloud in an Indian language: the server translates it and returns speech, which plays here and
 * is never stored. Hidden when the deployment has no speech service configured.
 */
export function ListenButton({ text }: { text: string }) {
  const langs = useResource("speak-languages", (signal) => api.speakLanguages(signal));
  // Nothing renders until the language list loads in the browser, so reading storage here cannot mismatch the server.
  const [language, setLanguage] = useState(storedLanguage);
  const [state, setState] = useState<"idle" | "loading" | "playing" | "paused">("idle");
  const [error, setError] = useState<string | null>(null);
  const [spoken, setSpoken] = useState<{ key: string; text: string; url: string } | null>(null);
  const audio = useRef<HTMLAudioElement | null>(null);
  const selectId = useId();

  useEffect(() => () => {
    audio.current?.pause();
  }, []);

  if (!langs.data?.available || !text.trim()) return null;
  const key = `${language}:${text}`;

  const play = async () => {
    setError(null);
    if (audio.current && spoken?.key === key) {
      if (state === "playing") {
        audio.current.pause();
        setState("paused");
      } else {
        await audio.current.play();
        setState("playing");
      }
      return;
    }
    audio.current?.pause();
    setState("loading");
    try {
      const res = await api.speak(text, language);
      const url = `data:${res.mime};base64,${res.audio_base64}`;
      const el = new Audio(url);
      el.onended = () => setState("idle");
      audio.current = el;
      setSpoken({ key, text: res.text, url });
      await el.play();
      setState("playing");
    } catch (e) {
      setState("idle");
      setError(errorMessage(e));
    }
  };

  const name = langs.data.languages.find((l) => l.code === language)?.name ?? language;
  return (
    <div className="flex flex-wrap items-center gap-1.5 text-[0.82rem]">
      <label htmlFor={selectId} className="sr-only">Language to listen in</label>
      <select
        id={selectId}
        value={language}
        onChange={(e) => {
          setLanguage(e.target.value);
          try {
            window.localStorage.setItem(STORE, e.target.value);
          } catch {
            /* the choice is a convenience; private windows may refuse storage */
          }
        }}
        className="field h-8 w-auto py-0 pr-7 text-[0.82rem]"
      >
        {langs.data.languages.map((l) => <option key={l.code} value={l.code}>{l.name}</option>)}
      </select>
      <button type="button" className="btn btn-line btn-sm" onClick={() => void play()} disabled={state === "loading"} aria-live="polite">
        {state === "playing" ? <Pause size={14} aria-hidden /> : <Volume2 size={14} aria-hidden />}
        {state === "loading" ? "Preparing…" : state === "playing" ? "Pause" : spoken?.key === key ? "Resume" : "Listen"}
      </button>
      {spoken?.key === key && language !== "en-IN" ? (
        <details className="basis-full">
          <summary className="cursor-pointer text-ink-3">Read it in {name.replace(/ \(.*\)$/, "")}</summary>
          <p className="mt-1 text-[0.92rem] leading-relaxed text-ink">{spoken.text}</p>
        </details>
      ) : null}
      {error ? <p role="status" className="basis-full text-[0.8rem] text-bad">{error}</p> : null}
    </div>
  );
}
