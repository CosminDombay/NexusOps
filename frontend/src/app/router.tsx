import { createBrowserRouter } from 'react-router-dom';

import { AppLayout } from '../components/layout/AppLayout';
import { DeploymentsPage } from '../features/deployments/DeploymentsPage';
import { InventoryPage } from '../features/inventory/InventoryPage';
import { JobsPage } from '../features/jobs/JobsPage';
import { MonitoringPage } from '../features/monitoring/MonitoringPage';
import { PackagesPage } from '../features/packages/PackagesPage';
import { InfrastructurePage } from '../features/proxmox/pages/InfrastructurePage';
import { ProfilesPage } from '../features/profiles/ProfilesPage';
import { ProvisioningPage } from '../features/provisioning/ProvisioningPage';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <InventoryPage /> },
      { path: 'infrastructure', element: <InfrastructurePage /> },
      { path: 'provisioning', element: <ProvisioningPage /> },
      { path: 'deployments', element: <DeploymentsPage /> },
      { path: 'packages', element: <PackagesPage /> },
      { path: 'monitoring', element: <MonitoringPage /> },
      { path: 'profiles', element: <ProfilesPage /> },
      { path: 'jobs', element: <JobsPage /> },
    ],
  },
]);
