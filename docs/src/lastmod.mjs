/**
 * Last-modified dates for sitemap entries, taken from git history.
 *
 * A sitemap without <lastmod> tells a crawler nothing about what has changed,
 * so every page looks equally stale on every visit. The commit date of the file
 * behind a page is the honest answer, and it costs one `git log` for the set.
 *
 * Falls back to no dates at all when git is unavailable or the checkout has no
 * history — a shallow CI clone, or a tarball. A sitemap without lastmod is
 * valid; a sitemap with invented dates is not.
 */
import { execFileSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const CONTENT_DIR = fileURLToPath(new URL('./content/docs/', import.meta.url));
const REPO_ROOT = fileURLToPath(new URL('../../', import.meta.url));

/** Most recent commit date per repository path. */
function commitDates() {
  const dates = new Map();
  let output;
  try {
    output = execFileSync(
      'git',
      ['log', '--pretty=format:%cI', '--name-only', '--no-merges'],
      { cwd: REPO_ROOT, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 }
    );
  } catch {
    return dates;
  }

  let commitDate = null;
  for (const line of output.split('\n')) {
    const value = line.trim();
    if (!value) continue;
    if (/^\d{4}-\d{2}-\d{2}T/.test(value)) {
      commitDate = value;
    } else if (!dates.has(value)) {
      // Commits are newest first, so the first sighting is the latest change.
      dates.set(value, commitDate);
    }
  }
  return dates;
}

const DATES = commitDates();

const PAGES_DIR = fileURLToPath(new URL('./pages/', import.meta.url));

/** The source file a URL pathname was built from, if there is one. */
function sourceFor(pathname) {
  const slug = pathname.replace(/^\/|\/$/g, '');
  const candidates = slug
    ? [
        CONTENT_DIR + `${slug}.md`,
        CONTENT_DIR + `${slug}.mdx`,
        CONTENT_DIR + `${slug}/index.md`,
        CONTENT_DIR + `${slug}/index.mdx`,
      ]
    // The home page is a route, not content.
    : [PAGES_DIR + 'index.astro', CONTENT_DIR + 'index.md', CONTENT_DIR + 'index.mdx'];

  for (const absolute of candidates) {
    if (existsSync(absolute)) {
      // Windows gives back separators git never uses.
      return absolute.slice(REPO_ROOT.length).split(String.fromCharCode(92)).join('/');
    }
  }
  return null;
}

export function lastmodFor(url) {
  let pathname;
  try {
    pathname = new URL(url).pathname;
  } catch {
    return undefined;
  }
  const source = sourceFor(pathname);
  return source ? DATES.get(source) : undefined;
}

export const hasHistory = DATES.size > 0;
