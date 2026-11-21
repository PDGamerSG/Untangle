import { spawnSync } from "node:child_process";
import { randomUUID } from "node:crypto";

// Both are required: domain routing, TLS and asset paths can fail independently.
const origins = [
  ["vercel", "https://untangle-code.vercel.app"],
  ["custom-domain", "https://untangle.pallabdas.me"],
];

// Both domains share one database, so one throwaway account serves the whole run. Supply UNTANGLE_LIVE_EMAIL and
// UNTANGLE_LIVE_PASSWORD to use an existing account instead; a created account is deleted at the end.
let email = process.env.UNTANGLE_LIVE_EMAIL;
let password = process.env.UNTANGLE_LIVE_PASSWORD;
let cookie = null;
if (!email || !password) {
  email = `live-check-${Date.now()}@example.com`;
  password = `live check ${randomUUID()}`;
  const response = await fetch(`${origins[0][1]}/api/auth/register`, {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ email, password, name: "Live check" }),
  });
  if (response.status !== 201) {
    console.error(`Could not create the live-check account: ${response.status} ${await response.text()}`);
    process.exit(1);
  }
  cookie = response.headers.get("set-cookie")?.split(";")[0] ?? null;
}

let failed = false;
for (const [name, origin] of origins) {
  console.log(`\nTesting production: ${origin}\n`);
  const result = spawnSync("pnpm", ["exec", "playwright", "test", "tests/production.spec.ts", "--workers=1", "--reporter=list,json",
    `--output=test-results/production-${name}`, ...process.argv.slice(2)], {
    stdio: "inherit",
    env: { ...process.env, UNTANGLE_LIVE_TESTS: "1", E2E_BASE_URL: origin, UNTANGLE_LIVE_EMAIL: email, UNTANGLE_LIVE_PASSWORD: password,
      PLAYWRIGHT_JSON_OUTPUT_FILE: `test-results/production-${name}/results.json` },
  });
  if (result.error) console.error(result.error.message);
  if (result.status !== 0) failed = true;
}

if (cookie) {
  const removed = await fetch(`${origins[0][1]}/api/auth/account`, { method: "DELETE", headers: { cookie } });
  console.log(`\nLive-check account ${removed.status === 204 ? "deleted" : `not deleted (${removed.status})`}.`);
}
process.exitCode = failed ? 1 : 0;
