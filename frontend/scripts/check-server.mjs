// build-apk.bat runs this before building: the app's server comes only from VITE_API_URL in frontend/.env. It checks
// the value the build will really use (Vite's own env loading) and stops with a clear message when it is missing or wrong.
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { parseEnv } from "node:util";
import { loadEnv } from "vite";

const dir = fileURLToPath(new URL("..", import.meta.url));
const fail = (message) => {
  console.error(message);
  process.exit(1);
};

let own = "";
try {
  own = (parseEnv(readFileSync(`${dir}/.env`, "utf8").replace(/^\uFEFF/, "")).VITE_API_URL ?? "").trim();
} catch {
  // No frontend/.env yet.
}
if (!own) fail("Set the server first: put a line like VITE_API_URL=https://account.example.in in frontend/.env");
if (!/^https?:\/\/[^\s/]+/i.test(own)) {
  fail(`VITE_API_URL in frontend/.env must start with https:// (or http:// for a PC on your network); it is "${own}".`);
}
const used = (loadEnv("production", dir, "VITE_").VITE_API_URL ?? "").trim();
if (used !== own) {
  const others = [".env.local", ".env.production", ".env.production.local"].filter((name) => existsSync(`${dir}/${name}`));
  fail(
    used && others.length
      ? `VITE_API_URL is also set to "${used}" in ${others.join(" / ")}, which override frontend/.env. Remove it there.`
      : `The build would read VITE_API_URL as "${used}", not "${own}". Write the line in frontend/.env exactly as VITE_API_URL=${own} (saved as UTF-8 without a BOM).`,
  );
}
const host = new URL(own).hostname;
if (own.startsWith("http://") && !/^(localhost|\d{1,3}(\.\d{1,3}){3}|\[[0-9a-f:]+\])$/i.test(host)) {
  console.warn(`Note: ${own} uses http://. If that server redirects to https, the app cannot connect; use https:// then.`);
}
console.log(`Server built into the app: ${own}`);
