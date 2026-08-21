import { readFileSync } from 'node:fs';
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import tailwindcss from '@tailwindcss/vite';
import sitemap from '@astrojs/sitemap';

import { lastmodFor } from './src/lastmod.mjs';
import sitemapPaths from './src/sitemap-paths.mjs';
import { currentSidebar } from './src/sidebar.mjs';
import { archivedVersions } from './src/versions.mjs';

const SITE = 'https://buraqproject.com';

/**
 * Current sidebar, plus one collapsed group per archived version. Route
 * middleware (src/routeData.ts) narrows this per page so each version shows
 * only its own nav. Archived sidebars are frozen at snapshot time by
 * `npm run snapshot-version`.
 */
const sidebar = [
  ...currentSidebar,
  ...archivedVersions.map((version) => ({
    label: version.label,
    collapsed: true,
    items: JSON.parse(
      readFileSync(new URL(`./src/versions/${version.slug}.sidebar.json`, import.meta.url), 'utf8')
    ),
  })),
];

export default defineConfig({
  site: SITE,
  vite: {
    plugins: [tailwindcss()],
  },
  trailingSlash: 'never',
  integrations: [
    /**
     * Declared before Starlight so this configuration is used rather than the
     * unconfigured sitemap Starlight would add on its own. The index and the
     * URL list were already correct; what was missing is <lastmod>, without
     * which every page looks equally stale to a crawler on every visit.
     *
     * changefreq and priority are deliberately absent: Google ignores both.
     */
    sitemap({
      serialize(item) {
        const lastmod = lastmodFor(item.url);
        return lastmod ? { ...item, lastmod } : item;
      },
    }),
    starlight({
      title: 'Buraq',
      description: 'The async Python framework you already know how to use',
      logo: {
        light: './src/assets/logo.svg',
        dark: './src/assets/logo.svg',
        replacesTitle: false,
      },
      social: [
        { icon: 'github', label: 'GitHub', href: 'https://github.com/nezanuha/buraq' },
      ],
      customCss: ['./src/styles/custom.css'],
        /**
         * Template snippets are fenced `html+jinja` (and one `html+django`) —
         * Pygments names carried over from the previous docs tooling. Shiki has
         * no grammar under those names, so every build warned and fell back to
         * plain text. `twig` is the bundled grammar that highlights HTML with
         * `{% %}` / `{{ }}` tags, which is exactly what these snippets are.
         */
        expressiveCode: {
          shiki: {
            langAlias: {
              'html+jinja': 'twig',
              'html+django': 'twig',
            },
          },
        },
      components: {
        Header: './src/components/Header.astro',
        Footer: './src/components/Footer.astro',
        Banner: './src/components/Banner.astro',
        PageTitle: './src/components/PageTitle.astro',
      },
      editLink: {
        baseUrl: 'https://github.com/nezanuha/buraq/edit/main/docs/',
      },
      lastUpdated: true,
      pagination: true,
      tableOfContents: { minHeadingLevel: 2, maxHeadingLevel: 3 },
      /**
       * Social card. Starlight already sets `twitter:card=summary_large_image`,
       * which promises an image — without og:image, shares render as a bare
       * text card. Regenerate with `node scripts/make-og-image.mjs`.
       */
      head: [
        { tag: 'meta', attrs: { property: 'og:image', content: `${SITE}/og.png` } },
        { tag: 'meta', attrs: { property: 'og:image:width', content: '1200' } },
        { tag: 'meta', attrs: { property: 'og:image:height', content: '630' } },
        {
          tag: 'meta',
          attrs: {
            property: 'og:image:alt',
            content: 'Buraq — the async Python framework you already know how to use',
          },
        },
        { tag: 'meta', attrs: { name: 'twitter:image', content: `${SITE}/og.png` } },
      ],
      routeMiddleware: './src/routeData.ts',
      sidebar,
    }),
    // After the sitemap integration: build:done hooks run in declaration order.
    sitemapPaths({ site: SITE }),
  ],
});
