"use client";

import { Download } from "lucide-react";

export function ExportBrief({ label, filename, build, disabled = false }: {
  label: string;
  filename: string;
  build: (origin: string) => string;
  disabled?: boolean;
}) {
  function download() {
    const url = URL.createObjectURL(new Blob([build(window.location.origin)], { type: "text/markdown;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <button type="button" className="btn btn-line btn-sm" onClick={download} disabled={disabled} title="Download a Markdown brief with source links"><Download size={14} aria-hidden />{label}</button>;
}
