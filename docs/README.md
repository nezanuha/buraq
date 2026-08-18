# Buraq docs site

Astro + Starlight. Docs live at `src/content/docs/docs/`, served at `/docs/...`.

## Commands

```bash
npm run dev      # local dev server
npm run build    # production build
npm run preview  # preview the build
```

## Releasing a new major version (v2, v3, ...)

**Before editing docs for the next major**, freeze the current docs as an
archive — once you start editing in place, separating the two versions means
cherry-picking from git history page by page.

```bash
npm run snapshot-version -- v1
```

Then follow the printed instructions: uncomment one line in `src/versions.mjs`,
bump `currentVersion.label`, `npm run build`. Full explanation in the header
comment of `src/versions.mjs`.

## SEO / meta

- `node scripts/add-descriptions.mjs --write` — regenerate per-page meta descriptions
- `node scripts/make-og-image.mjs` — regenerate the social card at `public/og.png`
