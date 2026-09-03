/**
 * Things that go wrong in a built page without anything failing.
 *
 * An <Icon name="..."> Starlight does not ship renders an empty <svg> — no
 * error, no warning, just a button with a gap where its icon should be. That
 * is how the "Copy page" button lost its icon: `copy` is not one of the names
 * Starlight has, and nothing said so.
 *
 * Run after `astro build`:  node scripts/check-build.mjs
 */
import { readdir, readFile } from 'node:fs/promises';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

// fileURLToPath, not URL.pathname: on Windows the latter gives "/D:/..." and
// joining that produces "D:\D:\...".
const DIST = fileURLToPath(new URL('../dist', import.meta.url));

/** Every built page. */
async function* pages(dir) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) yield* pages(path);
    else if (entry.name.endsWith('.html')) yield path;
  }
}

const checks = [
  {
    name: 'empty <svg> (an icon name Starlight does not ship)',
    pattern: /<svg[^>]*>\s*<\/svg>/,
  },
  {
    // A snippet whose language has no grammar falls back to plain text, so the
    // page still builds and the code just reads as grey.
    name: 'code block that fell back to plaintext',
    pattern: /data-language="plaintext"[^>]*>\s*<code[^>]*>\s*<div[^>]*>\s*<span[^>]*>\s*(?:from|import|def|class|await|CACHE|RATE)/,
  },
  {
    name: 'unrendered MDX expression',
    pattern: /\{\s*(?:Astro|props|frontmatter)\./,
  },
];

let failures = 0;
let scanned = 0;

for await (const page of pages(DIST)) {
  scanned += 1;
  const html = await readFile(page, 'utf8');
  for (const check of checks) {
    if (check.pattern.test(html)) {
      console.error(`  ${relative(DIST, page)}: ${check.name}`);
      failures += 1;
    }
  }
}

console.log(`  checked ${scanned} pages`);
if (failures > 0) {
  console.error(`  ${failures} problem(s) found`);
  process.exit(1);
}
console.log('  no empty icons, no plaintext fallbacks, no unrendered expressions');
