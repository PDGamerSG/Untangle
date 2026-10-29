"use client";

import { useState } from "react";
import Link from "next/link";
import { Upload } from "lucide-react";
import { api, errorMessage, SAMPLE_MODE } from "@/lib/api";

export function MeetingUpload({ repo, onUploaded }: { repo: string | null; onUploaded: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [meeting, setMeeting] = useState<string | null>(null);
  if (SAMPLE_MODE) return null;

  return (
    <form className="card space-y-4 p-4 sm:p-5" onSubmit={async (event) => {
      event.preventDefault();
      if (!repo || busy) return;
      const form = event.currentTarget;
      const values = new FormData(form);
      const file = values.get("file");
      setError(""); setMeeting(null);
      if (!(file instanceof File) || !file.size) { setError("Choose a recording or transcript first."); return; }
      if (file.size > 4_000_000) { setError("Choose a file smaller than 4 MB, or upload a transcript of the recording."); return; }
      const body = new FormData();
      body.set("repo", repo);
      body.set("title", String(values.get("title") || file.name));
      body.set(/\.(json|txt)$/i.test(file.name) ? "transcript" : "audio", file);
      setBusy(true);
      try {
        const result = await api.ingestMeeting(body);
        setMeeting(result.meeting_id); form.reset(); onUploaded();
      } catch (err) { setError(errorMessage(err)); }
      finally { setBusy(false); }
    }}>
      <h2 className="flex items-center gap-2 font-semibold"><Upload size={16} aria-hidden /> Add a handover</h2>
      <p className="text-sm text-ink-2">Upload an audio recording or a JSON/text transcript to connect the conversation to {repo ?? "your repository"}. Audio is transcribed by Sarvam; Claude extracts the decisions.</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="space-y-1 text-sm">Meeting title<input name="title" className="field w-full" placeholder="Architecture handover" maxLength={200} disabled={busy} /></label>
        <label className="space-y-1 text-sm">Recording or transcript<input name="file" type="file" className="field w-full" accept="audio/*,.json,.txt" required disabled={busy} /></label>
      </div>
      <p className="text-xs text-ink-3">Up to 4 MB. Recordings are processed for transcription and are not stored for playback. Only upload conversations you have permission to share.</p>
      <button className="btn btn-primary" disabled={busy || !repo} type="submit">{busy ? "Processing handover…" : "Upload handover"}</button>
      <div aria-live="polite">
        {error ? <p role="alert" className="text-sm text-bad">{error}</p> : null}
        {meeting ? <p className="text-sm">Handover saved. <Link href={`/meetings/${encodeURIComponent(meeting)}`} className="underline">View transcript and decisions</Link></p> : null}
      </div>
    </form>
  );
}
