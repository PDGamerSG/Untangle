# Untangle eval: listmonk (knadh/listmonk)

Generated 2026-10-28T15:53:48.764853Z from `eval/gold/listmonk.yaml`: 25 questions (19 verified, 6 unverified), modes graph, baseline.

`graph` is Untangle's answer from the decision graph; `baseline` is vector-only retrieval over the same text (no decisions, no supersession, no refusal logic). An expectation marked *unverified* was written without checking the repository's history, so those rows are scored but reported apart.

## Summary (verified questions)

| Metric | graph | baseline |
|---|---|---|
| Questions | 19 | 19 |
| Evidence-chain accuracy (cites + contains) | 9/11 (82%) | 4/11 (36%) |
| Supersession correctness | 1/1 (100%) | 0/1 (0%) |
| Refusal precision | 100% | n/a |
| Refusal recall | 100% | 0% |
| Refusal F1 | 100% | n/a |
| Person-to-ask hit rate | 4/4 (100%) | 4/4 (100%) |
| Entity resolution hit rate | 13/14 (93%) | 13/14 (93%) |
| Latency p50 | 31 ms | 14 ms |
| Latency p95 | 96 ms | 1369 ms |
| Errors | 0 | 0 |

## Unverified expectations

| Metric | graph | baseline |
|---|---|---|
| Questions | 6 | 6 |
| Evidence-chain accuracy (cites + contains) | 4/4 (100%) | 1/4 (25%) |
| Supersession correctness | n/a | n/a |
| Refusal precision | n/a | n/a |
| Refusal recall | n/a | n/a |
| Refusal F1 | n/a | n/a |
| Person-to-ask hit rate | 2/2 (100%) | 2/2 (100%) |
| Entity resolution hit rate | 6/6 (100%) | 5/6 (83%) |
| Latency p50 | 35 ms | 13 ms |
| Latency p95 | 48 ms | 14 ms |
| Errors | 0 | 0 |

## Per question

