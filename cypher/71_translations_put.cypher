// 71_translations_put: store English renderings so each sentence is translated once.
// Params: $rows = [{key, en, source, at}].
UNWIND $rows AS r
MERGE (t:Translation {key: r.key})
SET t.en = r.en, t.source = r.source, t.at = r.at
