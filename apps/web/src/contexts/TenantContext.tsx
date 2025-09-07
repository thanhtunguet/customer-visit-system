import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import { Tenant } from '../types/api';
import { apiClient } from '../services/api';

interface TenantContextValue {
  tenants: Tenant[];
  loading: boolean;
  loadTenants: () => Promise<void>;
  refreshTenants: () => Promise<void>;
}

const TenantContext = createContext<TenantContextValue | null>(null);

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

export const useTenants = (): TenantContextValue => {
  const context = useContext(TenantContext);
  if (!context) {
    throw new Error('useTenants must be used within a TenantProvider');
  }
  return context;
};