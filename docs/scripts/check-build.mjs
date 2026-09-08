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
import { existsSync } from 'node:fs';
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
  {
    // A C0 control character in the page text. These arrive by accident
    // and are invisible in every editor: a Windows path written through a
    // tool that eats backslashes turns .venv\\Scripts\\activate into
    // Scripts + BEL + ctivate, which renders as "Scriptsctivate" and beeps
    // if anyone pastes it. Tab, newline and carriage return are the three
    // that legitimately appear in HTML, so they are not in the range.
    name: 'control character in page text',
    pattern: /[\u0000-\u0008\u000B\u000C\u000E-\u001F]/,
  },
];

/**
 * An ID selector styling `#_top` without saying which page it means.
 *
 * `#_top` is the skip-link target on every page, including the splash hero, so
 * an unscoped rule reaches both and wins on specificity over any class. That is
 * how the home page heading came out black on black in the light theme: a rule
 * written for doc titles set `color: var(--sl-color-white)`, which is near-black
 * in that theme, on a hero that is dark in both.
 */
async function checkStylesheets() {
  const astro = join(DIST, '_astro');
  let found = 0;
  for (const entry of await readdir(astro)) {
    if (!entry.endsWith('.css')) continue;
    const css = await readFile(join(astro, entry), 'utf8');
    // A rule beginning at `h1#_top` or `#_top` with nothing scoping it.
    for (const match of css.matchAll(/(^|[,}])\s*([a-z0-9]*#_top)\s*[,{]/g)) {
      console.error(
        `  ${entry}: "${match[2]}" is not scoped to a page -- it also matches ` +
        `the splash hero, and beats any class on specificity`
      );
      found += 1;
    }
  }
  return found;
}

/**
 * A built page referencing an asset that was never emitted.
 *
 * Astro caches rendered markdown. When the Expressive Code config changes, EC
 * emits its stylesheet under a new hash — but pages served from that cache keep
 * the <link> to the old one. The result is silent and partial: the few pages
 * that happened to re-render look perfect, and every cached page loses all code
 * styling, rendering snippets as unhighlighted black text on white.
 *
 * It shipped once as 85 of 89 pages pointing at a stylesheet that did not exist.
 * The cure is `rm -rf .astro node_modules/.astro dist` before rebuilding; this
 * check is here so the symptom is never silent again.
 */
async function checkAssetRefs() {
  const referenced = new Map();
  for await (const page of pages(DIST)) {
    const html = await readFile(page, 'utf8');
    for (const match of html.matchAll(/(?:href|src)="(\/_astro\/[^"]+\.(?:css|js))"/g)) {
      if (!referenced.has(match[1])) referenced.set(match[1], relative(DIST, page));
    }
  }

  let found = 0;
  for (const [asset, firstPage] of referenced) {
    if (existsSync(join(DIST, asset.slice(1)))) continue;
    console.error(
      `  ${asset} is referenced but was never emitted (first seen in ${firstPage}) -- ` +
      `stale Astro cache; clear .astro and node_modules/.astro, then rebuild`
    );
    found += 1;
  }
  return found;
}

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

failures += await checkStylesheets();
failures += await checkAssetRefs();

console.log(`  checked ${scanned} pages`);
if (failures > 0) {
  console.error(`  ${failures} problem(s) found`);
  process.exit(1);
}
console.log('  no empty icons, no plaintext fallbacks, no unrendered expressions,');
console.log('  no unscoped #_top rules, no missing asset references,');
console.log('  no stray control characters');
