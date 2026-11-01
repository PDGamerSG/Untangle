import { spawnSync } from "node:child_process";

// Both are required: domain routing, TLS and asset paths can fail independently.
const origins = [
  ["vercel", "https://untangle-code.vercel.app"],
  ["custom-domain", "https://untangle.pallabdas.me"],
];
let failed = false;
for (const [name, origin] of origins) {
  console.log(`\nTesting production: ${origin}\n`);
  const result = spawnSync("pnpm", ["exec", "playwright", "test", "tests/production.spec.ts", "--workers=1",
    `--output=test-results/production-${name}`, ...process.argv.slice(2)], {
    stdio: "inherit",
    env: { ...process.env, UNTANGLE_LIVE_TESTS: "1", E2E_BASE_URL: origin },
  });
  if (result.error) console.error(result.error.message);
  if (result.status !== 0) failed = true;
}
process.exitCode = failed ? 1 : 0;
