// 14_upsert_comments: review bodies, review comments, PR conversation and issue comments, with
// (Comment)-[:ON]->(PullRequest|Issue), (Person)-[:WROTE]->(Comment) and (Comment)-[:ABOUT_LINE]->(File).
// Params: $rows = [{id, repo, kind, body, created_at, url, author_login, path, line, review_state, on_id, author_id, file_id}].
UNWIND $rows AS r
MERGE (c:Comment {id: r.id})
SET c.repo = r.repo, c.kind = r.kind, c.body = r.body, c.created_at = r.created_at, c.url = r.url,
    c.author_login = r.author_login, c.path = r.path, c.line = r.line, c.review_state = r.review_state
WITH c, r
MATCH (t) WHERE (t:PullRequest OR t:Issue) AND t.id = r.on_id
MERGE (c)-[:ON]->(t)
WITH c, r
OPTIONAL MATCH (a:Person {id: r.author_id})
FOREACH (_ IN CASE WHEN a IS NULL THEN [] ELSE [1] END | MERGE (a)-[:WROTE]->(c))
WITH c, r
OPTIONAL MATCH (f:File {id: r.file_id})
FOREACH (_ IN CASE WHEN f IS NULL THEN [] ELSE [1] END | MERGE (c)-[:ABOUT_LINE]->(f))
RETURN count(*) AS n
