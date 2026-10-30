// 60_pulse: active code decisions whose surrounding graph shows knowledge risk.
// Params: $repo, $now, $stale_before, $owner_stale_before, $limit.
// KT decisions are evidence against code decisions, never roots in this queue. Signal weights mirror untangle.pulse.
MATCH (d:Decision {repo: $repo, status: 'active'})
WHERE coalesce(d.kind, '') <> 'kt'
MATCH (d)-[:ABOUT]->(e)
WITH DISTINCT d, e
OPTIONAL MATCH (e)-[:SET_IN|DEFINED_IN|DECLARED_IN]->(f1:File)
OPTIONAL MATCH (f2:File)-[:IN]->(e)
WITH d, e, collect(DISTINCT f1) + collect(DISTINCT f2) AS files
UNWIND [e] + files AS target
WITH d, e, max(coalesce(target.last_touched_at, target.last_seen_at, target.first_seen_at)) AS last_touched
OPTIONAL MATCH (kt:Decision)-[:CONTRADICTS]->(d)
WITH d, e, last_touched, collect(DISTINCT kt) AS contradiction_nodes
OPTIONAL MATCH (d)-[:STATED_BY]->(owner:Person)
WITH collect({d: d, e: e, last_touched: last_touched, contradiction_nodes: contradiction_nodes, owner: owner}) AS rows,
     collect(DISTINCT owner) AS owners
// Each owner's latest activity is computed once, not once per decision: a maintainer can have thousands of commits
// and reviews, and expanding them for every decision they stated times out on large repositories.
CALL (owners) {
  UNWIND owners AS o
  CALL (o) {
    OPTIONAL MATCH (o)-[:AUTHORED]->(oc:Commit)
    WHERE oc.repo = $repo
    RETURN max(oc.authored_at) AS commit_last
  }
  CALL (o) {
    OPTIONAL MATCH (o)-[:REVIEWED]->(opr:PullRequest)
    WHERE opr.repo = $repo
    RETURN max(opr.merged_at) AS merged_last, max(opr.created_at) AS created_last
  }
  RETURN collect({id: o.id, last: reduce(latest = 0, x IN [commit_last, merged_last, created_last] |
                   CASE WHEN x IS NOT NULL AND x > latest THEN x ELSE latest END)}) AS activity
}
UNWIND rows AS r
WITH r.d AS d, r.e AS e, r.last_touched AS last_touched, r.contradiction_nodes AS contradiction_nodes, r.owner AS owner,
     CASE WHEN r.owner IS NULL THEN 0 ELSE coalesce([a IN activity WHERE a.id = r.owner.id | a.last][0], 0) END AS owner_last_active
WITH d, e, last_touched, contradiction_nodes, owner, owner_last_active,
     size(contradiction_nodes) > 0 AS contradiction,
     last_touched IS NOT NULL AND last_touched > coalesce(d.valid_from, 0) AS drift,
     owner IS NULL OR owner_last_active < $owner_stale_before AS ownership_gap,
     (coalesce(d.rationale, '') = '' AND size([(d)-[:EVIDENCED_BY]->() | 1]) = 0) AS rationale_gap,
     coalesce(d.valid_from, 0) < $stale_before AS stale
WITH d, e, last_touched, contradiction_nodes, owner, owner_last_active, contradiction, drift, ownership_gap, rationale_gap, stale,
     CASE WHEN contradiction THEN 0.72 ELSE 0 END +
     CASE WHEN drift THEN 0.16 ELSE 0 END +
     CASE WHEN ownership_gap THEN 0.14 ELSE 0 END +
     CASE WHEN rationale_gap THEN 0.11 ELSE 0 END +
     CASE WHEN stale THEN 0.08 ELSE 0 END AS raw_score
WITH d, e, last_touched, contradiction_nodes, owner, owner_last_active, contradiction, drift, ownership_gap, rationale_gap, stale,
     CASE WHEN raw_score > 1.0 THEN 1.0 ELSE raw_score END AS pulse_score
ORDER BY pulse_score DESC, d.valid_from ASC, d.id ASC
LIMIT $limit
RETURN count { MATCH (all:Decision {repo: $repo, status: 'active'}) WHERE coalesce(all.kind, '') <> 'kt' } AS active_decisions,
       d.id AS decision_id, d.kind AS decision_kind, d.key AS decision_key, d.subject AS decision_subject,
       d.predicate AS decision_predicate, d.object AS decision_object, d.text AS decision_text,
       d.rationale AS decision_rationale, d.status AS decision_status, d.valid_from AS decision_valid_from,
       d.valid_to AS decision_valid_to, d.created_at AS decision_created_at, d.confidence AS decision_confidence,
       d.signal AS decision_signal,
       {id: e.id, label: [l IN labels(e) WHERE l <> 'Incident'][0], name: coalesce(e.name, e.key, e.path),
        path: e.path, key: e.key} AS entity,
       CASE WHEN owner IS NULL THEN null ELSE {id: owner.id, name: owner.name, login: owner.login} END AS owner,
       [(d)-[:ABOUT]->(a) | {id: a.id, labels: labels(a), name: coalesce(a.name, a.key, a.path), path: a.path, key: a.key}] AS about,
       [(d)-[:STATED_BY]->(p:Person) | {id: p.id, name: p.name, login: p.login}][0] AS stated_by,
       [(d)-[:DECIDED_IN]->(x) | {id: x.id, labels: labels(x), title: coalesce(x.title, x.path), url: x.url,
                                  number: x.number, kind: x.kind, sha: x.sha, author: x.author_login,
                                  created_at: coalesce(x.merged_at, x.started_at, x.created_at, x.authored_at, x.date)}][0] AS decided_in,
       [(d)-[:MOTIVATED_BY]->(i:Issue) | {id: i.id, labels: labels(i), title: i.title, url: i.url, number: i.number,
                                          created_at: i.created_at, excerpt: left(coalesce(i.body, ''), 320),
                                          is_incident: coalesce(i.is_incident, false) OR i:Incident}] AS motivated_by,
       [(d)-[:IMPLEMENTED_BY]->(c:Commit) | {id: c.id, labels: labels(c), title: c.title, url: c.url, sha: c.sha,
                                             created_at: c.authored_at, excerpt: left(coalesce(c.message, ''), 320),
                                             author: [(pp:Person)-[:AUTHORED]->(c) | pp.name][0]}] AS implemented_by,
       [(d)-[:EVIDENCED_BY]->(ev) | {id: ev.id, labels: labels(ev), title: coalesce(ev.title, ev.path), kind: ev.kind,
                                     number: ev.number, sha: ev.sha, url: ev.url, path: ev.path,
                                     excerpt: left(coalesce(ev.body, ev.message, ev.text_en, ev.text, ev.title, ''), 320),
                                     created_at: coalesce(ev.created_at, ev.authored_at, ev.date),
                                     author: coalesce(ev.author_login, [(ev)<-[:AUTHORED|WROTE|OPENED]-(pp:Person) | pp.name][0])}] AS evidence,
       [(k:Decision)-[:CONTRADICTS]->(d) | {id: k.id, labels: labels(k), title: k.text, kind: k.kind,
                                           object: k.object, created_at: k.created_at,
                                           excerpt: left(coalesce(k.text, ''), 320)}] AS contradictions,
       contradiction, drift, ownership_gap, rationale_gap, stale, pulse_score,
       last_touched, owner_last_active
