import { NavLink, Outlet } from 'react-router-dom';

const navGroups = [
  {
    label: 'Core',
    items: [
      { to: '/', label: 'Inventory' },
      { to: '/infrastructure', label: 'Infrastructure' },
      { to: '/provisioning', label: 'Provisioning' },
      { to: '/infrastructure/credentials', label: 'Credentials' },
    ],
  },
  {
    label: 'Operations/Orchestration',
    items: [
      { to: '/jobs', label: 'Jobs' },
      { to: '/workflows', label: 'Workflows' },
      { to: '/automations', label: 'Automations' },
      { to: '/packages', label: 'Packages' },
      { to: '/profiles', label: 'Profiles' },
      { to: '/deployments', label: 'Deployments' },
      { to: '/identity', label: 'Identity' },
      { to: '/monitoring', label: 'Monitoring' },
      { to: '/settings/integrations', label: 'Integrations' },
    ],
  },
];

export function AppLayout() {
  return (
    <div className="min-h-screen bg-zinc-50 text-zinc-950">
      <aside className="border-b border-zinc-200 bg-white lg:fixed lg:inset-y-0 lg:left-0 lg:w-64 lg:border-b-0 lg:border-r">
        <div className="border-b border-zinc-200 px-5 py-4">
          <h1 className="text-lg font-semibold">NexusOps</h1>
          <p className="text-sm text-zinc-500">Infrastructure orchestration</p>
        </div>
        <nav className="flex gap-3 overflow-x-auto p-3 lg:flex-col lg:overflow-visible">
          {navGroups.map((group) => (
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
        <Outlet />
      </main>
    </div>
  );
}
