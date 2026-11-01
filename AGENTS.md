# Untangle project instructions

## Production verification

Whenever testing a release or reporting production verification, test **both** public URLs:

- https://untangle-code.vercel.app
- https://untangle.pallabdas.me

Run the live browser suite against each origin after deploying. Check the landing page, repository onboarding
and selection, dashboard, Ask with citations, history, Pulse, feature/commit map, downloads, icons and mobile
navigation. Report the exact results for each origin. A passing check on one domain does not verify the other.
Local and mocked tests remain useful but do not replace these live checks. If a domain is unavailable, report
the failure rather than claiming deployment is fully verified.

Keep model/provider names out of the website's own UI copy. Preserve genuine names in repository evidence,
source code and dependencies. Use the configured lower-cost Claude API; do not upgrade the model without the
user's request. Never put credentials in browser code, logs or commits.

Follow `web/AGENTS.md` when changing the Next.js application.
