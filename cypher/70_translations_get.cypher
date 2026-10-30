// 70_translations_get: cached English renderings of stored text, keyed by the SHA-1 of the source text.
// Params: $keys.
UNWIND $keys AS k
MATCH (t:Translation {key: k})
RETURN t.key AS key, t.en AS en
