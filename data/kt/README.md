# Handover-call (KT) recordings and transcripts

Untangle turns a knowledge-transfer call into graph nodes (`Meeting`, `Utterance`, `Person`), links what was said
to the repository's files, config keys and dependencies (`MENTIONS`), and records the decisions that were spoken
as `kt` decisions on the same keys the code history uses, so a reason given on a call confirms or supersedes a
value found in commits.

## What is in this folder

| File | What |
|---|---|
| `listmonk-kt-sample.json` | **Synthetic**, clearly labelled (`_note`) three-speaker Hinglish handover call about the real `knadh/listmonk` repository. Fictional people; real paths, keys and dependency names; demo rationale. ~7 minutes of timestamps, 40 utterances. |

No audio is committed. Real recordings go here too (`*.wav`, `*.mp3`, `*.m4a`) but are git-ignored until the team
decides otherwise.

## Consent, every time

A KT call is personal data of everyone on it. Before recording:

1. Tell every participant the call is recorded, that it will be transcribed by Sarvam AI (an Indian cloud service;
   audio leaves your machine) and loaded into a Neo4j graph that other engineers will query.
2. Get a clear yes from each participant **on the recording** ("recording शुरू हो गई है, सब ठीक है?" and the answers).
3. Name the repository the call is about so the transcript lands on the right `Repo`.
4. Anyone can ask for their utterances to be removed later: `untangle kt` writes every node with the meeting id, so a
   meeting can be deleted with one Cypher statement (`MATCH (m:Meeting {id: $id}) OPTIONAL MATCH (m)-[:HAS]->(u) DETACH DELETE u, m`).

Do not record customers, do not record anyone who has not agreed, and do not put secrets (tokens, passwords, keys)
in a call that will be transcribed.

## Recording a real one

- Any format works; 16 kHz mono WAV gives the best diarisation. `ffmpeg -i call.m4a -ac 1 -ar 16000 call.wav`.
- Clips of at most 30 s go through Sarvam's synchronous endpoint; anything longer goes through the batch job API
  (up to a few hours) with speaker diarisation. If the batch API is not enabled on the account, WAV files fall back
  to 28-second windows through the synchronous endpoint (speaker labels are then per window).
- Say identifiers the way they are written (`app dot concurrency`, `queries dot sql`): Untangle sends the repository's
  most-touched file names, config keys, symbols and dependency names to Sarvam as `keyterms`, which biases
  recognition toward them.
- Give the call a title and, if you know it, the number of speakers:

```
untangle kt ingest --repo knadh/listmonk --audio data/kt/call.wav --title "Campaign manager handover" --speakers 3 --language hi-IN
```

`SARVAM_API_KEY` must be set in `.env`. Without it, transcribe elsewhere and load the transcript:

```
untangle kt ingest --repo knadh/listmonk --transcript data/kt/listmonk-kt-sample.json
untangle kt list --repo knadh/listmonk
untangle kt show "mtg:knadh/listmonk:listmonk-handover-campaign-manager-and-config-20261020"
```

## Transcript formats `untangle kt ingest --transcript` accepts

**Untangle JSON** (this folder's format):

```jsonc
{
  "title": "...", "language": "hi-IN", "started_at": "2026-10-20T10:00:00+05:30",
  "speakers": { "S1": { "name": "Rohan Mehta", "login": "rohan-gh", "email": "rohan@example.com" } },
  "utterances": [ { "speaker": "S1", "start_ms": 0, "end_ms": 9000, "text": "..." } ]
}
```

A `login` or `email` that the code history already knows links the speaker to that contributor's `Person`
node (the voice on the call and the commit author become one person); otherwise a `Person` of kind `speaker` is
created.

**Sarvam JSON**: the response of `POST /speech-to-text` (with `with_diarization`) or a batch job output document
(`diarized_transcript.entries[...]`). Speaker ids become the labels.

**Plain text**: one utterance per line, `Speaker: text`, optionally prefixed with `[mm:ss]`. Lines without a
speaker continue the previous one. Missing timestamps are estimated from text length.

## What the pipeline does with the words

- Consecutive entries of the same speaker closer than 1.5 s are merged; entries longer than 400 characters are
  split at sentence ends (`.`, `?`, `!`, `।`).
- With `SARVAM_API_KEY`, every utterance also gets `text_en` (Sarvam translate, `mayura:v1`) and the meeting's
  language is identified with `/text-lid` when the transcript does not say.
- Decisions: with `LLM_BACKEND=sarvam` (sarvam-105b) or `anthropic`/`openai`, the model is asked for strict JSON
  anchored on utterance numbers and the repository's keyterms (`signal: llm_kt`). With `LLM_BACKEND=fake` a
  transparent rule-based extractor runs (`signal: heuristic_kt`, confidence 0.5): sentences with decision cues in
  English or Hinglish that name an identifier the repository knows.
- Every KT decision is `EVIDENCED_BY` the utterances it came from, `STATED_BY` the speaker, `DECIDED_IN` the
  meeting and `ABOUT` the resolved entity. A `config_value` statement lands on the key
  `<path>::<key>|config_value`, exactly where `untangle ingest` puts the value it found in commits.