| id | intent | mode | refused | evidence | supersession | person | entity | confidence | latency | answer |
|---|---|---|---|---|---|---|---|---|---|---|
| cfg-concurrency-why | config_value | graph | answered | yes | - | - | yes | 0.69 | 96 ms | `app.concurrency` in `schema.sql` is 10 [dec:knadh/listmonk:config_value:1746b14b6895]. It was set in commit 942eb7c 'Add settings UI and... |
| cfg-message-rate | config_value | graph | answered | yes | - | - | yes | 0.69 | 32 ms | `app.message_rate` in `schema.sql` is 10 [dec:knadh/listmonk:config_value:ca5bd6139c2e]. It was set in commit 942eb7c 'Add settings UI an... |
| cfg-batch-size | config_value | graph | answered | yes | - | - | yes | 0.69 | 32 ms | `app.batch_size` in `schema.sql` is 1000 [dec:knadh/listmonk:config_value:b348d6d92099]. It was set in commit 942eb7c 'Add settings UI an... |
| cfg-max-send-errors | config_value | graph | answered | yes | - | - | yes | 0.69 | 31 ms | `app.max_send_errors` in `schema.sql` is 1000 [dec:knadh/listmonk:config_value:23752b0a64fa]. It was set in commit 942eb7c 'Add settings ... |
| cfg-concurrency-history | supersession | graph | answered | yes | yes | - | yes | 0.69 | 34 ms | `app.concurrency` in `schema.sql` is 10 [dec:knadh/listmonk:config_value:1746b14b6895]. It was set in commit 942eb7c 'Add settings UI and... |
| file-manager *(unverified)* | entity_why | graph | answered | yes | - | - | yes | 0.70 | 33 ms | 8 decisions are recorded about `internal/manager/manager.go`: 1) internal/manager is owned by Priya Nair (said by Rohan Mehta in KT "List... |
| file-queries-sql *(unverified)* | entity_why | graph | answered | yes | - | - | yes | 0.74 | 45 ms | PR #2411: WIP: Fix SQL search [dec:knadh/listmonk:change:b7795eaee2f5]. It was set in PR #2411 'WIP: Fix SQL search.' by Kailash Nadh on ... |
| file-campaigns-go *(unverified)* | entity_why | graph | answered | yes | - | - | yes | 0.70 | 32 ms | 8 decisions are recorded about `cmd/campaigns.go`: 1) cmd/campaigns.go is owned by Priya Nair (said by Rohan Mehta in KT "Listmonk handov... |
| dep-lib-pq | dependency | graph | answered | NO | - | - | NO | 0.55 | 29 ms | `postgres.user` in `sqlboiler.toml` is removed [dec:knadh/listmonk:config_value:26a1c6c7ba2a]. It was set in commit 7eeb813 'Add embeddin... |
| dep-echo *(unverified)* | dependency | graph | answered | yes | - | - | yes | 0.66 | 35 ms | `github.com/labstack/echo/v4` is pinned at removed [dec:knadh/listmonk:dependency:e221b1b7ac8a]. It was set in commit 52f80cc 'Upgrade `l... |
| refuse-mongodb | refuse | graph | refused | - | - | - | - | 0.00 | 18 ms | Untangle found nothing in the graph that answers that. Closest related: resetDB (Symbol), initDB (Symbol), manager_db.go (File). Person to as... |
| refuse-kafka | refuse | graph | refused | - | - | - | - | 0.00 | 20 ms | Untangle found nothing in the graph that answers that. Closest related: none. Person to ask: Kailash Nadh, who authored 1386 of 2000 commits ... |
| refuse-rust | refuse | graph | refused | - | - | - | - | 0.00 | 16 ms | Untangle found nothing in the graph that answers that. Closest related: none. Person to ask: Kailash Nadh, who authored 1386 of 2000 commits ... |
| refuse-graphql | refuse | graph | refused | - | - | - | - | 0.00 | 21 ms | Untangle found nothing in the graph that answers that. Closest related: frontend/src/api (Module), frontend-vue/src/api (Module), api (Symbol... |
| refuse-redis | refuse | graph | refused | - | - | - | - | 0.00 | 17 ms | Untangle found nothing in the graph that answers that. Closest related: email-templates/subscriber-optin.html (File), static/public/subscribe... |
| who-manager | who_to_ask | graph | answered | - | - | yes | yes | 0.70 | 42 ms | Owner on record: Priya Nair; Rohan Mehta said so in the handover call 'Listmonk handover: campaign manager and config' on 20 Oct 2026 [de... |
| who-queries | who_to_ask | graph | answered | - | - | yes | yes | 0.70 | 50 ms | Person to ask about `queries.sql`: Kailash Nadh, who authored 174 of 189 commits on queries.sql, reviewed 3 of 18 PRs touching it, left 2... |
| who-campaigns | who_to_ask | graph | answered | - | - | yes | yes | 0.70 | 45 ms | Owner on record: Priya Nair; Rohan Mehta said so in the handover call 'Listmonk handover: campaign manager and config' on 20 Oct 2026 [de... |
| who-frontend *(unverified)* | who_to_ask | graph | answered | - | - | yes | yes | 0.60 | 48 ms | Person to ask about `frontend`: Kailash Nadh, who authored 60 of 153 commits on frontend, reviewed 1 of 94 PRs touching it [person:gh:kna... |
| who-dockerfile *(unverified)* | who_to_ask | graph | answered | - | - | yes | yes | 0.59 | 36 ms | Person to ask about `services.dev.build.dockerfile` in `dev/docker-compose.yml`: Kailash Nadh, who authored 5 of 8 commits on services.de... |
| kt-concurrency | kt | graph | answered | yes | - | - | yes | 0.70 | 28 ms | schema.sql::app.concurrency constraint: हाँ, दो। पहला: app.concurrency को 10 से ऊपर मत बढ़ाना जब तक SES quota बढ़वा ना लो, वरना वही 454 व... |
| kt-max-send-errors | kt | graph | answered | yes | - | - | yes | 0.70 | 29 ms | `app.max_send_errors` in `schema.sql` is 1000 [dec:knadh/listmonk:kt:e0f967c7ce94]. It was set in the handover call 'Listmonk handover: c... |
| kt-owner-manager | who_to_ask | graph | answered | yes | - | yes | yes | 0.70 | 31 ms | Owner on record: Priya Nair; Rohan Mehta said so in the handover call 'Listmonk handover: campaign manager and config' on 20 Oct 2026 [de... |
| kt-retry-revert | kt | graph | answered | NO | - | - | yes | 0.70 | 34 ms | internal/manager/manager.go constraint: manager.go में application level retry दोबारा add मत करना जब तक idempotency key ना हो, ये हमारी c... |
| kt-queries-sql | kt | graph | answered | yes | - | - | yes | 0.70 | 35 ms | queries.sql: chose postgres (said by Rohan Mehta in KT "Listmonk handover: campaign manager and config") [dec:knadh/listmonk:kt:855231fc0... |
| cfg-concurrency-why | config_value | baseline | answered | NO | - | - | yes | 0.00 | 1369 ms | Closest passages by embedding similarity, best first: (1) comment: Your last comment in that issue also makes it sound like this current ... |
| cfg-message-rate | config_value | baseline | answered | NO | - | - | yes | 0.00 | 11 ms | Closest passages by embedding similarity, best first: (1) comment: Your last comment in that issue also makes it sound like this current ... |
| cfg-batch-size | config_value | baseline | answered | NO | - | - | yes | 0.00 | 14 ms | Closest passages by embedding similarity, best first: (1) utterance: Priya Nair: और app.batch_size? वो 1000 क्यों है? [chunk:utt:mtg:knad... |
| cfg-max-send-errors | config_value | baseline | answered | NO | - | - | yes | 0.00 | 12 ms | Closest passages by embedding similarity, best first: (1) utterance: Rohan Mehta: max_send_errors को 1000 रखा है ताकि एक गलत SMTP config ... |
| cfg-concurrency-history | supersession | baseline | answered | yes | NO | - | yes | 0.00 | 12 ms | Closest passages by embedding similarity, best first: (1) utterance: Rohan Mehta: हाँ, दो। पहला: app.concurrency को 10 से ऊपर मत बढ़ाना ज... |
| file-manager *(unverified)* | entity_why | baseline | answered | yes | - | - | yes | 0.00 | 12 ms | Closest passages by embedding similarity, best first: (1) commit: Fix typo in manager.go [chunk:commit:knadh/listmonk@dc4e3a678038#0] (2)... |
| file-queries-sql *(unverified)* | entity_why | baseline | answered | NO | - | - | NO | 0.00 | 12 ms | Closest passages by embedding similarity, best first: (1) issue: Using the exact same SQL query to filter in listmonk's UI works correctl... |
| file-campaigns-go *(unverified)* | entity_why | baseline | answered | NO | - | - | yes | 0.00 | 13 ms | Closest passages by embedding similarity, best first: (1) comment: ### Issues Found No issues found. ### Summary Total issues: 0 critical... |
| dep-lib-pq | dependency | baseline | answered | NO | - | - | NO | 0.00 | 14 ms | Closest passages by embedding similarity, best first: (1) issue: ```yml db: image: postgres:13 environment: - POSTGRES_PASSWORD=listmonk ... |
| dep-echo *(unverified)* | dependency | baseline | answered | NO | - | - | yes | 0.00 | 14 ms | Closest passages by embedding similarity, best first: (1) comment: Duplicity of https://github.com/knadh/listmonk/issues/2814 [chunk:comm... |
| refuse-mongodb | refuse | baseline | answered (wrong) | - | - | - | - | 0.00 | 15 ms | Closest passages by embedding similarity, best first: (1) issue: Support for other Databases **Is your feature request related to a probl... |
| refuse-kafka | refuse | baseline | answered (wrong) | - | - | - | - | 0.00 | 14 ms | Closest passages by embedding similarity, best first: (1) issue: PostgreSQL - role "listmonk" does not exist **Version:** - listmonk: v2.... |
| refuse-rust | refuse | baseline | answered (wrong) | - | - | - | - | 0.00 | 13 ms | Closest passages by embedding similarity, best first: (1) comment: `sweetppro/listmonk:master` is unfortunately no longer compatible with... |
| refuse-graphql | refuse | baseline | answered (wrong) | - | - | - | - | 0.00 | 14 ms | Closest passages by embedding similarity, best first: (1) issue: Is there any rate limiting on the backend server..? [chunk:issue:knadh/l... |
| refuse-redis | refuse | baseline | answered (wrong) | - | - | - | - | 0.00 | 12 ms | Closest passages by embedding similarity, best first: (1) commit: Refactor subscriber data src to check for errors [chunk:commit:knadh/li... |
| who-manager | who_to_ask | baseline | answered | - | - | yes | yes | 0.00 | 15 ms | Closest passages by embedding similarity, best first: (1) commit: Update general-question.md [chunk:commit:knadh/listmonk@6a2658006634#0]... |
| who-queries | who_to_ask | baseline | answered | - | - | yes | yes | 0.00 | 14 ms | Closest passages by embedding similarity, best first: (1) utterance: Rohan Mehta: हाँ, queries.sql में हमने raw SQL रखा है, ORM नहीं, क्य... |
| who-campaigns | who_to_ask | baseline | answered | - | - | yes | yes | 0.00 | 14 ms | Closest passages by embedding similarity, best first: (1) utterance: Rohan Mehta: cmd/ में सारे HTTP handlers हैं, cmd/campaigns.go में c... |
| who-frontend *(unverified)* | who_to_ask | baseline | answered | - | - | yes | yes | 0.00 | 13 ms | Closest passages by embedding similarity, best first: (1) commit: chore: fix frontend directory structure [chunk:commit:knadh/listmonk@11... |
| who-dockerfile *(unverified)* | who_to_ask | baseline | answered | - | - | yes | yes | 0.00 | 14 ms | Closest passages by embedding similarity, best first: (1) issue: Any help getting up and running would be appreciate though, I believe I ... |
| kt-concurrency | kt | baseline | answered | yes | - | - | yes | 0.00 | 14 ms | Closest passages by embedding similarity, best first: (1) utterance: Rohan Mehta: हाँ, और env var का naming LISTMONK_app__concurrency जैस... |
| kt-max-send-errors | kt | baseline | answered | yes | - | - | yes | 0.00 | 14 ms | Closest passages by embedding similarity, best first: (1) utterance: Rohan Mehta: max_send_errors को 1000 रखा है ताकि एक गलत SMTP config ... |
| kt-owner-manager | who_to_ask | baseline | answered | yes | - | yes | yes | 0.00 | 14 ms | Closest passages by embedding similarity, best first: (1) utterance: Rohan Mehta: अब से internal/manager का owner Priya है। मैं exit के ब... |
| kt-retry-revert | kt | baseline | answered | NO | - | - | yes | 0.00 | 14 ms | Closest passages by embedding similarity, best first: (1) issue: For example, when I decided to seriously look into solving this recurrin... |
| kt-queries-sql | kt | baseline | answered | NO | - | - | yes | 0.00 | 14 ms | Closest passages by embedding similarity, best first: (1) commit: Fix discrepency in SQL query/export queries. Closes #1241. [chunk:commi... |
