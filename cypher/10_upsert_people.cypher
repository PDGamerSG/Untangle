// 10_upsert_people: one Person per GitHub login when known, else per email. People are shared across repositories
// (no `repo` property, see CONTRACTS §2). Params: $rows = [{id, name, login, email, tokens, kind}].
UNWIND $rows AS r
MERGE (p:Person {id: r.id})
SET p.name = coalesce(r.name, p.name), p.login = coalesce(r.login, p.login), p.email = coalesce(r.email, p.email),
    p.tokens = r.tokens, p.kind = coalesce(r.kind, p.kind, 'contributor')
RETURN count(*) AS n
