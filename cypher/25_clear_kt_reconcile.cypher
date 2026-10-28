// 25_clear_kt_reconcile: drop the CONFIRMS / CONTRADICTS links of these spoken decisions before reconciling again,
// so a verdict made against an older picture of the repository cannot linger. Params: $ids (kt decision ids).
UNWIND $ids AS id
MATCH (k:Decision {id: id})-[x:CONFIRMS|CONTRADICTS]->()
DELETE x
RETURN count(x) AS cleared
