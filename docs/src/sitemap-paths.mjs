/**
 * Publish the sitemap at conventional paths.
 *
 * @astrojs/sitemap hardcodes `${filenameBase}-index.xml` and `${filenameBase}-N.xml`,
 * so the entry point lands at /sitemap-index.xml. Crawlers and audit tools probe
 * /sitemap.xml, and `sitemap-0.xml` says nothing about what is inside it. This
 * moves them:
 *
 *     /sitemap.xml        the index, and the only URL worth submitting
 *     /sitemap/docs.xml   the documentation URLs
 *
 * Splitting by section earns its keep once there is a second content type; the
 * naming is adopted now so the submitted URL never has to change.
 *
 * Declare this after the sitemap integration — astro:build:done hooks run in the
 * order their integrations appear.
 */
import { mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const SECTION = 'docs';

export default function sitemapPaths({ site }) {
  return {
    name: 'buraq:sitemap-paths',
    hooks: {
      'astro:build:done': ({ dir, logger }) => {
        const outDir = fileURLToPath(dir);
        const generated = readdirSync(outDir)
          .filter((name) => /^sitemap-\d+\.xml$/.test(name))
          .sort();

        if (!generated.length) {
          logger.warn('no sitemap files found; leaving paths alone');
          return;
        }

        mkdirSync(path.join(outDir, 'sitemap'), { recursive: true });

        const moved = generated.map((name, index) => {
          // sitemap-0 is the section itself; any further files are overflow.
          const target = index === 0 ? `${SECTION}.xml` : `${SECTION}-${index}.xml`;
          writeFileSync(
            path.join(outDir, 'sitemap', target),
            readFileSync(path.join(outDir, name))
          );
          rmSync(path.join(outDir, name));
          return `sitemap/${target}`;
        });

        // Rebuilt rather than rewritten, so the index cannot keep naming a file
        // that no longer exists.
        const base = new URL(site).origin;
        const entries = moved
          .map((file) => `<sitemap><loc>${base}/${file}</loc></sitemap>`)
          .join('');
        writeFileSync(
          path.join(outDir, 'sitemap.xml'),
          '<?xml version="1.0" encoding="UTF-8"?>'
            + '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            + entries
            + '</sitemapindex>\n'
        );
        rmSync(path.join(outDir, 'sitemap-index.xml'), { force: true });

        // Starlight puts <link rel="sitemap" href="/sitemap-index.xml"> in every
        // page head. Moving the file without this leaves 88 pages pointing at
        // something that is no longer there.
        let patched = 0;
        const relink = (dir) => {
          for (const entry of readdirSync(dir, { withFileTypes: true })) {
            const full = path.join(dir, entry.name);
            if (entry.isDirectory()) {
              relink(full);
            } else if (entry.name.endsWith('.html')) {
              const html = readFileSync(full, 'utf8');
              if (!html.includes('/sitemap-index.xml')) continue;
              writeFileSync(full, html.split('/sitemap-index.xml').join('/sitemap.xml'));
              patched += 1;
            }
          }
        };
        relink(outDir);

        logger.info(`sitemap.xml -> ${moved.join(', ')} (relinked ${patched} pages)`);
      },
    },
  };
}
