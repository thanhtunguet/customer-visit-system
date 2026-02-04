import { useContext } from 'react';
import { TenantContext } from './TenantContextInternal';
export const useTenants = () => {
  const context = useContext(TenantContext);
  if (!context) {
    throw new Error('useTenants must be used within a TenantProvider');
  }
  return context;
};
