// 13_upsert_config_keys: ConfigKeys (dotted keys of YAML/TOML/JSON/.env/INI files and source constants) and
// (ConfigKey)-[:SET_IN]->(File). current_value is null once a key was removed.
// Params: $rows = [{id, repo, key, path, tokens, current_value, current_since, file_id}].
UNWIND $rows AS r
MATCH (f:File {id: r.file_id})
MERGE (k:ConfigKey {id: r.id})
SET k.repo = r.repo, k.key = r.key, k.path = r.path, k.tokens = r.tokens, k.current_value = r.current_value,
    k.current_since = r.current_since
MERGE (k)-[:SET_IN]->(f)
RETURN count(*) AS n
