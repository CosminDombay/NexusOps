import { NavLink, Outlet } from 'react-router-dom';

import { useAuth } from '../../features/auth/hooks/useAuth';
import type { UserRole } from '../../features/auth/types/auth';

const roleRank: Record<UserRole, number> = {
  viewer: 1,
  operator: 2,
  admin: 3,
};

const navGroups = [
  {
    label: 'Core',
    items: [
      { to: '/', label: 'Inventory', minimumRole: 'viewer' },
      { to: '/infrastructure', label: 'Infrastructure', minimumRole: 'viewer' },
      { to: '/provisioning', label: 'Provisioning', minimumRole: 'operator' },
      { to: '/infrastructure/credentials', label: 'Credentials', minimumRole: 'admin' },
    ],
  },
  {
    label: 'Operations/Orchestration',
    items: [
      { to: '/jobs', label: 'Jobs', minimumRole: 'operator' },
      { to: '/workflows', label: 'Workflows', minimumRole: 'viewer' },
      { to: '/automations', label: 'Automations', minimumRole: 'operator' },
      { to: '/packages', label: 'Packages', minimumRole: 'operator' },
      { to: '/profiles', label: 'Profiles', minimumRole: 'operator' },
      { to: '/deployments', label: 'Deployments', minimumRole: 'operator' },
      { to: '/identity', label: 'Identity', minimumRole: 'admin' },
      { to: '/monitoring', label: 'Monitoring', minimumRole: 'viewer' },
      { to: '/settings/integrations', label: 'Integrations', minimumRole: 'admin' },
    ],
  },
] satisfies Array<{
  label: string;
  items: Array<{ to: string; label: string; minimumRole: UserRole }>;
}>;

export function AppLayout() {
  const { user, logout } = useAuth();

  const visibleNavGroups = navGroups
    .map((group) => ({
      ...group,
      items: group.items.filter(
        (item) => user && roleRank[user.role] >= roleRank[item.minimumRole],
      ),
    }))
    .filter((group) => group.items.length > 0);

  return (
    <div className="min-h-screen bg-zinc-50 text-zinc-950">
      <aside className="border-b border-zinc-200 bg-white lg:fixed lg:inset-y-0 lg:left-0 lg:w-64 lg:border-b-0 lg:border-r">
        <div className="border-b border-zinc-200 px-5 py-4">
          <h1 className="text-lg font-semibold">NexusOps</h1>
          <p className="text-sm text-zinc-500">Infrastructure orchestration</p>
        </div>
        <nav className="flex gap-3 overflow-x-auto p-3 lg:flex-col lg:overflow-visible">
          {visibleNavGroups.map((group) => (
            <div key={group.label} className="flex shrink-0 gap-1 lg:flex-col">
              <div className="hidden px-3 pb-1 pt-2 text-xs font-semibold uppercase tracking-normal text-zinc-400 lg:block">
                {group.label}
              </div>
              {group.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end
                  className={({ isActive }) =>
                    [
                      'whitespace-nowrap rounded-md px-3 py-2 text-sm font-medium',
                      isActive ? 'bg-zinc-900 text-white' : 'text-zinc-600 hover:bg-zinc-100',
                    ].join(' ')
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
      </aside>
      <main className="min-h-screen p-4 sm:p-6 lg:ml-64 lg:p-8">
        <header className="mb-6 flex items-center justify-end gap-3 border-b border-zinc-200 pb-4">
          <div className="text-right">
            <p className="text-sm font-semibold text-zinc-900">{user?.username}</p>
            <p className="text-xs uppercase tracking-normal text-zinc-500">{user?.role}</p>
          </div>
          <button
            className="rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100"
            type="button"
            onClick={() => void logout()}
          >
            Logout
          </button>
        </header>
        <Outlet />
      </main>
    </div>
  );
}
