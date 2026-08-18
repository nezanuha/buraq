/**
 * Documentation versions — single source of truth.
 *
 * URL scheme:
 *   /docs/tutorial/models        current version (always; never carries a version segment)
 *   /docs/v1/tutorial/models     archived version
 *
 * An archived version is only created once it has been SUPERSEDED. While v1 is
 * the current release there is deliberately no /docs/v1/ — that would be a
 * duplicate of /docs/ and split ranking signals between two identical URLs.
 *
 * To archive the current docs before starting work on the next major:
 *
 *   npm run snapshot-version -- v1
 *
 * That copies the live docs to src/content/docs/docs/v1/, freezes the sidebar to
 * src/versions/v1.sidebar.json, and prints the entry to paste into
 * `archivedVersions` below.
 */

/** Label for the live docs served at /docs/... — update when a new major ships. */
export const currentVersion = {
  label: 'v1.x',
};

/**
 * Archived versions, newest first. Each entry needs a matching content
 * directory at src/content/docs/docs/<slug>/ and a frozen sidebar at
 * src/versions/<slug>.sidebar.json.
 *
 * Empty while v1 is current — see the note above.
 */
export const archivedVersions = [
  // { slug: 'v1', label: 'v1.x' },
];

/** Every selectable version, current first. Used by the version picker. */
export function allVersions() {
  return [
    { slug: null, label: currentVersion.label, current: true, href: '/docs' },
    ...archivedVersions.map((v) => ({ ...v, current: false, href: `/docs/${v.slug}` })),
  ];
}

/**
 * Given a page id from the docs collection (e.g. `docs/v1/tutorial/models`),
 * return the archived version it belongs to, or undefined for current docs.
 */
export function versionForId(id) {
  const match = /^docs\/([^/]+)\//.exec(id ?? '');
  if (!match) return undefined;
  return archivedVersions.find((v) => v.slug === match[1]);
}

/** Map an archived page id back to its equivalent URL in the current docs. */
export function currentEquivalentOf(id, slug) {
  return '/' + String(id).replace(new RegExp(`^docs/${slug}/`), 'docs/');
}
