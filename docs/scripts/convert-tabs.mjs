/**
 * Convert leftover MkDocs content tabs to Starlight <Tabs>/<TabItem>.
 *
 *   === "uv (recommended)"
 *
 *       ```bash
 *       uv add buraq
 *       ```
 *
 *   === "pip"
 *       ...
 *
 * becomes
 *
 *   <Tabs>
 *   <TabItem label="uv (recommended)">
 *
 *   ```bash
 *   uv add buraq
 *   ```
 *
 *   </TabItem>
 *   ...
 *   </Tabs>
 *
 * Notes:
 *  - Body is dedented to column 0. Leaving MkDocs' 4-space indent would make MDX
 *    treat the content as an indented code block.
 *  - Blank lines around the children are required for MDX to parse them as
 *    markdown rather than raw text.
 *  - Components only work in .mdx, so converted files are renamed and given the
 *    Starlight components import after their frontmatter.
 *
 * Run with --write to apply; omit for a dry run.
 */
import { readFileSync, writeFileSync, renameSync, globSync } from 'node:fs';

const WRITE = process.argv.includes('--write');
const IMPORT = "import { Tabs, TabItem } from '@astrojs/starlight/components';";
const OPEN = /^===\s+"([^"]*)"\s*$/;

export function convert(src) {
  const eol = src.includes('\r\n') ? '\r\n' : '\n';
  const lines = src.split(/\r?\n/);
  const out = [];
  let groups = 0;

  for (let i = 0; i < lines.length; i++) {
    if (!OPEN.test(lines[i])) { out.push(lines[i]); continue; }

    // Collect every consecutive `=== "label"` block into one <Tabs> group.
    const tabs = [];
    while (i < lines.length) {
      const m = lines[i].match(OPEN);
      if (!m) break;

      const body = [];
      let j = i + 1;
      while (j < lines.length) {
        const line = lines[j];
        if (line.trim() === '') { body.push(''); j++; continue; }
        if (/^ {4}/.test(line)) { body.push(line.slice(4)); j++; continue; }
        break;
      }
      while (body.length && body[body.length - 1] === '') body.pop();
      while (body.length && body[0] === '') body.shift();

      tabs.push({ label: m[1], body });
      i = j;
    }
    i--; // step back; the outer loop will i++

    if (!tabs.length) { out.push(lines[i + 1]); continue; }

    out.push('<Tabs>');
    for (const t of tabs) {
      out.push(`<TabItem label="${t.label}">`);
      out.push('');            // blank line => children parsed as markdown
      out.push(...t.body);
      out.push('');
      out.push('</TabItem>');
    }
    out.push('</Tabs>');

    const next = lines[i + 1];
    if (next !== undefined && next.trim() !== '') out.push('');

    groups++;
  }

  return { text: out.join(eol), groups };
}

/** Insert the components import directly after the frontmatter block. */
function addImport(text) {
  if (text.includes(IMPORT)) return text;
  const eol = text.includes('\r\n') ? '\r\n' : '\n';
  const lines = text.split(/\r?\n/);
  if (lines[0].replace(/^﻿/, '') !== '---') return `${IMPORT}${eol}${eol}${text}`;

  let close = -1;
  for (let i = 1; i < lines.length; i++) if (lines[i] === '---') { close = i; break; }
  if (close === -1) return `${IMPORT}${eol}${eol}${text}`;

  lines.splice(close + 1, 0, '', IMPORT);
  return lines.join(eol);
}

let files = 0, totalGroups = 0;

for (const file of globSync('src/content/docs/**/*.md')) {
  const src = readFileSync(file, 'utf8');
  if (!/^===\s+"/m.test(src)) continue;

  const { text, groups } = convert(src);
  if (!groups) continue;

  const final = addImport(text);
  const target = file.replace(/\.md$/, '.mdx');

  files++; totalGroups += groups;
  if (WRITE) {
    writeFileSync(file, final, 'utf8');
    renameSync(file, target);
  }
  console.log(`${WRITE ? 'wrote' : 'would convert'}  ${groups} group(s)  ${file} -> ${target}`);
}

console.log(`\n${WRITE ? 'Converted' : 'Would convert'} ${totalGroups} tab groups across ${files} files.`);
