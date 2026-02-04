import { useContext } from 'react';
import { TenantContext, TenantContextValue } from './TenantContextInternal';

export const useTenants = (): TenantContextValue => {
  const context = useContext(TenantContext);
  if (!context) {
    throw new Error('useTenants must be used within a TenantProvider');
  }
  return context;
};
