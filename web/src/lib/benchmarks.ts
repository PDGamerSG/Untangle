// Generated from docs/development/EVAL.md (the recorded evaluation snapshot). Regenerate after a new run rather
// than editing by hand, so the page never shows a number the report does not.

export interface BenchmarkCell { outcome: string; evidence: string; supersession: string; person: string; entity: string }
export interface BenchmarkRow { id: string; intent: string; verified: boolean; graph?: BenchmarkCell; baseline?: BenchmarkCell }

export const BENCHMARK = {
  "recorded": "2026-10-28",
  "gold": "eval/gold/listmonk.yaml",
  "questions": 25,
  "verified": 19,
  "unverified": 6,
  "metrics": [
    {
      "name": "Questions",
      "graph": "19",
      "baseline": "19"
    },
    {
      "name": "Evidence-chain accuracy (cites + contains)",
      "graph": "9/11 (82%)",
      "baseline": "4/11 (36%)"
    },
    {
      "name": "Supersession correctness",
      "graph": "1/1 (100%)",
      "baseline": "0/1 (0%)"
    },
    {
      "name": "Refusal precision",
      "graph": "100%",
      "baseline": "n/a"
    },
    {
      "name": "Refusal recall",
      "graph": "100%",
      "baseline": "0%"
    },
    {
      "name": "Refusal F1",
      "graph": "100%",
      "baseline": "n/a"
    },
    {
      "name": "Person-to-ask hit rate",
      "graph": "4/4 (100%)",
      "baseline": "4/4 (100%)"
    },
    {
      "name": "Entity resolution hit rate",
      "graph": "13/14 (93%)",
      "baseline": "13/14 (93%)"
    },
    {
      "name": "Latency p50",
      "graph": "31 ms",
      "baseline": "14 ms"
    },
    {
      "name": "Latency p95",
      "graph": "96 ms",
      "baseline": "1369 ms"
    },
    {
      "name": "Errors",
      "graph": "0",
      "baseline": "0"
    }
  ],
  "rows": [
    {
      "id": "cfg-concurrency-why",
      "intent": "config_value",
      "verified": true,
      "graph": {
        "outcome": "answered",
        "evidence": "yes",
        "supersession": "-",
        "person": "-",
        "entity": "yes"
      },
      "baseline": {
        "outcome": "answered",
        "evidence": "NO",
        "supersession": "-",
        "person": "-",
        "entity": "yes"
      }
    },
    {
      "id": "cfg-message-rate",
      "intent": "config_value",
      "verified": true,
      "graph": {
        "outcome": "answered",
        "evidence": "yes",
        "supersession": "-",
        "person": "-",
        "entity": "yes"
      },
      "baseline": {
        "outcome": "answered",
        "evidence": "NO",
        "supersession": "-",
        "person": "-",
        "entity": "yes"
      }
    },
    {
      "id": "cfg-batch-size",
      "intent": "config_value",
      "verified": true,
      "graph": {
        "outcome": "answered",
        "evidence": "yes",
        "supersession": "-",
        "person": "-",
        "entity": "yes"
      },
      "baseline": {
        "outcome": "answered",
        "evidence": "NO",
        "supersession": "-",
        "person": "-",
        "entity": "yes"
      }
    },
    {
      "id": "cfg-max-send-errors",
      "intent": "config_value",
      "verified": true,
      "graph": {
        "outcome": "answered",
        "evidence": "yes",
        "supersession": "-",
        "person": "-",
        "entity": "yes"
      },
      "baseline": {
        "outcome": "answered",
        "evidence": "NO",
        "supersession": "-",
        "person": "-",
        "entity": "yes"
      }
    },
    {
      "id": "cfg-concurrency-history",
      "intent": "supersession",
      "verified": true,
      "graph": {
        "outcome": "answered",
        "evidence": "yes",
        "supersession": "yes",
        "person": "-",
        "entity": "yes"
      },
      "baseline": {
        "outcome": "answered",
        "evidence": "yes",
        "supersession": "NO",
        "person": "-",
        "entity": "yes"
      }
    },
    {
      "id": "file-manager",
      "intent": "entity_why",
      "verified": false,
      "graph": {
        "outcome": "answered",
        "evidence": "yes",
        "supersession": "-",
        "person": "-",
        "entity": "yes"
      },
      "baseline": {
        "outcome": "answered",
        "evidence": "yes",
        "supersession": "-",
        "person": "-",
        "entity": "yes"
      }
    },
    {
      "id": "file-queries-sql",
      "intent": "entity_why",
      "verified": false,
      "graph": {
        "outcome": "answered",
        "evidence": "yes",
        "supersession": "-",
        "person": "-",
        "entity": "yes"
      },
      "baseline": {
        "outcome": "answered",
        "evidence": "NO",
        "supersession": "-",
        "person": "-",
        "entity": "NO"
      }
    },
    {
      "id": "file-campaigns-go",
      "intent": "entity_why",
      "verified": false,
      "graph": {
        "outcome": "answered",
        "evidence": "yes",
        "supersession": "-",
        "person": "-",
        "entity": "yes"
      },
      "baseline": {
        "outcome": "answered",
        "evidence": "NO",
        "supersession": "-",
        "person": "-",
        "entity": "yes"
      }
    },
    {
      "id": "dep-lib-pq",
      "intent": "dependency",
      "verified": true,
      "graph": {
        "outcome": "answered",
        "evidence": "NO",
        "supersession": "-",
        "person": "-",
        "entity": "NO"
      },
      "baseline": {
        "outcome": "answered",
        "evidence": "NO",
        "supersession": "-",
        "person": "-",
        "entity": "NO"
      }
    },
    {
      "id": "dep-echo",
      "intent": "dependency",
      "verified": false,
      "graph": {
        "outcome": "answered",
        "evidence": "yes",
        "supersession": "-",
        "person": "-",
        "entity": "yes"
      },
      "baseline": {
        "outcome": "answered",
        "evidence": "NO",
        "supersession": "-",
        "person": "-",
        "entity": "yes"
      }
    },
    {
      "id": "refuse-mongodb",
      "intent": "refuse",
      "verified": true,
      "graph": {
        "outcome": "refused",
        "evidence": "-",
        "supersession": "-",
        "person": "-",
        "entity": "-"
      },
      "baseline": {
        "outcome": "answered (wrong)",
        "evidence": "-",
        "supersession": "-",
        "person": "-",
        "entity": "-"
      }
    },
    {
      "id": "refuse-kafka",
      "intent": "refuse",
      "verified": true,
      "graph": {
        "outcome": "refused",
        "evidence": "-",
        "supersession": "-",
        "person": "-",
        "entity": "-"
      },
      "baseline": {
        "outcome": "answered (wrong)",
        "evidence": "-",
        "supersession": "-",
        "person": "-",
        "entity": "-"
      }
    },
    {
      "id": "refuse-rust",
      "intent": "refuse",
      "verified": true,
      "graph": {
        "outcome": "refused",
        "evidence": "-",
        "supersession": "-",
        "person": "-",
        "entity": "-"
      },
      "baseline": {
        "outcome": "answered (wrong)",
        "evidence": "-",
        "supersession": "-",
        "person": "-",
        "entity": "-"
      }
    },
    {
      "id": "refuse-graphql",
      "intent": "refuse",
      "verified": true,
      "graph": {
        "outcome": "refused",
        "evidence": "-",
        "supersession": "-",
        "person": "-",
        "entity": "-"
      },
      "baseline": {
        "outcome": "answered (wrong)",
        "evidence": "-",
        "supersession": "-",
        "person": "-",
        "entity": "-"
      }
    },
    {
      "id": "refuse-redis",
      "intent": "refuse",
      "verified": true,
      "graph": {
        "outcome": "refused",
        "evidence": "-",
        "supersession": "-",
        "person": "-",
        "entity": "-"
      },
      "baseline": {
        "outcome": "answered (wrong)",
        "evidence": "-",
        "supersession": "-",
        "person": "-",
        "entity": "-"
      }
    },
    {
      "id": "who-manager",
      "intent": "who_to_ask",
      "verified": true,
      "graph": {
        "outcome": "answered",
        "evidence": "-",
        "supersession": "-",
        "person": "yes",
        "entity": "yes"
      },
      "baseline": {
        "outcome": "answered",
        "evidence": "-",
        "supersession": "-",
        "person": "yes",
        "entity": "yes"
      }
    },
    {
      "id": "who-queries",
      "intent": "who_to_ask",
      "verified": true,
      "graph": {
        "outcome": "answered",
        "evidence": "-",
        "supersession": "-",
        "person": "yes",
        "entity": "yes"
      },
      "baseline": {
        "outcome": "answered",
        "evidence": "-",
        "supersession": "-",
        "person": "yes",
        "entity": "yes"
      }
    },
    {
      "id": "who-campaigns",
      "intent": "who_to_ask",
      "verified": true,
      "graph": {
        "outcome": "answered",
        "evidence": "-",
        "supersession": "-",
        "person": "yes",
        "entity": "yes"
      },
      "baseline": {
        "outcome": "answered",
        "evidence": "-",
        "supersession": "-",
        "person": "yes",
        "entity": "yes"
      }
    },
    {
      "id": "who-frontend",
      "intent": "who_to_ask",
      "verified": false,
      "graph": {
        "outcome": "answered",
        "evidence": "-",
        "supersession": "-",
        "person": "yes",
        "entity": "yes"
      },
      "baseline": {
        "outcome": "answered",
        "evidence": "-",
        "supersession": "-",
        "person": "yes",
        "entity": "yes"
      }
    },
    {
      "id": "who-dockerfile",
      "intent": "who_to_ask",
      "verified": false,
      "graph": {
        "outcome": "answered",
        "evidence": "-",
        "supersession": "-",
        "person": "yes",
        "entity": "yes"
      },
      "baseline": {
        "outcome": "answered",
        "evidence": "-",
        "supersession": "-",
        "person": "yes",
        "entity": "yes"
      }
    },
    {
      "id": "kt-concurrency",
      "intent": "kt",
      "verified": true,
      "graph": {
        "outcome": "answered",
        "evidence": "yes",
        "supersession": "-",
        "person": "-",
        "entity": "yes"
      },
      "baseline": {
        "outcome": "answered",
        "evidence": "yes",
        "supersession": "-",
        "person": "-",
        "entity": "yes"
      }
    },
    {
      "id": "kt-max-send-errors",
      "intent": "kt",
      "verified": true,
      "graph": {
        "outcome": "answered",
        "evidence": "yes",
        "supersession": "-",
        "person": "-",
        "entity": "yes"
      },
      "baseline": {
        "outcome": "answered",
        "evidence": "yes",
        "supersession": "-",
        "person": "-",
        "entity": "yes"
      }
    },
    {
      "id": "kt-owner-manager",
      "intent": "who_to_ask",
      "verified": true,
      "graph": {
        "outcome": "answered",
        "evidence": "yes",
        "supersession": "-",
        "person": "yes",
        "entity": "yes"
      },
      "baseline": {
        "outcome": "answered",
        "evidence": "yes",
        "supersession": "-",
        "person": "yes",
        "entity": "yes"
      }
    },
    {
      "id": "kt-retry-revert",
      "intent": "kt",
      "verified": true,
      "graph": {
        "outcome": "answered",
        "evidence": "NO",
        "supersession": "-",
        "person": "-",
        "entity": "yes"
      },
      "baseline": {
        "outcome": "answered",
        "evidence": "NO",
        "supersession": "-",
        "person": "-",
        "entity": "yes"
      }
    },
    {
      "id": "kt-queries-sql",
      "intent": "kt",
      "verified": true,
      "graph": {
        "outcome": "answered",
        "evidence": "yes",
        "supersession": "-",
        "person": "-",
        "entity": "yes"
      },
      "baseline": {
        "outcome": "answered",
        "evidence": "NO",
        "supersession": "-",
        "person": "-",
        "entity": "yes"
      }
    }
  ]
} as const satisfies {
  recorded: string; gold: string; questions: number; verified: number; unverified: number;
  metrics: readonly { name: string; graph: string; baseline: string }[];
  rows: readonly BenchmarkRow[];
};
