import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState, useEffect, useCallback } from 'react';
import { Layout as AntLayout, Menu, Avatar, Dropdown, Button, Typography, Space, Select, App } from 'antd';
import { DashboardOutlined, TeamOutlined, ShopOutlined, CameraOutlined, UserOutlined, BarChartOutlined, LogoutOutlined, EyeOutlined, UsergroupAddOutlined, KeyOutlined, CloudServerOutlined, } from '@ant-design/icons';
import { useNavigate, useLocation, Outlet } from 'react-router-dom';
import { apiClient } from '../services/api';
import { UserRole } from '../types/api';
import { ChangePasswordModal } from './ChangePasswordModal';
import { useTenants } from '../contexts/useTenants';
const { Header, Sider, Content } = AntLayout;
const { Text } = Typography;
export const AppLayout = () => {
    const navigate = useNavigate();
    const location = useLocation();
    const { message } = App.useApp();
    const { tenants, loadTenants } = useTenants();
    const [collapsed, setCollapsed] = useState(false);
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);
    const [selectedTenantId, setSelectedTenantId] = useState('__global__');
    const [changePasswordModalOpen, setChangePasswordModalOpen] = useState(false);
    const loadCurrentUser = useCallback(async () => {
        try {
            const userData = await apiClient.getCurrentUser();
            setUser(userData);
            // For system admin, use stored tenant context or default to global view
            if (userData.role === UserRole.SYSTEM_ADMIN) {
                const storedTenantId = apiClient.getCurrentTenant();
                // Convert null to '__global__' for Select component
                setSelectedTenantId(storedTenantId ?? '__global__');
            }
            else {
                // For non-system admins, use their assigned tenant
                setSelectedTenantId(userData.tenant_id ?? '__global__');
                apiClient.setCurrentTenant(userData.tenant_id || null);
            }
        }
        catch (error) {
            console.error('Failed to load user:', error);
            navigate('/login');
        }
        finally {
            setLoading(false);
        }
    }, [navigate]);
    useEffect(() => {
        loadCurrentUser();
    }, [loadCurrentUser]);
    useEffect(() => {
        if (user?.role === UserRole.SYSTEM_ADMIN) {
            loadTenants();
        }
    }, [user, loadTenants]);
    const handleTenantChange = async (tenantId) => {
        try {
            // Only system admins can switch views
            if (user?.role !== UserRole.SYSTEM_ADMIN) {
                message.error('Only system admins can switch views');
                return;
            }
            // Convert '__global__' or undefined to null for API
            const actualTenantId = (tenantId === '__global__' || tenantId === undefined) ? null : tenantId;
            // Use the switchView API to get new token
            await apiClient.switchView(actualTenantId);
            // Convert back to '__global__' for state (to match Select component expectation)
            setSelectedTenantId(actualTenantId ?? '__global__');
            if (actualTenantId) {
                const tenant = tenants.find(t => t.tenant_id === actualTenantId);
                message.success(`Switched to tenant: ${tenant?.name || actualTenantId}`);
                // If user is on a global page, redirect to tenant dashboard
                const currentPath = location.pathname;
                if (currentPath === '/tenants' || currentPath === '/users') {
                    navigate('/dashboard');
                    return;
                }
            }
            else {
                message.success('Switched to global view (all tenants)');
                // If user is on a tenant-specific page, redirect to global page
                const currentPath = location.pathname;
                const tenantSpecificPaths = ['/dashboard', '/sites', '/cameras', '/workers', '/staff', '/customers', '/visits', '/reports'];
                if (tenantSpecificPaths.includes(currentPath)) {
                    navigate('/tenants');
                    return;
                }
            }
            // Refresh current page data for context switch
            window.location.reload();
        }
        catch (error) {
            console.error('Failed to switch view:', error);
            message.error('Failed to switch view');
        }
    };
    const handleLogout = () => {
        apiClient.logout();
    };
    // Define menu items based on context
    const globalMenuItems = [
        {
            key: '/tenants',
            icon: _jsx(ShopOutlined, {}),
            label: 'Tenants',
        },
        {
            key: '/users',
            icon: _jsx(UsergroupAddOutlined, {}),
            label: 'Users',
        },
    ];
    const tenantSpecificMenuItems = [
        {
            key: '/dashboard',
            icon: _jsx(DashboardOutlined, {}),
            label: 'Dashboard',
        },
        {
            key: '/sites',
            icon: _jsx(ShopOutlined, {}),
            label: 'Sites',
        },
        {
            key: '/cameras',
            icon: _jsx(CameraOutlined, {}),
            label: 'Cameras',
        },
        {
            key: '/workers',
            icon: _jsx(CloudServerOutlined, {}),
            label: 'Workers',
        },
        {
            key: '/staff',
            icon: _jsx(TeamOutlined, {}),
            label: 'Staff',
        },
        {
            key: '/customers',
            icon: _jsx(UserOutlined, {}),
            label: 'Customers',
        },
        {
            key: '/visits',
            icon: _jsx(EyeOutlined, {}),
            label: 'Visits',
        },
        {
            key: '/reports',
            icon: _jsx(BarChartOutlined, {}),
            label: 'Reports',
        },
        {
            key: '/api-keys',
            icon: _jsx(KeyOutlined, {}),
            label: 'API Keys',
        },
    ];
    // Filter menu items based on user role and tenant context
    const getFilteredMenuItems = () => {
        if (!user)
            return [];
        if (user.role === UserRole.SYSTEM_ADMIN) {
            // System admin menu depends on tenant selection
            if (selectedTenantId !== '__global__') {
                // Tenant-specific view: only show tenant-specific features
                return tenantSpecificMenuItems;
            }
            else {
                // Global view: only show global management features
                return globalMenuItems;
            }
        }
        else if (user.role === UserRole.TENANT_ADMIN) {
            // Tenant admin can see all tenant-specific features but not global management
            return tenantSpecificMenuItems;
        }
        else if (user.role === UserRole.SITE_MANAGER) {
            // Site manager can only see site-specific features, no tenant/sites management
            return tenantSpecificMenuItems.filter(item => !['/sites', '/tenants'].includes(item.key));
        }
        else {
            // Worker role - very limited access
            return tenantSpecificMenuItems.filter(item => ['/dashboard', '/visits'].includes(item.key));
        }
    };
    const userMenuItems = [
        {
            key: 'profile',
            icon: _jsx(UserOutlined, {}),
            label: `${user?.sub || 'User'} (${user?.role})`,
            disabled: true,
        },
        ...(user?.role === UserRole.SYSTEM_ADMIN && selectedTenantId !== '__global__' ? [{
                key: 'tenant-context',
                icon: _jsx(ShopOutlined, {}),
                label: `Context: ${tenants.find(t => t.tenant_id === selectedTenantId)?.name || selectedTenantId}`,
                disabled: true,
            }] : user?.role === UserRole.SYSTEM_ADMIN ? [{
                key: 'tenant-context',
                icon: _jsx(ShopOutlined, {}),
                label: 'Context: Global View',
                disabled: true,
            }] : []),
        {
            type: 'divider',
        },
        {
            key: 'change-password',
            icon: _jsx(KeyOutlined, {}),
            label: 'Change Password',
            onClick: () => setChangePasswordModalOpen(true),
        },
        {
            key: 'logout',
            icon: _jsx(LogoutOutlined, {}),
            label: 'Logout',
            onClick: handleLogout,
        },
    ];
    if (loading) {
        return (_jsx("div", { className: "flex items-center justify-center min-h-screen", children: _jsxs("div", { className: "text-center", children: [_jsx("div", { className: "animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600 mx-auto" }), _jsx("p", { className: "mt-4 text-gray-600", children: "Loading..." })] }) }));
    }
    return (_jsxs(AntLayout, { className: "min-h-screen", children: [_jsxs(Sider, { trigger: null, collapsible: true, collapsed: collapsed, className: "bg-white shadow-md", children: [_jsx("div", { className: "p-4", children: _jsxs("div", { className: "text-center", children: [_jsx("h1", { className: `font-bold text-blue-600 transition-all ${collapsed ? 'text-sm' : 'text-lg'}`, children: collapsed ? 'CV' : 'Customer Visits' }), !collapsed && user?.role === UserRole.SYSTEM_ADMIN && (_jsx("div", { className: "text-xs text-gray-500 mt-1", children: selectedTenantId !== '__global__' ? (_jsx("span", { className: "bg-blue-100 text-blue-700 px-2 py-1 rounded", children: tenants.find(t => t.tenant_id === selectedTenantId)?.name || 'Tenant View' })) : (_jsx("span", { className: "bg-gray-100 text-gray-700 px-2 py-1 rounded", children: "Global View" })) }))] }) }), _jsx(Menu, { mode: "inline", selectedKeys: [location.pathname], items: getFilteredMenuItems(), onClick: ({ key }) => navigate(key), className: "border-r-0" })] }), _jsxs(AntLayout, { children: [_jsxs(Header, { className: "bg-white shadow-sm px-4 flex items-center justify-between", children: [_jsxs(Space, { children: [_jsx(Button, { type: "text", onClick: () => setCollapsed(!collapsed), className: "text-gray-600", children: collapsed ? '→' : '←' }), user?.role === UserRole.SYSTEM_ADMIN && (_jsxs(Space, { children: [_jsx(Text, { strong: true, className: "text-gray-700", children: "Tenant:" }), _jsx(Select, { value: selectedTenantId === '__global__' ? undefined : selectedTenantId, onChange: handleTenantChange, onClear: () => handleTenantChange('__global__'), placeholder: "Select tenant", style: { minWidth: 200 }, loading: tenants.length === 0, allowClear: true, options: [
                                                    { value: '__global__', label: 'All Tenants (Global View)' },
                                                    ...tenants.map(tenant => ({
                                                        value: tenant.tenant_id,
                                                        label: `${tenant.name} (${tenant.tenant_id})`,
                                                    }))
                                                ] })] }))] }), _jsx(Dropdown, { menu: { items: userMenuItems }, placement: "bottomRight", children: _jsxs(Button, { type: "text", className: "flex items-center", children: [_jsx(Avatar, { size: "small", icon: _jsx(UserOutlined, {}), className: "mr-2" }), _jsx("span", { className: "hidden sm:inline", children: user?.sub })] }) })] }), _jsx(Content, { className: "p-6 bg-gray-50", children: _jsx(Outlet, {}) })] }), _jsx(ChangePasswordModal, { open: changePasswordModalOpen, onClose: () => setChangePasswordModalOpen(false) })] }));
};
