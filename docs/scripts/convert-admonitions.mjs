/**
 * Convert leftover MkDocs admonitions to Starlight asides.
 *
 *   !!! warning "SECRET_KEY in production"
 *       Never commit your key.
 *
 *       Use an env var instead.
 *
 * becomes
 *
 *   :::caution[SECRET_KEY in production]
 *   Never commit your key.
 *
 *   Use an env var instead.
 *   :::
 *
 * MkDocs marks admonition body by 4-space indentation; Starlight asides are not
 * indented, so every body line is dedented by 4. Blank lines inside the block are
 * preserved (paragraph breaks); trailing blank lines are dropped.
 *
 * Run with --write to apply; omit for a dry run.
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { globSync } from 'node:fs';

const WRITE = process.argv.includes('--write');

// MkDocs type -> Starlight aside type. Starlight supports note/tip/caution/danger.
const TYPE_MAP = {
  note: 'note', info: 'note', abstract: 'note', summary: 'note', quote: 'note',
  example: 'note', question: 'note',
  tip: 'tip', hint: 'tip', success: 'tip', check: 'tip', done: 'tip',
  warning: 'caution', caution: 'caution', attention: 'caution',
  danger: 'danger', error: 'danger', failure: 'danger', bug: 'danger',
};

const OPEN = /^!!!\s+([a-z-]+)(?:\s+"([^"]*)")?\s*$/;

export function convert(src) {
  // These files are CRLF; preserve whatever the file already uses so the diff
  // stays to the lines actually changed.
  const eol = src.includes('\r\n') ? '\r\n' : '\n';
  const lines = src.split(/\r?\n/);
  const out = [];
  let converted = 0;

  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].match(OPEN);
    if (!m) { out.push(lines[i]); continue; }

    const [, rawType, title] = m;
    const type = TYPE_MAP[rawType.toLowerCase()];
    if (!type) { out.push(lines[i]); continue; } // unknown type: leave untouched

    // Collect the indented body (blank lines may appear between paragraphs).
    const body = [];
    let j = i + 1;
    while (j < lines.length) {
      const line = lines[j];
      if (line.trim() === '') { body.push(''); j++; continue; }
      if (/^ {4}/.test(line)) { body.push(line.slice(4)); j++; continue; }
      break; // non-indented, non-blank => block ended
    }

    // Drop trailing blanks that belong after the block, not inside it.
    while (body.length && body[body.length - 1] === '') body.pop();
    if (!body.length) { out.push(lines[i]); continue; } // no body: not an admonition

    out.push(title ? `:::${type}[${title}]` : `:::${type}`);
    out.push(...body);
    out.push(':::');

    // The body scan swallows the blank line that separated the block from what
    // follows. Put it back, so `:::` never sits flush against the next element
    // (a bare `---` after a line can otherwise read as a setext heading).
    if (j < lines.length && lines[j].trim() !== '') out.push('');

    converted++;
    i = j - 1; // resume after the consumed body
  }

  return { text: out.join(eol), converted };
}

const files = globSync('src/content/docs/**/*.md');
let totalFiles = 0, totalBlocks = 0;

for (const file of files) {
  const src = readFileSync(file, 'utf8');
  if (!/^!!!\s/m.test(src)) continue;

  const { text, converted } = convert(src);
  if (!converted || text === src) continue;

  totalFiles++; totalBlocks += converted;
  if (WRITE) writeFileSync(file, text, 'utf8');
  console.log(`${WRITE ? 'wrote' : 'would convert'}  ${converted}  ${file}`);
}

console.log(`\n${WRITE ? 'Converted' : 'Would convert'} ${totalBlocks} admonitions across ${totalFiles} files.`);
