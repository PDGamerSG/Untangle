MATCH (r:Repo {full_name:$repo})
CALL (r) {
  MATCH (n {repo:r.full_name})
  RETURN count(CASE WHEN n:File THEN 1 END) AS files,
    count(CASE WHEN n:File AND n.alive THEN 1 END) AS current_files,
    count(CASE WHEN n:Module THEN 1 END) AS modules, count(CASE WHEN n:Symbol THEN 1 END) AS symbols,
    count(CASE WHEN n:ConfigKey THEN 1 END) AS config_keys, count(CASE WHEN n:Dependency THEN 1 END) AS dependencies,
    count(CASE WHEN n:Document THEN 1 END) AS documents, count(CASE WHEN n:Commit THEN 1 END) AS commits,
    count(CASE WHEN n:PullRequest THEN 1 END) AS prs, count(CASE WHEN n:Issue THEN 1 END) AS issues,
    count(CASE WHEN n:Decision THEN 1 END) AS decisions, count(CASE WHEN n:Feature THEN 1 END) AS features,
    count(CASE WHEN n:Chunk THEN 1 END) AS chunks, count(CASE WHEN n:Meeting THEN 1 END) AS meetings
}
CALL (r) { MATCH (p:Person)--(n {repo:r.full_name}) RETURN count(DISTINCT p) AS people }
CALL (r) { MATCH (d:Dependency {repo:r.full_name})-[:DECLARED_IN]->(f:File) WITH d,f ORDER BY d.name LIMIT 50
  RETURN collect({id:d.id,name:d.name,ecosystem:d.ecosystem,version:d.current_version,path:f.path}) AS deps }
CALL (r) { MATCH (d:Document {repo:r.full_name}) WITH d ORDER BY d.path LIMIT 50
  RETURN collect({id:d.id,path:d.path,title:d.title}) AS docs }
CALL (r) { MATCH (f:Feature {repo:r.full_name}) OPTIONAL MATCH (f)-[:ENTRYPOINT]->(p:File)
  WITH f, collect(p.path) AS entrypoints ORDER BY f.name LIMIT 60
  RETURN collect({id:f.id,name:f.name,source:f.source,entrypoints:entrypoints}) AS feature_list }
RETURN r.full_name AS repo, r.url AS url, r.description AS description, r.default_branch AS default_branch,
  r.head_sha AS head_sha, r.ingested_at AS ingested_at, coalesce(r.languages,[]) AS languages,
  {files:files,current_files:current_files,modules:modules,symbols:symbols,config_keys:config_keys,dependencies:dependencies,documents:documents,
   commits:commits,prs:prs,issues:issues,decisions:decisions,people:people,features:features,chunks:chunks,meetings:meetings} AS counts,
  deps AS dependencies, docs AS documents, feature_list AS features, r.map_coverage AS map_coverage,
  r.import_limits AS import_limits, coalesce(r.import_warnings,[]) AS warnings
