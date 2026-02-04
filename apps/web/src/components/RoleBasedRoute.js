import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState, useEffect } from 'react';
import { Navigate } from 'react-router-dom';
import { Card, Alert, Spin } from 'antd';
import { apiClient } from '../services/api';
export const RoleBasedRoute = ({ children, allowedRoles, }) => {
    const [currentUser, setCurrentUser] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    useEffect(() => {
        checkUserRole();
    }, []);
    const checkUserRole = async () => {
        try {
            setLoading(true);
            const user = await apiClient.getCurrentUser();
            setCurrentUser(user);
        }
        catch (error) {
            console.error('Failed to get current user:', error);
            setError('Failed to verify user role');
        }
        finally {
            setLoading(false);
        }
    };
    if (loading) {
        return (_jsx("div", { className: "p-6 flex justify-center items-center", children: _jsxs(Card, { className: "w-full max-w-md text-center", children: [_jsx(Spin, { size: "large" }), _jsx("p", { className: "mt-4", children: "Verifying access permissions..." })] }) }));
    }
    if (error) {
        return (_jsx("div", { className: "p-6", children: _jsx(Card, { children: _jsx(Alert, { message: "Authentication Error", description: error, type: "error", showIcon: true }) }) }));
    }
    if (!currentUser) {
        return _jsx(Navigate, { to: "/login", replace: true });
    }
    // Check if user has required role
    const hasRequiredRole = allowedRoles.includes(currentUser.role);
    if (!hasRequiredRole) {
        return (_jsx("div", { className: "p-6", children: _jsxs(Card, { children: [_jsx(Alert, { message: "Access Denied", description: `This page requires one of the following roles: ${allowedRoles.join(', ')}. Your current role (${currentUser.role}) is insufficient to access this page.`, type: "error", showIcon: true, className: "mb-4" }), _jsxs("div", { className: "text-sm text-gray-600", children: [_jsxs("p", { children: [_jsx("strong", { children: "Current User:" }), " ", currentUser.sub] }), _jsxs("p", { children: [_jsx("strong", { children: "Role:" }), " ", currentUser.role] }), _jsxs("p", { children: [_jsx("strong", { children: "Tenant:" }), " ", currentUser.tenant_id] })] })] }) }));
    }
    return _jsx(_Fragment, { children: children });
};
// Convenience components for specific roles
export const SystemAdminRoute = ({ children }) => (_jsx(RoleBasedRoute, { allowedRoles: ['system_admin'], children: children }));
export const TenantAdminRoute = ({ children }) => (_jsx(RoleBasedRoute, { allowedRoles: ['system_admin', 'tenant_admin'], children: children }));
export const SiteManagerRoute = ({ children }) => (_jsx(RoleBasedRoute, { allowedRoles: ['system_admin', 'tenant_admin', 'site_manager'], children: children }));
export const TenantManagementRoute = ({ children }) => (_jsx(RoleBasedRoute, { allowedRoles: ['system_admin'], children: children }));
export const SiteManagementRoute = ({ children }) => (_jsx(RoleBasedRoute, { allowedRoles: ['system_admin', 'tenant_admin'], children: children }));
