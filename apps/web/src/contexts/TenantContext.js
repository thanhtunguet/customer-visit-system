import { jsx as _jsx } from "react/jsx-runtime";
import { useState, useCallback } from 'react';
import { apiClient } from '../services/api';
import { TenantContext } from './TenantContextInternal';
export const TenantProvider = ({ children }) => {
    const [tenants, setTenants] = useState([]);
    const [loading, setLoading] = useState(false);
    const loadTenants = useCallback(async () => {
        try {
            setLoading(true);
            const data = await apiClient.getTenants();
            setTenants(data);
        }
        catch (error) {
            console.error('Failed to load tenants:', error);
            throw error;
        }
        finally {
            setLoading(false);
        }
    }, []);
    const refreshTenants = useCallback(async () => {
        await loadTenants();
    }, [loadTenants]);
    const value = {
        tenants,
        loading,
        loadTenants,
        refreshTenants,
    };
    return (_jsx(TenantContext.Provider, { value: value, children: children }));
};
