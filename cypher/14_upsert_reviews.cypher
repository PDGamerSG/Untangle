// 14_upsert_reviews: (Person)-[:REVIEWED {state, at}]->(PullRequest). One edge per reviewer and PR; the loader sends
// rows oldest first so the latest review state wins. Params: $rows = [{person_id, pr_id, state, at}].
UNWIND $rows AS r
MATCH (p:PullRequest {id: r.pr_id})
MATCH (a:Person {id: r.person_id})
MERGE (a)-[v:REVIEWED]->(p)
SET v.state = r.state, v.at = r.at
RETURN count(*) AS n
