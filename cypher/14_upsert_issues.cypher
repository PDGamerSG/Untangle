// 14_upsert_issues: Issue nodes (incidents also get the :Incident label) and (Person)-[:OPENED]->(Issue).
// Params: $rows = [{id, repo, number, title, body, state, labels, created_at, closed_at, url, author_login, is_incident,
//                   author_id}].
UNWIND $rows AS r
MERGE (i:Issue {id: r.id})
SET i.repo = r.repo, i.number = r.number, i.title = r.title, i.body = r.body, i.state = r.state, i.labels = r.labels,
    i.created_at = r.created_at, i.closed_at = r.closed_at, i.url = r.url, i.author_login = r.author_login,
    i.is_incident = r.is_incident
FOREACH (_ IN CASE WHEN r.is_incident THEN [1] ELSE [] END | SET i:Incident)
FOREACH (_ IN CASE WHEN r.is_incident THEN [] ELSE [1] END | REMOVE i:Incident)
WITH i, r
OPTIONAL MATCH (a:Person {id: r.author_id})
FOREACH (_ IN CASE WHEN a IS NULL THEN [] ELSE [1] END | MERGE (a)-[:OPENED]->(i))
RETURN count(*) AS n
