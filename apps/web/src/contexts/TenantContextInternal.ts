import { createContext } from 'react';
import { Tenant } from '../types/api';

export interface TenantContextValue {
  tenants: Tenant[];
  loading: boolean;
  loadTenants: () => Promise<void>;
  refreshTenants: () => Promise<void>;
}

export const TenantContext = createContext<TenantContextValue | null>(null);
