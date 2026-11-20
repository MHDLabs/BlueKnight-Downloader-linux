import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const scripts = [
  "web/js/shell.js",
  "web/js/routing.js",
  "web/js/components.js",
  "web/js/runtime.js",
];

const sources = scripts.map((path) => {
  const source = readFileSync(join(root, path), "utf8");
  // Parse each file on its own first, so syntax errors point to the right file.
  new Function(source);
  return source;
});

// Classic script tags share the page's global lexical scope. Parsing the files
// together also catches duplicate top-level let/const/class declarations,
// which individual node syntax checks cannot detect.
new Function(sources.join("\n;\n"));

console.log("Web JavaScript: OK");
console.log("  all four scripts parse independently");
console.log("  shared top-level declarations have no collisions");
