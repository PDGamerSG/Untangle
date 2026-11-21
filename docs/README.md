# Untangle documentation

Start with the [project overview](../README.md) to run the application, or the
[folder guide](development/PROJECT_STRUCTURE.md) to find the code you need.

## Architecture

- [Graph model](architecture/GRAPH_MODEL.md): nodes, relationships and evidence.
- [Contracts](architecture/CONTRACTS.md): identifiers, API payloads and component boundaries.

## Development and operations

- [Project structure](development/PROJECT_STRUCTURE.md): folder ownership and placement conventions.
- [Deployment](development/DEPLOYMENT.md): Vercel services, environment variables and production checks.
- [Evaluation](development/EVAL.md): gold questions and graph/vector evaluation.

## Product guides

- [Repository imports](guides/REPOSITORY_IMPORTS.md): onboarding, estimates, limits and recovery.
- [Feature map](guides/FEATURE_MAP.md): indexing, graph exploration and exports.
- [Demo runbook](guides/DEMO.md): a walkthrough of the product.
- [Handover recordings](../data/kt/README.md): sample transcript and recording guidance.

## Verification and design history

- [Verification record](verification/VERIFICATION.md): previous checks and deployment evidence.
- [Repository loading fixes](verification/2026-11-02-repository-loading.md): reproduction, changes and test results.
- [Project organization](verification/2026-11-02-project-organization.md): folder changes, history cleanup and checks.
- [Design specifications](superpowers/specs/): historical design decisions.
- [Implementation plans](superpowers/plans/): historical execution plans.

Keep dated test reports in `verification/`, operating instructions in `development/`,
product walkthroughs in `guides/`, and durable technical contracts in `architecture/`.
