// 35_decision_search: full-text search over `text_search` restricted to Decision nodes of one repo, expanded to the
// SUPERSEDES chains of the hits. Params: $repo, $q (Lucene query), $limit (hits), $chain_limit (rows after expansion).
// `score` is the best full-text score in the row's chain; `hit_score` is the row's own score (0 for chain members
// that did not match themselves). Lucene cannot filter by label, so a generous inner limit is used before filtering.
CALL db.index.fulltext.queryNodes('text_search', $q, {limit: 300}) YIELD node, score
WHERE node:Decision AND node.repo = $repo
WITH node AS root, score
ORDER BY score DESC
LIMIT $limit
OPTIONAL MATCH (root)-[:SUPERSEDES*0..10]->(older:Decision)
OPTIONAL MATCH (newer:Decision)-[:SUPERSEDES*1..10]->(root)
WITH root, score, collect(DISTINCT older) + collect(DISTINCT newer) AS members
UNWIND members AS d
WITH d, max(score) AS score, max(CASE WHEN d.id = root.id THEN score ELSE 0.0 END) AS hit_score
ORDER BY score DESC, hit_score DESC
LIMIT $chain_limit
RETURN d.id AS id, d.kind AS kind, d.key AS key, d.subject AS subject, d.predicate AS predicate, d.object AS object,
       d.text AS text, d.rationale AS rationale, d.status AS status, d.valid_from AS valid_from, d.valid_to AS valid_to,
       d.created_at AS created_at, d.confidence AS confidence, d.signal AS signal,
       [(d)-[:ABOUT]->(a) | {id: a.id, labels: labels(a), name: coalesce(a.name, a.key, a.path), path: a.path, key: a.key}] AS about,
       [(d)-[:STATED_BY]->(p:Person) | {id: p.id, name: p.name, login: p.login}][0] AS stated_by,
       [(d)-[:DECIDED_IN]->(x) | {id: x.id, labels: labels(x), title: coalesce(x.title, x.path), url: x.url, number: x.number,
                                  kind: x.kind, sha: x.sha, author: x.author_login,
                                  created_at: coalesce(x.merged_at, x.started_at, x.created_at, x.authored_at, x.date)}][0] AS decided_in,
       [(d)-[:MOTIVATED_BY]->(i:Issue) | {id: i.id, labels: labels(i), title: i.title, url: i.url, number: i.number,
                                          created_at: i.created_at, excerpt: left(coalesce(i.body, ''), 320),
                                          is_incident: coalesce(i.is_incident, false) OR i:Incident}] AS motivated_by,
       [(d)-[:IMPLEMENTED_BY]->(c:Commit) | {id: c.id, labels: labels(c), title: c.title, url: c.url, sha: c.sha,
                                             created_at: c.authored_at, excerpt: left(coalesce(c.message, ''), 320),
                                             author: [(pp:Person)-[:AUTHORED]->(c) | pp.name][0]}] AS implemented_by,
       [(d)-[:EVIDENCED_BY]->(ev) | {id: ev.id, labels: labels(ev), title: coalesce(ev.title, ev.path), kind: ev.kind,
                                     number: ev.number, sha: ev.sha, url: ev.url, path: ev.path, speaker: ev.speaker_label,
                                     excerpt: left(coalesce(ev.body, ev.message, ev.text_en, ev.text, ev.title, ''), 320),
                                     created_at: coalesce(ev.created_at, ev.authored_at, ev.date,
                                                          [(ev)<-[:HAS]-(m:Meeting) | m.started_at][0]),
                                     author: coalesce(ev.author_login,
                                                      [(ev)<-[:AUTHORED|WROTE|OPENED]-(pp:Person) | pp.name][0],
                                                      [(ev)-[:SPOKEN_BY]->(sp:Person) | sp.name][0])}] AS evidence,
       [(d)-[:CONFIRMS]->(c:Decision) | {id: c.id, text: c.text, object: c.object, kind: c.kind}] AS confirms,
       [(d)-[:CONTRADICTS]->(c:Decision) | {id: c.id, text: c.text, object: c.object, kind: c.kind}] AS contradicts,
       [(k:Decision)-[:CONFIRMS]->(d) | {id: k.id, text: k.text, object: k.object, kind: k.kind, rationale: k.rationale}] AS confirmed_by,
       [(k:Decision)-[:CONTRADICTS]->(d) | {id: k.id, text: k.text, object: k.object, kind: k.kind, rationale: k.rationale}] AS contradicted_by,
       [(d)-[:SUPERSEDES]->(o:Decision) | o.id] AS supersedes,
       [(n:Decision)-[s:SUPERSEDES]->(d) | {id: n.id, at: s.at, signal: s.signal}] AS superseded_by
       , score, hit_score
