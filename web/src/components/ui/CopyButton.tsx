"use client";

import { AlertCircle, Check, Copy } from "lucide-react";
import { useState } from "react";

export function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const [status, setStatus] = useState<"idle" | "copied" | "failed">("idle");

  const copy = async () => {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        const textarea = document.createElement("textarea");
        textarea.value = text;
        textarea.setAttribute("readonly", "");
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        document.body.appendChild(textarea);
        textarea.select();
        const copied = document.execCommand("copy");
        textarea.remove();
        if (!copied) throw new Error("clipboard unavailable");
      }
      setStatus("copied");
      window.setTimeout(() => setStatus("idle"), 1400);
    } catch {
      setStatus("failed");
      window.setTimeout(() => setStatus("idle"), 1800);
    }
  };

  const message = status === "copied" ? "Copied" : status === "failed" ? "Copy failed" : label;
  return (
    <>
      <button type="button" className="btn btn-ghost btn-sm" aria-label={message} title={label} onClick={() => void copy()}>
        {status === "copied" ? <Check size={14} /> : status === "failed" ? <AlertCircle size={14} /> : <Copy size={14} />}
        <span className="sr-only sm:not-sr-only">{message}</span>
      </button>
      <span className="sr-only" aria-live="polite">
        {status === "copied" ? `${label} copied to clipboard.` : status === "failed" ? `${label} could not be copied.` : ""}
      </span>
    </>
  );
}
