import React, { useState, useCallback, ReactNode } from 'react';
import { apiClient } from '../services/api';
import { TenantContext, TenantContextValue } from './TenantContextInternal';

interface TenantProviderProps {
  children: ReactNode;
}

export const TenantProvider: React.FC<TenantProviderProps> = ({ children }) => {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(false);

  const loadTenants = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiClient.getTenants();
      setTenants(data);
    } catch (error) {
      console.error('Failed to load tenants:', error);
      throw error;
    } finally {
      setLoading(false);
    }
  }, []);

  const refreshTenants = useCallback(async () => {
    await loadTenants();
  }, [loadTenants]);

  const value: TenantContextValue = {
    tenants,
    loading,
    loadTenants,
    refreshTenants
  };

  return (
    <TenantContext.Provider value={value}>
      {children}
    </TenantContext.Provider>
  );
};
