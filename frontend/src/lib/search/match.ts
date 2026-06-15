export function matchesSearch(query: string, values: Array<unknown>): boolean {
  const normalizedQuery = normalizeSearchText(query);
  if (!normalizedQuery) {
    return true;
  }

  return values.some((value) => normalizeSearchText(flattenSearchValue(value)).includes(normalizedQuery));
}

function flattenSearchValue(value: unknown): string {
  if (value === null || value === undefined) {
    return '';
  }
  if (Array.isArray(value)) {
    return value.map(flattenSearchValue).join(' ');
  }
  if (typeof value === 'object') {
    return Object.values(value).map(flattenSearchValue).join(' ');
  }
  return String(value);
}

function normalizeSearchText(value: string) {
  return value.trim().toLowerCase();
}
