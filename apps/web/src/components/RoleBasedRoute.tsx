import React, { useState, useEffect } from 'react';
import { Navigate } from 'react-router-dom';
import { Card, Alert, Spin } from 'antd';
import { apiClient } from '../services/api';
import { AuthUser } from '../types/api';

interface RoleBasedRouteProps {
  children: React.ReactNode;
  allowedRoles: string[];
  fallbackPath?: string;
}

export const RoleBasedRoute: React.FC<RoleBasedRouteProps> = ({
  children,
  allowedRoles,
}) => {
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    checkUserRole();
  }, []);

  const checkUserRole = async () => {
    try {
      setLoading(true);
      const user = await apiClient.getCurrentUser();
      setCurrentUser(user);
    } catch (error: unknown) {
      console.error('Failed to get current user:', error);
      setError('Failed to verify user role');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="p-6 flex justify-center items-center">
        <Card className="w-full max-w-md text-center">
          <Spin size="large" />
          <p className="mt-4">Verifying access permissions...</p>
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <Card>
          <Alert
            message="Authentication Error"
            description={error}
            type="error"
            showIcon
          />
        </Card>
      </div>
    );
  }

  if (!currentUser) {
    return <Navigate to="/login" replace />;
  }

  // Check if user has required role
  const hasRequiredRole = allowedRoles.includes(currentUser.role);

  if (!hasRequiredRole) {
    return (
      <div className="p-6">
        <Card>
          <Alert
            message="Access Denied"
            description={`This page requires one of the following roles: ${allowedRoles.join(', ')}. Your current role (${currentUser.role}) is insufficient to access this page.`}
            type="error"
            showIcon
            className="mb-4"
          />
          <div className="text-sm text-gray-600">
            <p><strong>Current User:</strong> {currentUser.sub}</p>
            <p><strong>Role:</strong> {currentUser.role}</p>
            <p><strong>Tenant:</strong> {currentUser.tenant_id}</p>
          </div>
        </Card>
      </div>
    );
  }

  return <>{children}</>;
};

// Convenience components for specific roles
export const SystemAdminRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <RoleBasedRoute allowedRoles={['system_admin']}>
    {children}
  </RoleBasedRoute>
);

export const TenantAdminRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <RoleBasedRoute allowedRoles={['system_admin', 'tenant_admin']}>
    {children}
  </RoleBasedRoute>
);

export const SiteManagerRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <RoleBasedRoute allowedRoles={['system_admin', 'tenant_admin', 'site_manager']}>
    {children}
  </RoleBasedRoute>
);

export const TenantManagementRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <RoleBasedRoute allowedRoles={['system_admin']}>
    {children}
  </RoleBasedRoute>
);

export const SiteManagementRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <RoleBasedRoute allowedRoles={['system_admin', 'tenant_admin']}>
    {children}
  </RoleBasedRoute>
);
