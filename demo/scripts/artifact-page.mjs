/**
 * Write the page the Artifact host publishes.
 *
 * Vite's own index.html brings a full document with it, and the host supplies
 * that shell itself — so this emits just the parts that belong inside it,
 * with the hashed asset names read back out of the build rather than typed.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const dist = join(dirname(fileURLToPath(import.meta.url)), "..", "dist");
const built = readFileSync(join(dist, "index.html"), "utf8");

const js = /src="\.\/(assets\/[^"]+\.js)"/.exec(built)?.[1];
const css = /href="\.\/(assets\/[^"]+\.css)"/.exec(built)?.[1];
if (!js || !css) throw new Error("Could not find the built assets in dist/index.html");

writeFileSync(
  join(dist, "page.html"),
  `<title>Itinerary Costing</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="${css}">
<div id="root"></div>
<script type="module" src="${js}"></script>
`,
);

console.log(`page.html -> ${css}, ${js}`);
