# Third-party notices

Untangle is distributed under the [MIT License](LICENSE). The application can integrate with the following third-party
services and libraries; their own terms apply when you install or enable them.

| Component | Use in Untangle | Terms |
|---|---|---|
| Neo4j | Graph storage, indexes, and Cypher execution. | [Neo4j licenses](https://neo4j.com/licensing/) |
| Sarvam AI | Optional speech-to-text, translation, and language detection for KT recordings. | [Sarvam terms](https://www.sarvam.ai/terms) |
| GitHub API | Optional repository, pull request, review, and issue ingestion. | [GitHub terms](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service) |
| Python packages | Backend runtime and development dependencies are pinned in `uv.lock`. | Each package's license is published by its distributor. |
| JavaScript packages | Web runtime and development dependencies are pinned in `web/pnpm-lock.yaml`. | Each package's license is published by its distributor. |

Untangle does not bundle Neo4j, Sarvam credentials, GitHub credentials, model weights, or third-party service data.
The `knadh/listmonk` records in `data/kt/`, `eval/`, and `web/sample/` are demonstration fixtures and remain labelled as
such in the product documentation.
