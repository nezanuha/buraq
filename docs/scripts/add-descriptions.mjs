/**
 * Give every docs page its own `description:` frontmatter.
 *
 * Without this every page inherits the site-wide description, so all 86 search
 * results share one snippet and Google rewrites them with text of its choosing.
 *
 * The description is derived from each page's own first prose paragraph — no
 * invented copy. Headings, code fences, asides, tables, lists, JSX and imports
 * are skipped so the snippet is real sentences.
 *
 * Run with --write to apply; omit for a dry run.
 */
import { readFileSync, writeFileSync, globSync } from 'node:fs';
import { sep } from 'node:path';

const WRITE = process.argv.includes('--write');
const MAX = 160;
const rel = (file) => file.split(sep).join('/').replace('src/content/docs/docs/', '');

/** Strip inline markdown so the snippet reads as plain prose. */
function clean(text) {
  return text
    .replace(/!\[[^\]]*\]\([^)]*\)/g, '')      // images
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')   // links -> their text
    .replace(/`([^`]+)`/g, '$1')               // inline code
    .replace(/\*\*([^*]+)\*\*/g, '$1')         // bold
    .replace(/(^|\s)\*([^*]+)\*/g, '$1$2')     // italics
    .replace(/<[^>]+>/g, '')                   // stray html / jsx
    .replace(/\s+/g, ' ')
    .trim();
}

/** Every prose paragraph in the body, in order. */
function paragraphs(body) {
  const out = [];
  let buf = [];
  let fence = false;
  const flush = () => {
    if (buf.length) out.push(clean(buf.join(' ')));
    buf = [];
  };

  for (const line of body.split(/\r?\n/)) {
    const t = line.trim();

    if (t.startsWith('```') || t.startsWith('~~~')) {
      fence = !fence;
      flush();
      continue;
    }
    if (fence) continue;

    // Blank lines and any non-prose structure end the current paragraph.
    if (!t || /^#{1,6}\s/.test(t) || /^(import\s|:::|<|\||---|===)/.test(t) || /^([-*+]\s|\d+\.\s)/.test(t)) {
      flush();
      continue;
    }

    buf.push(t);
  }

  flush();
  return out.filter(Boolean);
}

/**
 * Pick the best paragraph for a meta description.
 *
 * A paragraph ending in ':' is a lead-in to a code block ("Usage:", "Or from
 * environment:") — useless as a snippet, so prefer a real sentence further down
 * the page before falling back to it.
 */
function bestParagraph(body) {
  const found = paragraphs(body);
  // Document order wins: a page's opening line is almost always the best
  // summary, even when short. Only skip it if it isn't a usable sentence.
  const usable = (p) => p.length >= 40 && !p.endsWith(':');
  return found.find(usable) ?? found.find((p) => p.length >= 40) ?? found[0] ?? '';
}

function truncate(text) {
  if (text.length <= MAX) return text;
  const cut = text.slice(0, MAX);
  const at = cut.lastIndexOf(' ');
  return (at > 60 ? cut.slice(0, at) : cut).replace(/[,;:.\s]+$/, '') + '…';
}

let done = 0;
const skipped = [];

for (const file of globSync('src/content/docs/docs/**/*.{md,mdx}')) {
  const src = readFileSync(file, 'utf8');
  if (/^description:/m.test(src)) continue;

  const eol = src.includes('\r\n') ? '\r\n' : '\n';
  const lines = src.split(/\r?\n/);
  if (lines[0].replace(/^﻿/, '') !== '---') {
    skipped.push([file, 'no frontmatter']);
    continue;
  }

  const close = lines.findIndex((l, i) => i > 0 && l.trim() === '---');
  if (close === -1) {
    skipped.push([file, 'unterminated frontmatter']);
    continue;
  }

  const desc = truncate(bestParagraph(lines.slice(close + 1).join('\n')));
  if (desc.length < 40) {
    skipped.push([file, `too short (${desc.length} chars): "${desc}"`]);
    continue;
  }

  if (WRITE) {
    lines.splice(close, 0, `description: ${JSON.stringify(desc)}`);
    writeFileSync(file, lines.join(eol), 'utf8');
  } else {
    console.log(`${rel(file)}\n  ${desc}\n`);
  }
  done++;
}

if (skipped.length) {
  console.log('NEEDS MANUAL ATTENTION:');
  for (const [file, why] of skipped) console.log(`  ${rel(file)} — ${why}`);
}
console.log(`\n${WRITE ? 'Wrote' : 'Would write'} ${done} descriptions; ${skipped.length} skipped.`);
