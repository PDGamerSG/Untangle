// 26_prune_kt_meeting: re-ingesting a handover call replaces what was extracted from it. Spoken decisions decided in
// this meeting that the current extraction no longer produces (for example because a key now resolves to the file
// that defines it today) are deleted with their links. Params: $meeting_id, $keep (decision ids just recorded).
MATCH (d:Decision {kind: 'kt'})-[:DECIDED_IN]->(:Meeting {id: $meeting_id})
WHERE NOT d.id IN $keep
DETACH DELETE d
RETURN count(*) AS pruned
