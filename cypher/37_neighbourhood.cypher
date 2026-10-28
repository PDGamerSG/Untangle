// 37_neighbourhood: a small subgraph around a set of seed nodes for the "Why this answer" panel.
// Params: $ids (seed node ids of any label except Chunk/Identity), $per_seed (neighbours kept per seed), $limit
// (total nodes, 60 at most by convention). Decisions, people and PRs/issues are preferred as neighbours; Chunk and
// Identity nodes are never shown. Edges are those among the returned nodes only.
UNWIND $ids AS nid
MATCH (n:Decision|File|Module|Symbol|ConfigKey|Dependency|PullRequest|Issue|Commit|Person|Document|Comment|Meeting|Utterance|Repo {id: nid})
WITH collect(DISTINCT n) AS seeds
CALL (seeds) {
  UNWIND seeds AS s
  MATCH (s)-[r]-(m)
  WHERE NOT m:Chunk AND NOT m:Identity AND NOT m IN seeds
  WITH s, m
  ORDER BY CASE WHEN m:Decision THEN 0 WHEN m:Person THEN 1 WHEN m:PullRequest OR m:Issue THEN 2 ELSE 3 END
  WITH s, collect(DISTINCT m)[0..$per_seed] AS nb
  UNWIND nb AS m
  RETURN collect(DISTINCT m) AS extra
}
WITH (seeds + extra)[0..$limit] AS nodes
UNWIND nodes AS a
OPTIONAL MATCH (a)-[r]->(b)
WHERE b IN nodes
WITH nodes, collect(DISTINCT CASE WHEN r IS NULL THEN null ELSE {from: a.id, to: b.id, type: type(r)} END) AS edges
RETURN [n IN nodes | {
          id: n.id,
          label: [l IN labels(n) WHERE l <> 'Incident'][0],
          props: {
            name: coalesce(n.name, n.title, n.key, n.path, n.full_name, n.login, n.sha),
            text: left(coalesce(n.text, n.text_en, n.body, n.message, ''), 160),
            status: n.status, object: n.object, kind: n.kind, number: n.number, url: n.url, path: n.path,
            at: coalesce(n.valid_from, n.merged_at, n.created_at, n.authored_at, n.started_at, n.date)
          }
        }] AS nodes,
       edges
