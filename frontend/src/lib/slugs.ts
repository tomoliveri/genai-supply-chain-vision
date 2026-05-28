/**
 * Convert a location name like "Port of Beira, Mozambique" to a URL-safe slug
 * like "beira-mozambique".
 *
 * The slug is deterministic — any code that slugifies the same location_name
 * will produce the same slug, so we can match without maintaining a separate
 * mapping file.
 */
export function slugifyLocationName(name: string): string {
  return name
    .toLowerCase()
    // Remove "Port of " and "Port " prefixes
    .replace(/^port of /i, '')
    .replace(/^port /i, '')
    // Remove parentheticals like "(JNPT)" or "(Yantian)"
    .replace(/\([^)]*\)/g, '')
    // Replace commas, underscores, and whitespace with hyphens
    .replace(/[,\s_]+/g, '-')
    // Remove any remaining non-alphanumeric characters except hyphens
    .replace(/[^a-z0-9-]/g, '')
    // Collapse multiple hyphens
    .replace(/-{2,}/g, '-')
    // Trim hyphens from edges
    .replace(/^-+|-+$/g, '');
}
