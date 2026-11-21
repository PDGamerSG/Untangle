// 87_rate_limit_peek: the current count of a fixed window without adding to it. Params: $id.
OPTIONAL MATCH (r:RateLimit {id: $id})
RETURN coalesce(r.count, 0) AS count
