// 36_prs_about_entity: merged pull requests that touched the entity's file(s), newest first, with their closing
// issues, author, review-comment count and first commits. The fallback evidence when no Decision exists
// ("no recorded decision, but it changed in PR #812 ..."). Params: $ids (entity ids), $limit.
UNWIND $ids AS eid
MATCH (e:File|Module|Symbol|ConfigKey|Dependency {id: eid})
OPTIONAL MATCH (e)-[:DEFINED_IN|SET_IN|DECLARED_IN]->(f1:File)
OPTIONAL MATCH (f2:File)-[:IN]->(e)
WITH collect(DISTINCT f1) + collect(DISTINCT f2) + collect(DISTINCT CASE WHEN e:File THEN e END) AS files
UNWIND files AS f
MATCH (pr:PullRequest)-[:TOUCHED]->(f)
WHERE pr.merged = true
WITH DISTINCT pr, collect(DISTINCT f.path) AS paths
ORDER BY coalesce(pr.merged_at, pr.created_at) DESC
LIMIT $limit
RETURN pr.id AS id, pr.number AS number, pr.title AS title, pr.url AS url, pr.merged_at AS merged_at,
       pr.created_at AS created_at, pr.author_login AS author_login, pr.labels AS labels,
       left(coalesce(pr.body, ''), 320) AS excerpt, paths,
       [(pr)-[:CLOSES]->(i:Issue) | {id: i.id, number: i.number, title: i.title, url: i.url,
                                     is_incident: coalesce(i.is_incident, false) OR i:Incident}] AS closes,
       [(p:Person)-[:OPENED]->(pr) | {id: p.id, name: p.name, login: p.login}][0] AS author,
       size([(c:Comment)-[:ON]->(pr) WHERE c.kind IN ['pr_review', 'pr_review_comment'] | c]) AS review_comments,
       [(c:Commit)-[:PART_OF]->(pr) | {id: c.id, sha: c.sha, title: c.title, authored_at: c.authored_at}][0..5] AS commits
