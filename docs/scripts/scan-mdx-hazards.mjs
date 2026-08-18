/**
 * Find `{` / `<` in MDX prose, which MDX parses as JS expressions / JSX tags.
 * Ignores fenced code, inline code spans, imports, and our own Tabs markup.
 */
import { readFileSync, globSync } from 'node:fs';

const FENCE = /^\s*(```|~~~)/;
const OURS = /^\s*(import\s|<\/?Tabs|<\/?TabItem)/;

let hits = 0;
for (const file of globSync('src/content/docs/**/*.mdx')) {
  const lines = readFileSync(file, 'utf8').split(/\r?\n/);
  let fence = false;
  // Frontmatter is YAML, not MDX — `{` and `<` are literal there.
  let inFrontmatter = lines[0]?.replace(/^﻿/, '') === '---';

  lines.forEach((line, i) => {
    if (inFrontmatter) {
      if (i > 0 && line.trim() === '---') inFrontmatter = false;
      return;
    }
    if (FENCE.test(line)) { fence = !fence; return; }
    if (fence || OURS.test(line)) return;

    // Inline code spans are safe in MDX — strip them before testing.
    const bare = line.replace(/`[^`]*`/g, '');
    if (/[{<]/.test(bare)) {
      hits++;
      console.log(`${file.replace(/\\/g, '/')}:${i + 1}: ${line.trim()}`);
    }
  });
}
console.log(hits ? `\n${hits} hazard(s).` : '\nNo hazards.');
