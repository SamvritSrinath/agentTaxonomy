import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const root = new URL("../src", import.meta.url).pathname;
const exportPattern = /^\s*export\s+(?:declare\s+)?(?:async\s+)?(?:interface|type|function|const|class)\s+([A-Za-z0-9_]+)/;
const files = walk(root).filter((file) => /\.(ts|tsx)$/.test(file));
const failures = [];

for (const file of files) {
  const lines = readFileSync(file, "utf8").split("\n");
  lines.forEach((line, index) => {
    const match = line.match(exportPattern);
    if (!match) {
      return;
    }
    if (!hasLeadingTsdoc(lines, index)) {
      failures.push(`${file}:${index + 1} exported ${match[1]} is missing TSDoc`);
    }
  });
}

if (failures.length > 0) {
  console.error(failures.join("\n"));
  process.exit(1);
}

console.log(`TSDoc check passed for ${files.length} TypeScript files.`);

function walk(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? walk(path) : [path];
  });
}

function hasLeadingTsdoc(lines, index) {
  let cursor = index - 1;
  while (cursor >= 0 && lines[cursor].trim() === "") {
    cursor -= 1;
  }
  if (cursor < 0 || lines[cursor].trim() !== "*/") {
    return false;
  }
  for (let i = cursor; i >= Math.max(0, cursor - 16); i -= 1) {
    if (lines[i].trim().startsWith("/**")) {
      return true;
    }
  }
  return false;
}
