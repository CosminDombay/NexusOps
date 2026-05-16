import { createBrowserRouter } from 'react-router-dom';

import { AppLayout } from '../components/layout/AppLayout';
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

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <InventoryPage /> },
      { path: 'inventory/:id', element: <HostDetailPage /> },
      { path: 'infrastructure', element: <InfrastructurePage /> },
      { path: 'infrastructure/nodes/:id', element: <InfrastructureNodeDetailPage /> },
      { path: 'identity', element: <IdentityPage /> },
      { path: 'provisioning', element: <ProvisioningPage /> },
      { path: 'deployments', element: <DeploymentsPage /> },
      { path: 'packages', element: <PackagesPage /> },
      { path: 'monitoring', element: <MonitoringPage /> },
      { path: 'profiles', element: <ProfilesPage /> },
      { path: 'jobs', element: <JobsPage /> },
      { path: 'settings/integrations', element: <IntegrationsPage /> },
    ],
  },
]);
