// 23_link_decisions: bulk version of 22_link_decision for ingestion. Same rows ({decision_id, rel, target_id, props})
// and the same semantics, but the target lookup names every label it may carry so the planner uses the unique-id
// indexes (an unlabelled `{id: ...}` match is a full node scan per row, which is far too slow for ~50k links).
// Missing targets are skipped, so a typo cannot invent evidence. Params: $rows, $now.
UNWIND $rows AS r
MATCH (d:Decision {id: r.decision_id})
MATCH (t) WHERE (t:File OR t:Symbol OR t:ConfigKey OR t:Dependency OR t:Module OR t:PullRequest OR t:Issue OR t:Document
                 OR t:Commit OR t:Comment OR t:Person OR t:Decision OR t:Meeting OR t:Utterance) AND t.id = r.target_id
FOREACH (_ IN CASE WHEN r.rel = 'ABOUT' THEN [1] ELSE [] END | MERGE (d)-[:ABOUT]->(t))
FOREACH (_ IN CASE WHEN r.rel = 'DECIDED_IN' THEN [1] ELSE [] END | MERGE (d)-[:DECIDED_IN]->(t))
FOREACH (_ IN CASE WHEN r.rel = 'EVIDENCED_BY' THEN [1] ELSE [] END | MERGE (d)-[:EVIDENCED_BY]->(t))
FOREACH (_ IN CASE WHEN r.rel = 'STATED_BY' THEN [1] ELSE [] END | MERGE (d)-[:STATED_BY]->(t))
FOREACH (_ IN CASE WHEN r.rel = 'IMPLEMENTED_BY' THEN [1] ELSE [] END | MERGE (d)-[:IMPLEMENTED_BY]->(t))
FOREACH (_ IN CASE WHEN r.rel = 'MOTIVATED_BY' THEN [1] ELSE [] END | MERGE (d)-[:MOTIVATED_BY]->(t))
FOREACH (_ IN CASE WHEN r.rel = 'SUPERSEDES' THEN [1] ELSE [] END |
  MERGE (d)-[s:SUPERSEDES]->(t) SET s.at = coalesce(r.props.at, $now), s.signal = coalesce(r.props.signal, 'explicit')
  SET t.status = CASE WHEN t.status = 'active' THEN 'superseded' ELSE t.status END,
      t.valid_to = coalesce(t.valid_to, d.valid_from), t.expired_at = coalesce(t.expired_at, $now)
)
RETURN count(*) AS linked
