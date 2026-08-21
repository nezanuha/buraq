/**
 * The raw Markdown behind every documentation page, at the page's own URL plus
 * `.md`.
 *
 * Serves the "Markdown" link and the copy action, and gives an assistant
 * something to read that is not wrapped in the site's HTML.
 */
import type { APIRoute, GetStaticPaths } from 'astro';
import { getCollection } from 'astro:content';

export const getStaticPaths: GetStaticPaths = async () => {
  const entries = await getCollection('docs');
  return entries.map((entry) => ({
    params: { slug: entry.id },
    props: { title: entry.data.title, body: entry.body ?? '' },
  }));
};

/**
 * MDX pages carry component imports and JSX that mean nothing outside the site.
 * Tab labels do carry meaning, so they survive as bold lines rather than leaving
 * with their tags.
 */
function toPlainMarkdown(body: string): string {
  return body
    .replace(/^import\s.+?;?\s*$/gm, '')
    .replace(/<TabItem\s+label=["']([^"']+)["'][^>]*>/g, '**$1**')
    .replace(/<\/?Tabs[^>]*>/g, '')
    .replace(/<\/TabItem>/g, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

export const GET: APIRoute = ({ props }) => {
  const { title, body } = props as { title: string; body: string };
  // Frontmatter is metadata for the site, not for the reader; the title is the
  // one part worth keeping, as a heading.
  const markdown = `# ${title}\n\n${toPlainMarkdown(body)}\n`;
  return new Response(markdown, {
    headers: { 'content-type': 'text/markdown; charset=utf-8' },
  });
};
