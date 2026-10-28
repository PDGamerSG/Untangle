// 39_decision_bounds: the time range a repository's decisions span, for the timeline slider. Params: $repo.
MATCH (d:Decision {repo: $repo})
RETURN min(d.valid_from) AS earliest, max(d.valid_from) AS latest, count(d) AS decisions
