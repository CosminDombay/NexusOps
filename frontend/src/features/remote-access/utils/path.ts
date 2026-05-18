export function parentPath(path: string): string {
  if (path === '/') {
    return '/';
  }
  const parts = path.split('/').filter(Boolean);
  parts.pop();
  return parts.length ? `/${parts.join('/')}` : '/';
}

export function breadcrumbs(path: string): Array<{ label: string; path: string }> {
  const parts = path.split('/').filter(Boolean);
  const items = [{ label: '/', path: '/' }];
  let next = '';
  for (const part of parts) {
    next += `/${part}`;
    items.push({ label: part, path: next });
  }
  return items;
}

export function formatRemoteBytes(value: number): string {
  const units = ['B', 'KB', 'MB', 'GB'];
  let next = value;
  let index = 0;
  while (next >= 1024 && index < units.length - 1) {
    next /= 1024;
    index += 1;
  }
  return `${next.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}
