// 99_decision_state: every decision in force at $t, as (id, key) only, so two dates can be compared without the
// display limit of 33_belief_at. Agent notes are left out. Params: $repo, $t (epoch ms), $limit.
MATCH (d:Decision)
WHERE d.repo = $repo AND d.status IN ['active', 'superseded'] AND d.kind <> 'agent'
  AND d.valid_from <= $t AND (d.valid_to IS NULL OR d.valid_to > $t)
RETURN d.id AS id, coalesce(d.key, d.id) AS key
LIMIT $limit
