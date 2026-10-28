// 14_link_references: (PullRequest)-[:CLOSES]->(Issue) from "closes/fixes/resolves #N" and
// (PullRequest|Issue|Commit)-[:REFERENCES]->(Issue|PullRequest) from plain "#N" mentions.
// The label disjunction keeps the lookup on the unique-id indexes. Params: $rows = [{from_id, rel, to_id}].
UNWIND $rows AS r
MATCH (a) WHERE (a:PullRequest OR a:Issue OR a:Commit) AND a.id = r.from_id
MATCH (b) WHERE (b:Issue OR b:PullRequest) AND b.id = r.to_id
FOREACH (_ IN CASE WHEN r.rel = 'CLOSES' THEN [1] ELSE [] END | MERGE (a)-[:CLOSES]->(b))
FOREACH (_ IN CASE WHEN r.rel = 'REFERENCES' THEN [1] ELSE [] END | MERGE (a)-[:REFERENCES]->(b))
RETURN count(*) AS n
