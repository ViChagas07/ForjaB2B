// Rasteriza as ilustracoes SVG em PNG (96 e 320 px) para revisao visual (Prompt 10, B4).
// Pasta de saida ignorada pelo Git: assets-src/render/.
// Uso: node scripts/rasterize-illustrations.mjs  (a partir de frontend/)
import { mkdirSync, readdirSync } from "node:fs";
import { resolve, basename } from "node:path";
import { fileURLToPath } from "node:url";

import { chromium } from "playwright";

const frontendRoot = resolve(fileURLToPath(new URL(".", import.meta.url)), "..");
const repoRoot = resolve(frontendRoot, "..");
const inputDir = resolve(repoRoot, "frontend/public/catalog/illustrations");
const extraDir = resolve(repoRoot, "backend/app/static/catalog");
const extras = ["protecao-respiratoria.svg", "protecao-maos.svg"];
const outDir = resolve(repoRoot, "assets-src/render");
const sizes = [96, 320];

mkdirSync(outDir, { recursive: true });
const files = readdirSync(inputDir)
  .filter((f) => f.endsWith(".svg"))
  .map((f) => resolve(inputDir, f));
for (const extra of extras) {
  files.push(resolve(extraDir, extra));
}

const browser = await chromium.launch();
const page = await browser.newPage();
for (const file of files) {
  for (const size of sizes) {
    const out = resolve(outDir, `${basename(file, ".svg")}-${size}.png`);
    await page.setViewportSize({ width: size, height: size });
    await page.goto(`file:///${file.split("\\").join("/")}`);
    await page.screenshot({ path: out, clip: { x: 0, y: 0, width: size, height: size } });
    console.log(`ok: ${basename(out)}`);
  }
}
await browser.close();
