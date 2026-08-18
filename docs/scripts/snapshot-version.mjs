/**
 * Freeze the current docs as an archived version.
 *
 *   npm run snapshot-version -- v1
 *
 * Copies src/content/docs/docs/** into src/content/docs/docs/<slug>/ (skipping
 * any existing archived versions), and writes the frozen sidebar to
 * src/versions/<slug>.sidebar.json with every slug rewritten to point at the
 * archived copy.
 *
 * Run this BEFORE you start editing docs for the next major — once you begin
 * editing in place, the tree is a hybrid and separating the versions means
 * cherry-picking from git history page by page.
 */
import { cp, mkdir, readdir, writeFile, readFile, access } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const DOCS = join(ROOT, 'src/content/docs/docs');
const VERSIONS_DIR = join(ROOT, 'src/versions');

const slug = process.argv[2];

if (!slug || !/^[a-z0-9][a-z0-9.-]*$/i.test(slug)) {
  console.error('Usage: npm run snapshot-version -- <slug>      e.g. v1\n');
  process.exit(1);
}

const { archivedVersions } = await import('../src/versions.mjs');
const knownSlugs = new Set(archivedVersions.map((v) => v.slug));

if (knownSlugs.has(slug)) {
  console.error(`Version "${slug}" is already registered in src/versions.mjs.`);
  process.exit(1);
}

const target = join(DOCS, slug);
if (await access(target).then(() => true, () => false)) {
  console.error(`${target} already exists — remove it first or pick another slug.`);
  process.exit(1);
}

// Copy the live docs, skipping directories belonging to other archived versions.
await mkdir(target, { recursive: true });
for (const entry of await readdir(DOCS, { withFileTypes: true })) {
  if (entry.name === slug) continue;
  if (entry.isDirectory() && knownSlugs.has(entry.name)) continue;
  await cp(join(DOCS, entry.name), join(target, entry.name), { recursive: true });
}

/**
 * Keep archived pages out of the search index.
 *
 * Pagefind indexes every page, so without this a search for "models" returns
 * both the current and the archived page — duplicated, near-identical results.
 * Starlight honours `pagefind: false` in frontmatter to skip a page.
 */
async function excludeFromSearch(dir) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) {
      await excludeFromSearch(path);
      continue;
    }
    if (!/\.mdx?$/.test(entry.name)) continue;

    const src = await readFile(path, 'utf8');
    if (/^pagefind:/m.test(src)) continue;

    const eol = src.includes('\r\n') ? '\r\n' : '\n';
    const lines = src.split(/\r?\n/);
    if (lines[0].replace(/^﻿/, '') !== '---') continue;

    const close = lines.findIndex((line, i) => i > 0 && line.trim() === '---');
    if (close === -1) continue;

    lines.splice(close, 0, 'pagefind: false');
    await writeFile(path, lines.join(eol), 'utf8');
  }
}

await excludeFromSearch(target);

// Freeze the sidebar exactly as it is today, repointing every slug at the copy.
const { currentSidebar } = await import('../src/sidebar.mjs');
const reslug = (items) =>
  items.map((item) => {
    const next = { ...item };
    if (typeof next.slug === 'string') next.slug = next.slug.replace(/^docs\//, `docs/${slug}/`);
    if (Array.isArray(next.items)) next.items = reslug(next.items);
    return next;
  });

await mkdir(VERSIONS_DIR, { recursive: true });
await writeFile(
  join(VERSIONS_DIR, `${slug}.sidebar.json`),
  JSON.stringify(reslug(currentSidebar), null, 2) + '\n',
  'utf8'
);

const count = (await readdir(target, { recursive: true })).filter((f) => /\.mdx?$/.test(f)).length;

console.log(`
Archived ${count} pages to src/content/docs/docs/${slug}/
Froze sidebar to src/versions/${slug}.sidebar.json

Next:
  1. Add this to \`archivedVersions\` in src/versions.mjs (newest first):

       { slug: '${slug}', label: '${slug.replace(/^v/, 'v')}.x' },

  2. Update \`currentVersion.label\` in the same file to the new major.
  3. npm run build
`);
