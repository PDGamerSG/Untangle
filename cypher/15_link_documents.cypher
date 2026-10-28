// 15_link_documents: (Document)-[:SUPERSEDED_BY]->(Document) from an ADR status "Superseded by ADR-0007".
// Params: $rows = [{old_id, new_id}].
UNWIND $rows AS r
MATCH (old:Document {id: r.old_id})
MATCH (new:Document {id: r.new_id})
MERGE (old)-[:SUPERSEDED_BY]->(new)
RETURN count(*) AS n
