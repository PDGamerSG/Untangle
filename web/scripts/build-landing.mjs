import { execFileSync } from "node:child_process";
import { cpSync, mkdirSync, rmSync } from "node:fs";
import { fileURLToPath } from "node:url";

const landing = fileURLToPath(new URL("../../landing", import.meta.url));
const destination = fileURLToPath(new URL("../public/welcome", import.meta.url));
execFileSync("pnpm", ["install", "--frozen-lockfile"], { cwd: landing, stdio: "inherit" });
execFileSync("pnpm", ["build", "--base=/welcome/"], { cwd: landing, stdio: "inherit" });
rmSync(destination, { recursive: true, force: true });
mkdirSync(destination, { recursive: true });
cpSync(`${landing}/dist`, destination, { recursive: true });
