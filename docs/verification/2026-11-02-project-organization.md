# Project organization and commit attribution — 2 November 2026

## Commit history

Removed four Claude co-author trailers from commit messages. Rewriting their descendants changed
34 commit IDs. Verified that every rewritten commit preserves its complete file tree, human author,
committer and timestamps; only the attribution line and affected parent IDs changed.

Updated all three published branches atomically using explicit force-with-lease checks:
`main`, `feat/claude-ui-onboarding` and `feat/connect-api-english`. Remote heads match the verified rewrite.
The pre-rewrite history and audit records are backed up locally under
`.git/attribution-cleanup-2026-11-02/`. Internal application checkpoints and recovery history are retained.

Added project instructions against AI commit attribution and `.claude/settings.json` with an empty
commit-attribution setting. These configuration changes are part of the local uncommitted work.

## Organization

Moved 28 components from the flat component directory into eight folders: `dashboard`, `decisions`,
`layout`, `map`, `meetings`, `pulse`, `repositories` and `ui`. The existing `ask` group remains alongside them.
Updated route imports, shared component imports, design-context paths and feature-map entry points.
Checked that the 24 components without earlier loading fixes preserve their implementation exactly,
apart from import paths. The other four retain the previously tested loading changes.

Moved eight documentation files into `architecture`, `development`, `guides` and `verification`.
Added a documentation index and a project structure guide. Updated local links, README references,
source comments and the example environment file. No broken local Markdown links or missing
feature-map entry points remain.

The Python package, API entry point, query directory, build roots, dependency manifests and deployment
configuration retain their existing locations. The organization changes and earlier loading fixes remain
local and have not been committed, pushed or deployed.

## Verification

- Backend lint: passed.
- Python suite with a disposable local Neo4j database: 278 passed, no skips (32.25 seconds).
- Web lint and production build: passed.
- API-client and browser suites: 47 passed (42.4 seconds).
- Python wheel build: passed; every packaged query loads outside the checkout.
- Markdown links, feature entry points, history integrity and whitespace checks: passed.

Public-domain baseline checks are recorded after the history-only push. They validate the existing
published application, not the local organization or loading changes.

- https://untangle-code.vercel.app: 10 passed, 0 failed (1.6 minutes).
- https://untangle.pallabdas.me: 10 passed, 0 failed (1.1 minutes).

Both origins covered landing, repository onboarding/selection, dashboard, cited answers, comparison,
history, Pulse, feature/commit maps, downloads, icons and mobile navigation.
