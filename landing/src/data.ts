// Content for the page. Everything here comes from Untangle's checked-in sample
// fixtures for knadh/listmonk (web/sample/), so the page shows real output.

export const REPO_URL = "https://github.com/PDGamerSG/Untangle";
export const QUICKSTART_URL = `${REPO_URL}#-quick-start`;

/** "Why" in the languages of the teams that inherit code. The first entry is the page's own language. */
export const WHYS = [
  { text: "Why", lang: "en" },
  { text: "なぜ", lang: "ja" },
  { text: "¿Por qué", lang: "es" },
  { text: "Warum", lang: "de" },
  { text: "为什么", lang: "zh" },
  { text: "Pourquoi", lang: "fr" },
  { text: "Почему", lang: "ru" },
  { text: "왜", lang: "ko" },
  { text: "Kenapa", lang: "id" },
  { text: "Por quê", lang: "pt" },
  { text: "Neden", lang: "tr" },
];

/** Things people say about a codebase, floating inside the knot. */
export const FRAGMENTS = [
  "who set app.concurrency to 10?",
  "revert: per-message retry (duplicate sends)",
  "454 Throttling: Maximum sending rate exceeded",
  "LISTMONK_app__concurrency (double underscore!)",
  "don't add an ORM. ask Rohan why",
  "Rohan's last day is Friday",
  "#1747 Support for other databases",
  "concurrency = 5  # config.toml.sample",
  "TODO: document this somewhere",
  "it was 25 once. it broke.",
  "is lib/pq still the driver?",
  "max_msg_retries stays at 2",
  "why is batch_size 1000?",
  "nobody knows, it just works",
];

export const QUESTION = "why is app.concurrency set the way it is?";

export interface Tag {
  kind: string;
  title: string;
  titleIsCode?: boolean;
  titleLang?: string;
  note: string;
  href?: string;
}

/** The evidence chain Untangle returns for QUESTION, in the order it walks it. */
export const EVIDENCE: Tag[] = [
  { kind: "Entity", title: "app.concurrency", titleIsCode: true, note: "Config key in schema.sql, matched exactly" },
  { kind: "Decision", title: "app.concurrency is 10", note: "Active since 8 Jul 2020" },
  {
    kind: "Commit",
    title: "942eb7c",
    titleIsCode: true,
    note: "Add settings UI and “hot reload” support to the app.",
    href: "https://github.com/knadh/listmonk/commit/942eb7c3d86e925de5d9f7d0b6b40f7b8a9323fd",
  },
  {
    kind: "Handover call",
    title: "“We were hitting the SES rate limit.”",
    note: "Rohan Mehta, recorded handover call, 20 Oct 2026",
  },
  { kind: "Person to ask", title: "Kailash Nadh", note: "Authored 114 of 133 commits on app.concurrency" },
  { kind: "Date", title: "8 Jul 2020", note: "When the current value took effect" },
];

export const CONFIDENCE = {
  score: 0.69,
  label: "Medium confidence",
  reasons: [
    "2 independent sources",
    "Backed by a commit message",
    "The decision is active",
    "A recorded handover call confirms it",
    "Entity matched exactly",
    "The decision is 6 years old",
  ],
};

/** Value history of app.concurrency. Dates are when each decision took effect. */
export const HISTORY = [
  { date: "2018-10-25", value: "100", where: "config.toml.sample", label: "Set to 100" },
  { date: "2020-04-02", value: "5", where: "config.toml.sample", label: "Lowered to 5" },
  { date: "2020-07-08", value: "10", where: "schema.sql", label: "Moved to schema.sql at 10" },
  { date: "2026-10-20", value: "10", where: "schema.sql", label: "Handover call confirms 10", call: true },
];

export const TRANSCRIPT = [
  {
    at: "0:28",
    speaker: "Rohan Mehta",
    text: "We kept app.concurrency at 10 because we were hitting the SES rate limit.",
    links: ["app.concurrency"],
  },
  {
    at: "1:09",
    speaker: "Rohan Mehta",
    text: "There's an incident ticket, and the PR that took it from 25 to 10 says so in its description.",
    links: [],
  },
  {
    at: "2:59",
    speaker: "Rohan Mehta",
    text: "Don't add application-level retries back to manager.go until there's an idempotency key.",
    links: ["manager.go"],
  },
  {
    at: "4:51",
    speaker: "Rohan Mehta",
    text: "From now on, Priya owns internal/manager.",
    links: ["internal/manager"],
  },
  {
    at: "5:57",
    speaker: "Rohan Mehta",
    text: "Don't raise app.concurrency above 10 until the SES quota goes up.",
    links: ["app.concurrency"],
  },
];

export const REFUSAL = {
  question: "why does listmonk use MongoDB?",
  closest: [
    { name: "resetDB", kind: "Symbol", path: "tests/helpers.js" },
    { name: "initDB", kind: "Symbol", path: "cmd/init.go" },
    { name: "manager_db.go", kind: "File", path: "manager_db.go" },
  ],
  person: "Kailash Nadh",
};

export const RISKS = [
  {
    category: "Contradiction",
    score: 0.88,
    entity: "app.concurrency",
    reason: "A handover call contradicts the active code decision.",
  },
  {
    category: "Drift",
    score: 0.27,
    entity: "x-app-defaults.networks",
    reason: "Related code changed after this decision was recorded.",
  },
  {
    category: "Ownership gap",
    score: 0.14,
    entity: "github.com/lib/pq",
    reason: "No recent owner is attached to this decision.",
  },
];

export const COMMANDS = [
  "docker compose up -d neo4j",
  "uv sync --all-extras",
  "uv run untangle schema",
  "uv run untangle ingest knadh/listmonk",
  'uv run untangle ask "why is app.concurrency set the way it is?" --repo knadh/listmonk',
];
