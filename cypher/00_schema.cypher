// Untangle graph schema. One statement per line; comment lines start with //. Every statement is idempotent.
// untangle.graph.schema.ensure_schema runs each line, then the unique-id constraints for UNIQUE_ID_LABELS, then
// waits for indexes to come online. {{EMBED_DIM}} is replaced with the configured embedding size.
// Only features available on AuraDB Free are used: one database, range/full-text/vector indexes, no APOC, no GDS.

// Range indexes
CREATE INDEX repo_full_name IF NOT EXISTS FOR (n:Repo) ON (n.full_name)
CREATE INDEX commit_sha IF NOT EXISTS FOR (n:Commit) ON (n.sha)
CREATE INDEX commit_repo_time IF NOT EXISTS FOR (n:Commit) ON (n.repo, n.authored_at)
CREATE INDEX file_repo_path IF NOT EXISTS FOR (n:File) ON (n.repo, n.path)
CREATE INDEX module_repo_path IF NOT EXISTS FOR (n:Module) ON (n.repo, n.path)
CREATE INDEX symbol_repo_name IF NOT EXISTS FOR (n:Symbol) ON (n.repo, n.name)
CREATE INDEX configkey_repo_key IF NOT EXISTS FOR (n:ConfigKey) ON (n.repo, n.key)
CREATE INDEX dependency_repo_name IF NOT EXISTS FOR (n:Dependency) ON (n.repo, n.name)
CREATE INDEX pr_repo_number IF NOT EXISTS FOR (n:PullRequest) ON (n.repo, n.number)
CREATE INDEX issue_repo_number IF NOT EXISTS FOR (n:Issue) ON (n.repo, n.number)
CREATE INDEX comment_repo_time IF NOT EXISTS FOR (n:Comment) ON (n.repo, n.created_at)
CREATE INDEX person_login IF NOT EXISTS FOR (n:Person) ON (n.login)
CREATE INDEX identity_value IF NOT EXISTS FOR (n:Identity) ON (n.kind, n.value)
CREATE INDEX decision_repo_status IF NOT EXISTS FOR (n:Decision) ON (n.repo, n.status)
CREATE INDEX decision_key IF NOT EXISTS FOR (n:Decision) ON (n.key)
CREATE INDEX decision_valid_from IF NOT EXISTS FOR (n:Decision) ON (n.valid_from)
CREATE INDEX decision_valid_to IF NOT EXISTS FOR (n:Decision) ON (n.valid_to)
CREATE INDEX chunk_repo_kind IF NOT EXISTS FOR (n:Chunk) ON (n.repo, n.source_kind)
CREATE INDEX meeting_repo IF NOT EXISTS FOR (n:Meeting) ON (n.repo)
CREATE INDEX utterance_meeting_seq IF NOT EXISTS FOR (n:Utterance) ON (n.meeting_id, n.seq)
CREATE INDEX translation_key IF NOT EXISTS FOR (n:Translation) ON (n.key)

// Full-text (Lucene standard analyzer). `tokens` holds names split on punctuation so `retry_limit` and `retry limit` both match.
CREATE FULLTEXT INDEX entity_search IF NOT EXISTS FOR (n:File|Module|Symbol|ConfigKey|Dependency) ON EACH [n.name, n.path, n.key, n.tokens]
CREATE FULLTEXT INDEX person_search IF NOT EXISTS FOR (n:Person) ON EACH [n.name, n.login, n.tokens]
CREATE FULLTEXT INDEX text_search IF NOT EXISTS FOR (n:Decision|PullRequest|Issue|Comment|Commit|Document|Chunk|Utterance) ON EACH [n.title, n.text, n.body, n.message]

// Vector index for the vector-only baseline and chunk recall. Cosine over normalised embeddings.
CREATE VECTOR INDEX chunk_embedding IF NOT EXISTS FOR (n:Chunk) ON (n.embedding) OPTIONS {indexConfig: {`vector.dimensions`: {{EMBED_DIM}}, `vector.similarity_function`: 'cosine'}}
