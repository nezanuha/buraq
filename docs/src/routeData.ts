import { defineRouteMiddleware } from '@astrojs/starlight/route-data';
import { getCollection } from 'astro:content';
import { archivedVersions, versionForId } from './versions.mjs';

/**
 * Starlight's sidebar is global, but each documentation version needs its own.
 *
 * astro.config registers the current sidebar plus one collapsed group per
 * archived version, so Starlight builds route data for all of them. This
 * middleware then narrows that per page:
 *
 *   /docs/v1/...  ->  only the v1 group
 *   /docs/...     ->  everything except archived groups
 *
 * Filtering the already-processed route data (rather than swapping in raw
 * config) keeps us in Starlight's own entry format, so links, current-page
 * highlighting, and collapse state all keep working.
 */

interface SidebarEntry {
  label?: string;
  href?: string;
  isCurrent?: boolean;
  entries?: SidebarEntry[];
}

interface StarlightRouteLike {
  entry: { id: string; data?: { title?: string } };
  sidebar: unknown;
  head: Array<{ tag: string; attrs?: Record<string, unknown>; content?: string }>;
}

const slugs: string[] = (archivedVersions as Array<{ slug: string }>).map((v) => v.slug);

/** Does this entry, or anything beneath it, link into /docs/<slug>/ ? */
function belongsTo(entry: SidebarEntry, slug: string): boolean {
  if (entry.href) return entry.href.replace(/\/$/, '').startsWith(`/docs/${slug}`);
  return entry.entries?.some((child) => belongsTo(child, slug)) ?? false;
}

const belongsToAnyArchived = (entry: SidebarEntry) => slugs.some((slug) => belongsTo(entry, slug));

/** Ids of every page in the CURRENT docs, built once and reused. */
let currentIds: Set<string> | undefined;
async function currentPageIds() {
  if (!currentIds) {
    const all = await getCollection('docs');
    currentIds = new Set(
      all.map((e) => e.id).filter((id) => !slugs.some((slug) => id.startsWith(`docs/${slug}/`)))
    );
  }
  return currentIds;
}

/** First real page URL inside a sidebar group, for linking the section crumb. */
function firstHref(entry: SidebarEntry): string | undefined {
  if (entry.href) return entry.href;
  for (const child of entry.entries ?? []) {
    const found = firstHref(child);
    if (found) return found;
  }
  return undefined;
}

function containsCurrent(entry: SidebarEntry): boolean {
  if (entry.isCurrent) return true;
  return entry.entries?.some(containsCurrent) ?? false;
}

/**
 * Emit BreadcrumbList structured data so results show
 * `buraqproject.com › Topics › Querying` instead of a bare URL.
 *
 * Section crumbs point at the group's first page rather than a synthetic path:
 * /docs, /docs/topics and /docs/topics/orm are not real pages, so linking them
 * would put 404s in the breadcrumb trail.
 */
function addBreadcrumbs(route: StarlightRouteLike, origin: string) {
  const url = origin + '/' + String(route.entry.id).replace(/\/index$/, '');
  const crumbs: Array<{ name: string; item?: string }> = [{ name: 'Buraq', item: origin }];

  const group = (route.sidebar as SidebarEntry[]).find(
    (entry) => !entry.href && containsCurrent(entry)
  );
  if (group?.label) {
    const href = firstHref(group);
    crumbs.push({ name: group.label, item: href ? origin + href : undefined });
  }

  crumbs.push({ name: route.entry.data?.title ?? '', item: url });

  route.head.push({
    tag: 'script',
    attrs: { type: 'application/ld+json' },
    content: JSON.stringify({
      '@context': 'https://schema.org',
      '@type': 'BreadcrumbList',
      itemListElement: crumbs.map((crumb, i) => ({
        '@type': 'ListItem',
        position: i + 1,
        name: crumb.name,
        ...(crumb.item ? { item: crumb.item } : {}),
      })),
    }),
  });
}

export const onRequest = defineRouteMiddleware(async (context) => {
  const route = context.locals.starlightRoute;
  if (!route) return;

  const origin = context.site ? String(context.site).replace(/\/$/, '') : '';
  if (origin && route.entry.id) addBreadcrumbs(route as StarlightRouteLike, origin);

  if (slugs.length === 0) return;

  const version = versionForId(route.entry.id) as { slug: string } | undefined;
  const sidebar = route.sidebar as SidebarEntry[];

  route.sidebar = (
    version
      ? sidebar.filter((entry) => belongsTo(entry, version.slug))
      : sidebar.filter((entry) => !belongsToAnyArchived(entry))
  ) as typeof route.sidebar;

  if (!version) return;

  // Point archived pages at their current equivalent so ranking signals
  // consolidate on the live docs instead of splitting across old versions.
  // Skipped when the page no longer exists in current docs — canonicalising to
  // a 404 is worse than self-canonicalising.
  const equivalentId = route.entry.id.replace(`docs/${version.slug}/`, 'docs/');
  if (!(await currentPageIds()).has(equivalentId)) return;

  const canonical = route.head.find(
    (tag) => tag.tag === 'link' && tag.attrs?.rel === 'canonical'
  );
  if (canonical?.attrs?.href) {
    canonical.attrs.href = String(canonical.attrs.href).replace(`/docs/${version.slug}/`, '/docs/');
  }
});
