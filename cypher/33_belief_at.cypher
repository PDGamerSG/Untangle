// 33_belief_at: the decisions in force at time $t for a repo, and those superseded since $t.
// Params: $repo, $t (epoch ms), $ids (entity ids to restrict to; [] for the whole repo), $limit.
// `in_force` = valid_from <= t < coalesce(valid_to, +inf); `superseded_since` = status superseded and valid_to > t.
// Retracted decisions are never returned. In-force first, newest first.
MATCH (d:Decision)
WHERE d.repo = $repo AND d.status IN ['active', 'superseded']
  AND (size($ids) = 0 OR EXISTS { (d)-[:ABOUT]->(a) WHERE a.id IN $ids })
  AND ((d.valid_from <= $t AND (d.valid_to IS NULL OR d.valid_to > $t))
       OR (d.status = 'superseded' AND d.valid_to IS NOT NULL AND d.valid_to > $t))
WITH d, (d.valid_from <= $t AND (d.valid_to IS NULL OR d.valid_to > $t)) AS in_force,
     (d.status = 'superseded' AND d.valid_to IS NOT NULL AND d.valid_to > $t) AS superseded_since
ORDER BY in_force DESC, d.valid_from DESC
LIMIT $limit
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
       , in_force, superseded_since
