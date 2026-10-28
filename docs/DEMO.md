# Demo run-of-show (5 minutes) and the 31 Oct video script

The demo repo is **knadh/listmonk** (Indian open-source newsletter app, Go; ~2,300 commits, ~900 PRs). Everything
below is driven from the web app at http://localhost:3000 with the API on :8090 and Neo4j (local or Aura).

Before the demo: `kyun ingest knadh/listmonk` has run; `kyun kt ingest --repo knadh/listmonk --transcript
data/kt/listmonk-kt-sample.json` has run; the Aura instance is awake (it pauses after 72 h without writes);
`kyun eval` has produced `eval/out/listmonk.md`; a recording of this exact flow exists as a backup.

| # | Time | Beat | What to say / do |
|---|---|---|---|
| 1 | 0:00 | The problem | "When an engineer leaves, the *why* leaves with them. Commits, PR threads, incident tickets and Hinglish handover calls hold it, and nobody can search across them." One number from our interviews (time to first meaningful commit). |
| 1a | 0:20 | Pulse before the question | Open **Pulse**: "What is the team about to forget?" Show the contradiction queue and click **Ask why** on the code-vs-handover conflict. "Kyun can find the risky knowledge before a new engineer has to trip over it." |
| 2 | 0:30 | A question the docs can't answer | Ask: **why is app.concurrency set the way it is?** Walk the evidence chain on screen: decision → PR → incident → person → date. Open **Why this answer** and show the Cypher and the subgraph: "the model only wrote the sentence; the graph found the answer". |
| 3 | 1:30 | Supersession | Ask: **do we still …?** (a key whose value changed). The banner shows the older value struck through with its date. Toggle **Compare with vector-only**: the baseline quotes the old text with no warning. "This is the failure the brief describes, and why a vector index alone cannot do this job." |
| 4 | 2:15 | Honest refusal | Ask: **why does listmonk use MongoDB?** → refusal, closest entities, person to ask. No confidence bar. |
| 5 | 2:35 | KT in Hinglish | Open **Meetings** → the handover call. Show the Hinglish utterances with the code they mention as chips, and the decision "app.concurrency is 10" that the call produced: it is linked to `schema.sql::app.concurrency` with **CONFIRMS**, so back on Ask the answer leads with the code and quotes the call's reason ("SES का rate limit hit हो रहा था"). Then show `smtp.my0.max_msg_retries`: the call says 2, the repository removed the key, and the answer says the two conflict. (With `SARVAM_API_KEY` set, the same call ingests from audio via Saaras with diarization, and each utterance gets an English rendering.) |
| 6 | 3:30 | Person to ask and time travel | Ask **who should I ask about internal/manager?**; then drag the **Timeline** slider to a year ago: "this is what the team believed then". |
| 7 | 4:10 | Numbers and who pays | Show `eval/out/listmonk.md`: graph vs vector-only on evidence accuracy, supersession correctness, refusal precision, person hit rate, latency. Close with the buyer (engineering leaders; attrition and handover), the metric (time to first meaningful commit), the pricing hypothesis, and the three-month roadmap (PR guard bot, IDE/MCP, the UNO Q KT box). |

Backups: the recording; `NEXT_PUBLIC_KYUN_SAMPLE=1` sample mode in the web app (visibly labelled; never pretend it is live).

## 31 Oct submission video (≤ 3 minutes)

Same beats 2, 3, 4, 5 and 7, each ~30 s, screen-recorded with a voice-over. Start on the terminal running
`kyun ask "why is app.concurrency 10?" --repo knadh/listmonk` so the judges see the CLI and the graph
stats, then switch to the web app. End on the eval table and the repository link.
