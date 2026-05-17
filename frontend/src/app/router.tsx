import { createBrowserRouter } from 'react-router-dom';

import { AppLayout } from '../components/layout/AppLayout';
import { AutomationsPage } from '../features/automations/pages/AutomationsPage';
import { AdminRoute, AuthenticatedRoute, OperatorRoute } from '../features/auth/components/RequireRole';
import { AccessDeniedPage } from '../features/auth/pages/AccessDeniedPage';
import { LoginPage } from '../features/auth/pages/LoginPage';
import { CredentialsPage } from '../features/credentials/CredentialsPage';
import { DeploymentsPage } from '../features/deployments/DeploymentsPage';
import { InventoryPage } from '../features/inventory/InventoryPage';
import { HostDetailPage } from '../features/inventory/pages/HostDetailPage';
import { IdentityPage } from '../features/identity/IdentityPage';
import { JobsPage } from '../features/jobs/JobsPage';
import { MonitoringPage } from '../features/monitoring/MonitoringPage';
import { PackagesPage } from '../features/packages/PackagesPage';
import { InfrastructurePage } from '../features/proxmox/pages/InfrastructurePage';
import { InfrastructureNodeDetailPage } from '../features/proxmox/pages/InfrastructureNodeDetailPage';
import { ProfilesPage } from '../features/profiles/ProfilesPage';
import { ProvisioningPage } from '../features/provisioning/ProvisioningPage';
import { IntegrationsPage } from '../features/settings/IntegrationsPage';
import { WorkflowsPage } from '../features/workflows/pages/WorkflowsPage';

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  { path: '/access-denied', element: <AccessDeniedPage /> },
  {
    path: '/',
    element: <AuthenticatedRoute />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { index: true, element: <InventoryPage /> },
          { path: 'inventory/:id', element: <HostDetailPage /> },
          { path: 'infrastructure', element: <InfrastructurePage /> },
          { path: 'infrastructure/nodes/:id', element: <InfrastructureNodeDetailPage /> },
          { path: 'monitoring', element: <MonitoringPage /> },
          { path: 'workflows', element: <WorkflowsPage /> },
          {
            element: <OperatorRoute />,
            children: [
              { path: 'provisioning', element: <ProvisioningPage /> },
              { path: 'deployments', element: <DeploymentsPage /> },
              { path: 'packages', element: <PackagesPage /> },
              { path: 'profiles', element: <ProfilesPage /> },
              { path: 'jobs', element: <JobsPage /> },
              { path: 'automations', element: <AutomationsPage /> },
            ],
          },
          {
            element: <AdminRoute />,
            children: [
              { path: 'infrastructure/credentials', element: <CredentialsPage /> },
              { path: 'identity', element: <IdentityPage /> },
              { path: 'settings/integrations', element: <IntegrationsPage /> },
            ],
          },
        ],
      },
    ],
  },
]);
