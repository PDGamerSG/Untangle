# Feature and commit impact map

## Decision

Combine explicit feature entry points, static file imports at the indexed Git HEAD, and Git commit/file history.
The map answers: which code supports a feature, which features share code, what a commit changed, and which
feature entry points can reach those changes through imports. It never executes a revert or labels inferred
reachability as a demonstrated failure.

The first release adds a `/map` workspace, read-only repository-map API, import indexing during ingestion,
and an Obsidian vault ZIP. A repository can define feature names and entry points in `.untangle/features.json`.
Repositories without that manifest show directory groups, explicitly labelled as inferred code areas.

## Research screen — 2026-11-01

This is a bounded primary-source investigation, not an exhaustive survey. Searches used official documentation
and upstream README files for "affected projects", "static dependency graph", "code intelligence index",
"git revert", "git bisect", "Obsidian graph" and "Obsidian internal links".

| Source | Observation | Consequence for Untangle |
| --- | --- | --- |
| [Nx affected](https://nx.dev/ci/features/affected) | Current Nx selects affected tasks using their inputs and upstream outputs; Nx 23 and earlier used project/dependent relationships. | Traverse reverse imports as a first candidate scope. Precise test selection needs task inputs as well, which this release does not model. |
| [dependency-cruiser](https://github.com/sverweij/dependency-cruiser#readme) | Static JS/TS dependencies support validation and visual output. | Static imports are useful evidence; avoid claiming complete runtime call coverage. |
| [SCIP](https://github.com/sourcegraph/scip#readme) | Language-specific indexers supply definitions, references and implementations. | Symbol-level impact is a future precision improvement with additional indexing cost. |
| [git revert](https://git-scm.com/docs/git-revert) | A revert applies inverse changes as a new commit; merge reverts require a mainline parent. | Removing a graph node is not equivalent to reverting a commit. A merge must not be treated as an ordinary patch. |
| [git bisect](https://git-scm.com/docs/git-bisect) | Finds a regression boundary using good/bad revisions and a test. | Test evidence is needed to establish actual breakage; history alone cannot establish it. |
| [Obsidian Graph view](https://help.obsidian.md/plugins/graph) | Notes are nodes and internal links are edges; local graphs have depth controls. | Export one note per feature/file/commit, with stable links and source metadata. |
| [Obsidian internal links](https://help.obsidian.md/links) | Wikilinks and URL-encoded Markdown links are supported; some filename characters are unsafe. | Use safe stable note filenames and keep original paths in note content. |

The Obsidian published pages returned app shells; the passages above were verified in the upstream
[Graph view](https://github.com/obsidianmd/obsidian-help/blob/master/en/Plugins/Graph%20view.md) and
[Internal links](https://github.com/obsidianmd/obsidian-help/blob/master/en/Linking%20notes%20and%20files/Internal%20links.md)
documents. An attempted Nx raw-document URL returned 404; its public documentation was used instead.
The 21st component search returned HTTP 401, so no external component was imported.

## Evidence model and limits

- **Observed:** Git parents and file changes, explicit feature entry points, supported static import declarations.
- **Inferred:** potential feature impact through the current import graph; shared dependencies between features.
- **Not established:** runtime failure, patch applicability, historical imports at each commit, dynamic imports
  with computed paths, service calls over HTTP, reflection, configuration effects, or external dependency effects.
- Python AST and literal JS/TS imports are supported. JS/TS extraction is lexical rather than type-resolved;
  aliases use local tsconfig/jsconfig mappings. Unsupported syntax and unresolved imports are reported.
- A negative result means no path in the indexed graph, never proof that reverting is safe.
- History is paginated and graph snapshots have explicit bounds. Counts distinguish returned from indexed data.
- Obsidian's native graph shows untyped links; relationship names and evidence live in the corresponding notes.

## Acceptance

Select a repository, inspect named features and shared files, page/search commit history, select a commit, see
changed files and affected features with shortest import paths, and download a linked Obsidian vault. Keyboard
selection, zoom/reset, mobile layout, empty/unindexed/error states and honest coverage labels are required.
Tests must prove reverse traversal direction, cycle handling, unrelated-feature exclusion, parsing boundaries,
repository isolation, reindex cleanup, Git parent preservation and export link integrity.

Actual reversal validation belongs in an isolated checkout with a passing baseline, a chosen mainline for merges,
`git revert --no-commit`, a conflict check, and the same affected tests/build. It is a separate execution step.
No API endpoint will change Git history or execute ingested repository code.

## Use the map

Open `/map`, select a feature to inspect its import graph, or select a commit from the paginated history to
highlight its changed files and potentially affected features. Commit history shows parent arrows. Imported
files can be opened at the exact indexed SHA. Search applies to the current page of 40 commits.

The **Export to Obsidian** action downloads a ZIP of Markdown notes with wikilinks. Extract it into a new folder,
open that folder as an Obsidian vault, and use Graph view. The `features`, `files` and `commits` tags support colored
groups. The export contains up to 200 recent indexed commits and the returned file graph (up to 2000 files).
It states its scope in README; no absent note is silently manufactured. Older commits can be exported with the
endpoint's `offset` parameter.

Normal ingestion refreshes the map. To refresh Git history and imports without rewriting decisions or embeddings:

```bash
uv run untangle map-index PDGamerSG/Untangle
# Or read an already checked-out repository; only committed HEAD is indexed:
uv run untangle map-index PDGamerSG/Untangle --path .
```

Define features in the target repository's `.untangle/features.json`:

```json
{"features": [{"id": "checkout", "name": "Checkout", "description": "Payment flow", "entrypoints": ["src/checkout.ts"]}]}
```

Definitions are explicit, repository-owned labels. Untangle does not ask a language model to invent feature
boundaries. Without a manifest it labels directory groups as inferred code areas. At most 60 definitions and
2000 eligible source files are indexed. Python AST and literal JS/TS imports are extracted without executing code;
local tsconfig/jsconfig `paths` are supported, while inherited configs and package export maps are not.

API: `GET /repository-map?repo=owner/name&offset=0&limit=40` and
`GET /repository-map/obsidian?repo=owner/name&offset=0&limit=200`. The API requires only the existing Neo4j connection.
`Feature` nodes have `ENTRYPOINT` links to files; `File` nodes have source-line-labelled `IMPORTS` links; commits
retain `parent_shas`. Each reindex atomically replaces only map-owned imports and feature definitions.
