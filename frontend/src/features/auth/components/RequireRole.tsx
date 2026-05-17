import { Navigate, Outlet, useLocation } from 'react-router-dom';

import { useAuth } from '../hooks/useAuth';
import type { UserRole } from '../types/auth';

const roleRank: Record<UserRole, number> = {
  viewer: 1,
  operator: 2,
  admin: 3,
};

export function RequireRole({ minimumRole }: { minimumRole?: UserRole }) {
  const { user, isAuthenticated, isRestoring } = useAuth();
  const location = useLocation();

  if (isRestoring) {
    return <div className="p-6 text-sm text-zinc-500">Restoring session...</div>;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (minimumRole && (!user || roleRank[user.role] < roleRank[minimumRole])) {
    return <Navigate to="/access-denied" replace />;
  }

  return <Outlet />;
}

export function AuthenticatedRoute() {
  return <RequireRole />;
}

export function OperatorRoute() {
  return <RequireRole minimumRole="operator" />;
}

export function AdminRoute() {
  return <RequireRole minimumRole="admin" />;
}
