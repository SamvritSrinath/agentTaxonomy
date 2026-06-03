import { copyFileSync, mkdirSync } from "node:fs";

mkdirSync("dist", { recursive: true });

copyFileSync("manifest.json", "dist/manifest.json");
copyFileSync("popup.html", "dist/popup.html");
copyFileSync("styles.css", "dist/styles.css");
