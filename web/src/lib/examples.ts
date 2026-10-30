/** Example questions and search terms per repository, picked so each one has an answer in that repository's graph. */
export interface RepoExamples {
  trace: string;
  current: string;
  owner: string;
  changed: string;
  refusal: string;
  search: string[];
}

const UNTANGLE: RepoExamples = {
  trace: "why do we use neo4j in pyproject.toml?",
  current: "do we still use fastapi?",
  owner: "who should I ask about src/untangle/answer?",
  changed: "what changed in docker-compose.yml?",
  refusal: "why does Untangle use MongoDB?",
  search: ["neo4j", "concurrency", "docker-compose.yml", "README.md", "config"],
};

const EXAMPLES: Record<string, RepoExamples> = {
  "PDGamerSG/Untangle": UNTANGLE,
  "knadh/listmonk": {
    trace: "why is app.concurrency set the way it is?",
    current: "do we still use github.com/lib/pq?",
    owner: "who should I ask about internal/manager?",
    changed: "what changed in docker-compose.yml?",
    refusal: "why does listmonk use MongoDB?",
    search: ["concurrency", "smtp", "docker-compose.yml", "queries.sql", "pq"],
  },
  "dcondrey/onrecord": {
    trace: "why do we use @contentauth/c2pa-node?",
    current: "do we still use @anthropic-ai/sdk?",
    owner: "who should I ask about src/cli.ts?",
    changed: "what changed in package.json?",
    refusal: "why does onrecord use MongoDB?",
    search: ["signature", "c2pa", "src/cli.ts", "schema", "README.md"],
  },
};

/** Questions that hold for any repository with a README, used until a repository has its own list. */
const GENERIC: RepoExamples = {
  trace: "why was README.md changed?",
  current: "what is the current state of README.md?",
  owner: "who should I ask about README.md?",
  changed: "what changed in README.md?",
  refusal: "why does this project use MongoDB?",
  search: ["README.md", "config", "test", "docs"],
};

export function examplesFor(repo: string | null | undefined): RepoExamples {
  return (repo && EXAMPLES[repo]) || GENERIC;
}
