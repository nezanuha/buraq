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
      /**
       * A wordmark lockup: the dual-bolt mark beside "Buraq".
       *
       * Pure vector, no embedded raster. The mark was contour-traced from
       * Buraq-dual-3.png and the word is real Onest 700 outlines pulled with
       * fontTools, so nothing depends on a font being present at render time.
       *
       * Two files, because one colour cannot serve both grounds. The mark's own
       * dark green #0b4131 measures 11.57:1 on the light page and 1.70:1 on the
       * dark one, where it is unreadable; the dark file uses the mark's mint
       * #79c9a2 at 10.01:1. That single value is the only difference between them.
       *
       * replacesTitle, because the lockup already contains the word. Left false,
       * the header would read "Buraq Buraq".
       */
      logo: {
        light: './src/assets/logo-light.svg',
        dark: './src/assets/logo-dark.svg',
        replacesTitle: true,
      },
      // The mark alone. A wide lockup makes an unreadable favicon.
      favicon: '/favicon.png',
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
          /**
           * One theme per site theme: the block is light on the light page.
           *
           * Tokyo Night is the blue-black of the bundled themes and its #7aa2f7
           * sits beside our #818cf8, so the dark window belongs to this site
           * rather than to a theme author.
           *
           * GitHub Light is the light half, on contrast range rather than on
           * saturation. Tokyo Night's tokens span 7.4-12.2:1 against their
           * ground -- keywords strong, comments faint, a real hierarchy.
           * Vitesse Light, tried here, normalises almost every token to ~5:1;
           * matching its saturation to the dark theme made it duller, not
           * calmer, because uniform contrast is what reads as flat. GitHub
           * Light spans 5.0-13.4:1, which is the shape that matters.
           *
           * Its saturation is high, and on the beige ground this block used to
           * have, the reds and oranges clashed. The ground is neutral now (see
           * --bq-code-bg), which is what those colours were drawn for.
           *
           * The home page's hero windows are a separate thing and stay dark in
           * both themes; they use --bq-window-bg, not these tokens.
           */
          themes: ['tokyo-night', 'github-light'],

          /**
           * The block ground follows the page, not the theme. Left alone, a
           * snippet is a rectangle in the theme author's background colour
           * pasted onto ours — which is what made the old dark blocks read as
           * grey (#18181b zinc) on a blue-black page.
           */
          styleOverrides: {
            codeBackground: 'var(--bq-code-bg)',
            borderColor: 'var(--bq-code-border)',
            /* Supplying custom themes turns off Starlight's own EC UI colours,
               and its corner radius goes with them — the frames came back
               square against every other rounded surface on the page. */
            borderRadius: 'var(--bq-radius)',
            frames: {
              /* Expressive Code draws its own drop shadow on .frame, which is
                 why removing the one on `pre` changed nothing visible. The
                 border defines the block; the shadow only smudged its edge. */
              frameBoxShadowCssValue: 'none',

              /* The active-tab indicator, pinned to one convention.
                 Each theme brings its own: Tokyo Night marks the tab along the
                 bottom edge, GitHub Light along the top in orange (#f9826c),
                 which is VS Code's Light+ convention. Left alone, the marker
                 jumped from under the filename to above it when the theme
                 changed. Bottom in both, in our accent rather than either
                 theme author's colour. */
              editorActiveTabIndicatorTopColor: 'transparent',
              /* Dimmed and hairline-thin. The tab already reads as active from
                 its own background; this only confirms it, so a solid 2px bar
                 in the full accent was doing a job that was already done. */
              editorActiveTabIndicatorBottomColor:
                'color-mix(in srgb, var(--sl-color-accent) 55%, transparent)',
              editorActiveTabIndicatorHeight: '1px',

              editorTabBarBackground: 'var(--bq-code-chrome)',
              editorActiveTabBackground: 'var(--bq-code-bg)',
              terminalBackground: 'var(--bq-code-bg)',
              terminalTitlebarBackground: 'var(--bq-code-chrome)',
            },
          },

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
