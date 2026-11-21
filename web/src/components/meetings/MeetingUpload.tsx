"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Upload } from "lucide-react";
import { api, errorMessage, SAMPLE_MODE, type IngestResult } from "@/lib/api";

// A recording that is still transcribing survives a reload or a visit to another page: the upload id is kept here
// and collected again when this form mounts. Storage can be unavailable (private windows), so every access is guarded.
const PENDING_KEY = "untangle.pendingHandover";
type Pending = { id: string; repo: string; title: string; startedAt?: number };

function readPending(): Pending | null {
  try {
    const value = JSON.parse(localStorage.getItem(PENDING_KEY) ?? "null");
    return value && typeof value.id === "string" && typeof value.repo === "string" ? value : null;
  } catch { return null; }
}
function writePending(value: Pending | null) {
  try {
    if (value) localStorage.setItem(PENDING_KEY, JSON.stringify(value));
    else localStorage.removeItem(PENDING_KEY);
  } catch { /* storage unavailable: the upload still finishes while this page stays open */ }
}

const clock = (ms: number) => {
  const seconds = Math.max(0, Math.floor(ms / 1000));
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
};

export function MeetingUpload({ repo, onUploaded }: { repo: string | null; onUploaded: () => void }) {
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState<"sending" | "transcribing">("sending");
  const [startedAt, setStartedAt] = useState(0);
  const [now, setNow] = useState(0);
  const [error, setError] = useState("");
  const [meeting, setMeeting] = useState<string | null>(null);
  const controller = useRef<AbortController | null>(null);
  const uploaded = useRef(onUploaded);
  useEffect(() => { uploaded.current = onUploaded; }, [onUploaded]);

  useEffect(() => {
    if (!busy) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [busy]);

  useEffect(() => () => controller.current?.abort(), []);

  async function track(work: (signal: AbortSignal) => Promise<IngestResult>, resumedFrom?: number) {
    controller.current?.abort();
    const current = new AbortController();
    controller.current = current;
    setError(""); setMeeting(null); setBusy(true); setStage(resumedFrom ? "transcribing" : "sending");
    setStartedAt(resumedFrom ?? Date.now()); setNow(Date.now());
    try {
      const result = await work(current.signal);
      writePending(null);
      setMeeting(result.meeting_id); uploaded.current();
      return true;
    } catch (err) {
      if (current.signal.aborted) return false;
      writePending(null);
      setError(errorMessage(err));
      return false;
    } finally {
      if (!current.signal.aborted) setBusy(false);
    }
  }

  // Pick up a recording that was still transcribing when this page was last left.
  useEffect(() => {
    if (SAMPLE_MODE) return;
    const pending = readPending();
    if (!pending) return;
    const start = setTimeout(() => void track((signal) => api.resumeMeeting(pending.id, signal), pending.startedAt ?? Date.now()), 0);
    return () => clearTimeout(start);
  }, []);

  if (SAMPLE_MODE) return null;

  const elapsed = clock(now - startedAt);
  const status = stage === "sending"
    ? `Uploading and transcribing… ${elapsed}`
    : `Still transcribing… ${elapsed}. You can leave this page; it continues when you come back.`;

  return (
    <form className="card space-y-4 p-4 sm:p-5" onSubmit={async (event) => {
      event.preventDefault();
      if (!repo || busy) return;
      const form = event.currentTarget;
      const values = new FormData(form);
      const file = values.get("file");
      setError(""); setMeeting(null);
      if (!(file instanceof File) || !file.size) { setError("Choose a recording or transcript first."); return; }
      if (!values.get("consent")) { setError("Confirm that everyone in the conversation agreed to share it."); return; }
      if (file.size > 4_000_000) { setError("Choose a file smaller than 4 MB, or upload a transcript of the recording."); return; }
      const title = String(values.get("title") || file.name);
      const body = new FormData();
      body.set("repo", repo);
      body.set("title", title);
      body.set(/\.(json|txt)$/i.test(file.name) ? "transcript" : "audio", file);
      const startedAt = Date.now();
      const saved = await track((signal) => api.ingestMeeting(body, (id) => {
        writePending({ id, repo, title, startedAt });
        setStage("transcribing");
      }, signal));
      if (saved) form.reset();
    }}>
      <h2 className="flex items-center gap-2 font-semibold"><Upload size={16} aria-hidden /> Add a handover</h2>
      <p className="text-sm text-ink-2">Upload an audio recording or a JSON/text transcript to connect the conversation to {repo ?? "your repository"}. Audio is transcribed automatically, then the decisions in it are extracted and linked to the code.</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="space-y-1 text-sm">Meeting title<input name="title" className="field w-full" placeholder="Architecture handover" maxLength={200} disabled={busy} /></label>
        <label className="space-y-1 text-sm">Recording or transcript<input name="file" type="file" className="field w-full" accept="audio/*,.json,.txt" required disabled={busy} /></label>
      </div>
      <p className="text-xs text-ink-3">Up to 4 MB. Transcripts are JSON or plain text with one <code className="t-code">Speaker: words</code> line per turn. A recording takes about a third of its length to transcribe (a 10-minute call takes 3 to 4 minutes) and is not stored for playback.</p>
      <label className="flex items-start gap-2 text-sm text-ink-2">
        <input name="consent" type="checkbox" required disabled={busy} className="mt-0.5 h-4 w-4 accent-[var(--accent)]" />
        <span>Everyone in this conversation agreed to it being transcribed and shared with other members of this workspace.</span>
      </label>
      <button className="btn btn-primary" disabled={busy || !repo} type="submit">{busy ? "Processing handover…" : "Upload handover"}</button>
      {/* The ticking clock stays outside the live region so screen readers are not interrupted every second. */}
      {busy ? <p className="t-num text-sm text-ink-2">{status}</p> : null}
      <div aria-live="polite">
        {error ? <p role="alert" className="text-sm text-bad">{error}</p> : null}
        {meeting ? <p className="text-sm">Handover saved. <Link href={`/meetings/${encodeURIComponent(meeting)}`} className="underline">View transcript and decisions</Link></p> : null}
      </div>
    </form>
  );
}
