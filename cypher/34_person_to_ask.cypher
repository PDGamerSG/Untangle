// 34_person_to_ask: who to ask about a set of entities, ranked by a recency-weighted score over four signals:
//   AUTHORED commits that TOUCHED the entity's files        weight 1.0 * exp(-age_days / 365)
//   REVIEWED pull requests that TOUCHED them                weight 0.8 * exp(-age_days / 365)
//   WROTE comments ABOUT_LINE them                          weight 0.5 * exp(-age_days / 365)
//   STATED_BY decisions ABOUT the entities themselves       weight 1.0 * exp(-age_days / 365)
// Params: $repo, $ids (File, Module, Symbol, ConfigKey or Dependency ids), $now (epoch ms), $limit.
// A Symbol/ConfigKey/Dependency resolves to the file it is DEFINED_IN/SET_IN/DECLARED_IN; a Module to the files IN it.
// Returns the top people with the counts that justify them ("authored 12 of 20 commits, reviewed 4 of 9 PRs").
UNWIND $ids AS eid
MATCH (e:File|Module|Symbol|ConfigKey|Dependency {id: eid})
OPTIONAL MATCH (e)-[:DEFINED_IN|SET_IN|DECLARED_IN]->(f1:File)
OPTIONAL MATCH (f2:File)-[:IN]->(e)
WITH collect(DISTINCT e) AS ents,
     collect(DISTINCT f1) + collect(DISTINCT f2) + collect(DISTINCT CASE WHEN e:File THEN e END) AS files
CALL (files) {
  UNWIND files AS f
  MATCH (c:Commit)-[:TOUCHED]->(f)
  RETURN count(DISTINCT c) AS total_commits
}
CALL (files) {
  UNWIND files AS f
  MATCH (pr:PullRequest)-[:TOUCHED]->(f)
  RETURN count(DISTINCT pr) AS total_prs
}
CALL (files, ents) {
  UNWIND files AS f
  MATCH (p:Person)-[:AUTHORED]->(c:Commit)-[:TOUCHED]->(f)
  RETURN DISTINCT p, 'commit' AS kind, c.id AS item,
         exp(-toFloat($now - coalesce(c.authored_at, 0)) / 31536000000.0) AS w
  UNION ALL
  UNWIND files AS f
  MATCH (p:Person)-[:REVIEWED]->(pr:PullRequest)-[:TOUCHED]->(f)
  RETURN DISTINCT p, 'review' AS kind, pr.id AS item,
         0.8 * exp(-toFloat($now - coalesce(pr.merged_at, pr.created_at, 0)) / 31536000000.0) AS w
  UNION ALL
  UNWIND files AS f
  MATCH (p:Person)-[:WROTE]->(cm:Comment)-[:ABOUT_LINE]->(f)
  RETURN DISTINCT p, 'comment' AS kind, cm.id AS item,
         0.5 * exp(-toFloat($now - coalesce(cm.created_at, 0)) / 31536000000.0) AS w
  UNION ALL
  UNWIND ents AS e
  MATCH (d:Decision)-[:ABOUT]->(e)
  MATCH (d)-[:STATED_BY]->(p:Person)
  RETURN DISTINCT p, 'decision' AS kind, d.id AS item,
         exp(-toFloat($now - coalesce(d.valid_from, 0)) / 31536000000.0) AS w
}
WITH total_commits, total_prs, p, kind, item, w
WITH total_commits, total_prs, p, kind, count(DISTINCT item) AS n, sum(w) AS w
WITH total_commits, total_prs, p, collect({kind: kind, n: n, weight: w}) AS parts, sum(w) AS score
ORDER BY score DESC
LIMIT $limit
RETURN p.id AS id, p.name AS name, p.login AS login, score, parts, total_commits, total_prs
