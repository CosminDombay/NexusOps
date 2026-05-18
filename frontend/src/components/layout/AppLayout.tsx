import { NavLink, Outlet } from 'react-router-dom';

import logoImage from '../../assets/logo.png';
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
      { to: '/settings/users', label: 'Users & RBAC', minimumRole: 'admin' },
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
    <div className="min-h-screen bg-zinc-950 text-zinc-950">
      <aside className="border-b border-cyan-400/15 bg-zinc-950 text-zinc-100 lg:fixed lg:inset-y-0 lg:left-0 lg:w-64 lg:border-b-0 lg:border-r">
        <div className="border-b border-cyan-400/15 px-5 py-4">
          <div
            aria-label="NexusOps"
            className="h-14 w-44 bg-center bg-no-repeat"
            role="img"
            style={{
              backgroundImage: `url(${logoImage})`,
              backgroundSize: '250%',
            }}
          />
          <p className="mt-2 text-sm text-zinc-400">Infrastructure orchestration</p>
        </div>
        <nav className="flex gap-3 overflow-x-auto p-3 lg:flex-col lg:overflow-visible">
          {visibleNavGroups.map((group) => (
            <div key={group.label} className="flex shrink-0 gap-1 lg:flex-col">
              <div className="hidden px-3 pb-1 pt-2 text-xs font-semibold uppercase tracking-normal text-cyan-300/60 lg:block">
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
                      isActive
                        ? 'bg-cyan-400 text-zinc-950 shadow-sm shadow-cyan-950/30'
                        : 'text-zinc-300 hover:bg-white/5 hover:text-white',
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
      <main className="min-h-screen bg-slate-950 p-4 text-slate-100 sm:p-6 lg:ml-64 lg:p-8">
        <header className="mb-6 flex items-center justify-end gap-3 border-b border-slate-700/70 pb-4">
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
