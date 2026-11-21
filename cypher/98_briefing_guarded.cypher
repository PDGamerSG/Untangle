// 98_briefing_guarded: active decisions a newcomer should read before changing anything, weighted by the evidence
// that guards them: an incident (6), a linked issue (3), a revert (3), a handover statement that confirms or
// contradicts it (3), a reason that says more than the decision's own text (1), and earlier values it replaced
// (1, or 2 for three or more). Agent notes count only with a rationale. Params: $repo, $limit.
MATCH (d:Decision {repo: $repo, status: 'active'})
WHERE d.kind <> 'agent' OR d.rationale IS NOT NULL
WITH d,
     COUNT { (d)-[:MOTIVATED_BY]->(i:Issue) WHERE coalesce(i.is_incident, false) OR i:Incident } AS incidents,
     COUNT { (d)-[:MOTIVATED_BY]->(:Issue) } AS motivated,
     COUNT { (d)-[:SUPERSEDES*1..10]->(:Decision) } AS earlier,
     COUNT { (:Decision)-[:CONFIRMS|CONTRADICTS]->(d) } AS spoken,
     CASE WHEN d.signal = 'revert_commit' THEN 1 ELSE 0 END AS reverted,
     CASE WHEN d.rationale IS NOT NULL AND size(d.rationale) > 24 AND d.rationale <> coalesce(d.text, '') THEN 1 ELSE 0 END AS reasoned
WITH d, earlier, incidents + motivated + reverted + spoken AS linked,
     incidents * 6 + (motivated - incidents) * 3 + reverted * 3 + spoken * 3 + reasoned
       + CASE WHEN earlier >= 3 THEN 2 WHEN earlier > 0 THEN 1 ELSE 0 END AS weight
// A key that is gone describes nothing left to change unless an issue, revert or handover explains the removal.
WHERE weight >= 3 AND (toLower(coalesce(d.object, '')) <> 'removed' OR linked > 0)
ORDER BY weight DESC, d.valid_from DESC
LIMIT $limit
RETURN d.id AS id, d.kind AS kind, d.key AS key, d.subject AS subject, d.predicate AS predicate, d.object AS object,
       d.text AS text, d.rationale AS rationale, d.status AS status, d.valid_from AS valid_from, d.valid_to AS valid_to,
       d.created_at AS created_at, d.confidence AS confidence, d.signal AS signal, weight, earlier,
       [(d)-[:ABOUT]->(a) | {id: a.id, labels: labels(a), name: coalesce(a.name, a.key, a.path), path: a.path, key: a.key}] AS about,
       [(d)-[:STATED_BY]->(p:Person) | {id: p.id, name: p.name, login: p.login}][0] AS stated_by,
       [(d)-[:DECIDED_IN]->(x) | {id: x.id, labels: labels(x), title: coalesce(x.title, x.path), url: x.url, number: x.number,
                                  kind: x.kind, sha: x.sha, author: x.author_login,
                                  created_at: coalesce(x.merged_at, x.started_at, x.created_at, x.authored_at, x.date)}][0] AS decided_in,
       [(d)-[:MOTIVATED_BY]->(i:Issue) | {id: i.id, labels: labels(i), title: i.title, url: i.url, number: i.number,
                                          created_at: i.created_at, is_incident: coalesce(i.is_incident, false) OR i:Incident}] AS motivated_by,
       [(k:Decision)-[:CONFIRMS]->(d) | {id: k.id, text: k.text, object: k.object, kind: k.kind, rationale: k.rationale}] AS confirmed_by,
       [(k:Decision)-[:CONTRADICTS]->(d) | {id: k.id, text: k.text, object: k.object, kind: k.kind, rationale: k.rationale}] AS contradicted_by,
       [(d)-[:SUPERSEDES]->(o:Decision) | o.id] AS supersedes
