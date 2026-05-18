/* eslint-disable react-refresh/only-export-components */
import { lazy, Suspense, type ReactNode } from 'react';
import { createBrowserRouter } from 'react-router-dom';

import { AppLayout } from '../components/layout/AppLayout';
import { AdminRoute, AuthenticatedRoute, OperatorRoute } from '../features/auth/components/RequireRole';

const AccessDeniedPage = lazy(() => import('../features/auth/pages/AccessDeniedPage').then((module) => ({ default: module.AccessDeniedPage })));
const AutomationsPage = lazy(() => import('../features/automations/pages/AutomationsPage').then((module) => ({ default: module.AutomationsPage })));
const CredentialsPage = lazy(() => import('../features/credentials/CredentialsPage').then((module) => ({ default: module.CredentialsPage })));
const DeploymentsPage = lazy(() => import('../features/deployments/DeploymentsPage').then((module) => ({ default: module.DeploymentsPage })));
const HostDetailPage = lazy(() => import('../features/inventory/pages/HostDetailPage').then((module) => ({ default: module.HostDetailPage })));
const HostToolsPage = lazy(() => import('../features/remote-access/pages/HostToolsPage').then((module) => ({ default: module.HostToolsPage })));
const IdentityPage = lazy(() => import('../features/identity/IdentityPage').then((module) => ({ default: module.IdentityPage })));
const InfrastructureNodeDetailPage = lazy(() => import('../features/proxmox/pages/InfrastructureNodeDetailPage').then((module) => ({ default: module.InfrastructureNodeDetailPage })));
const InfrastructurePage = lazy(() => import('../features/proxmox/pages/InfrastructurePage').then((module) => ({ default: module.InfrastructurePage })));
const IntegrationsPage = lazy(() => import('../features/settings/IntegrationsPage').then((module) => ({ default: module.IntegrationsPage })));
const InventoryPage = lazy(() => import('../features/inventory/InventoryPage').then((module) => ({ default: module.InventoryPage })));
const JobsPage = lazy(() => import('../features/jobs/JobsPage').then((module) => ({ default: module.JobsPage })));
const LoginPage = lazy(() => import('../features/auth/pages/LoginPage').then((module) => ({ default: module.LoginPage })));
const MonitoringPage = lazy(() => import('../features/monitoring/MonitoringPage').then((module) => ({ default: module.MonitoringPage })));
const PackagesPage = lazy(() => import('../features/packages/PackagesPage').then((module) => ({ default: module.PackagesPage })));
const ProfilesPage = lazy(() => import('../features/profiles/ProfilesPage').then((module) => ({ default: module.ProfilesPage })));
const ProvisioningPage = lazy(() => import('../features/provisioning/ProvisioningPage').then((module) => ({ default: module.ProvisioningPage })));
const UserManagementPage = lazy(() => import('../features/auth/pages/UserManagementPage').then((module) => ({ default: module.UserManagementPage })));
const WorkflowsPage = lazy(() => import('../features/workflows/pages/WorkflowsPage').then((module) => ({ default: module.WorkflowsPage })));

function LazyPage({ children }: { children: ReactNode }) {
  return (
    <Suspense fallback={<div className="rounded-lg border border-zinc-200 bg-white p-5 text-sm text-zinc-500">Loading workspace...</div>}>
      {children}
    </Suspense>
  );
}

export const router = createBrowserRouter([
  { path: '/login', element: <LazyPage><LoginPage /></LazyPage> },
  { path: '/access-denied', element: <LazyPage><AccessDeniedPage /></LazyPage> },
  {
    path: '/',
    element: <AuthenticatedRoute />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { index: true, element: <LazyPage><InventoryPage /></LazyPage> },
          { path: 'inventory/:id', element: <LazyPage><HostDetailPage /></LazyPage> },
          { path: 'infrastructure', element: <LazyPage><InfrastructurePage /></LazyPage> },
          { path: 'infrastructure/nodes/:id', element: <LazyPage><InfrastructureNodeDetailPage /></LazyPage> },
          { path: 'monitoring', element: <LazyPage><MonitoringPage /></LazyPage> },
          { path: 'workflows', element: <LazyPage><WorkflowsPage /></LazyPage> },
          {
            element: <OperatorRoute />,
            children: [
              { path: 'provisioning', element: <LazyPage><ProvisioningPage /></LazyPage> },
              { path: 'deployments', element: <LazyPage><DeploymentsPage /></LazyPage> },
              { path: 'packages', element: <LazyPage><PackagesPage /></LazyPage> },
              { path: 'profiles', element: <LazyPage><ProfilesPage /></LazyPage> },
              { path: 'jobs', element: <LazyPage><JobsPage /></LazyPage> },
              { path: 'automations', element: <LazyPage><AutomationsPage /></LazyPage> },
              { path: 'inventory/:id/tools', element: <LazyPage><HostToolsPage /></LazyPage> },
            ],
          },
          {
            element: <AdminRoute />,
            children: [
              { path: 'infrastructure/credentials', element: <LazyPage><CredentialsPage /></LazyPage> },
              { path: 'identity', element: <LazyPage><IdentityPage /></LazyPage> },
              { path: 'settings/integrations', element: <LazyPage><IntegrationsPage /></LazyPage> },
              { path: 'settings/users', element: <LazyPage><UserManagementPage /></LazyPage> },
            ],
          },
        ],
      },
    ],
  },
]);
