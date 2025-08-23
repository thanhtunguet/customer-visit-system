import React, { useState, useEffect } from 'react';
import { Layout as AntLayout, Menu, Avatar, Dropdown, Button, Typography, Space, Select, message } from 'antd';
import { 
  DashboardOutlined, 
  TeamOutlined, 
  ShopOutlined, 
  CameraOutlined,
  UserOutlined,
  BarChartOutlined,
  LogoutOutlined,
  EyeOutlined,
  UsergroupAddOutlined
} from '@ant-design/icons';
import { useNavigate, useLocation, Outlet } from 'react-router-dom';
import { apiClient } from '../services/api';
import { AuthUser, Tenant } from '../types/api';

const { Header, Sider, Content } = AntLayout;
const { Text } = Typography;

export const AppLayout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [selectedTenantId, setSelectedTenantId] = useState<string | null>(null);

  useEffect(() => {
    loadCurrentUser();
  }, []);

  useEffect(() => {
    if (user?.role === 'system_admin') {
      loadTenants();
    }
  }, [user]);

  const loadCurrentUser = async () => {
    try {
      const userData = await apiClient.getCurrentUser();
      setUser(userData);
      
      // For system admin, use stored tenant context or default to null (global view)
      if (userData.role === 'system_admin') {
        const storedTenantId = apiClient.getCurrentTenant();
        setSelectedTenantId(storedTenantId);
      } else {
        // For non-system admins, use their assigned tenant
        setSelectedTenantId(userData.tenant_id || null);
        apiClient.setCurrentTenant(userData.tenant_id || null);
      }
    } catch (error) {
      console.error('Failed to load user:', error);
      navigate('/login');
    } finally {
      setLoading(false);
    }
  };

  const loadTenants = async () => {
    try {
      const tenantsData = await apiClient.getTenants();
      setTenants(tenantsData);
    } catch (error) {
      console.error('Failed to load tenants:', error);
      message.error('Failed to load tenants');
    }
  };

  const handleTenantChange = (tenantId: string | null) => {
    setSelectedTenantId(tenantId);
    apiClient.setCurrentTenant(tenantId);
    
    if (tenantId) {
      const tenant = tenants.find(t => t.tenant_id === tenantId);
      message.success(`Switched to tenant: ${tenant?.name || tenantId}`);
      
      // If user is on a global page, redirect to tenant dashboard
      const currentPath = location.pathname;
      if (currentPath === '/tenants' || currentPath === '/users') {
        navigate('/dashboard');
        return;
      }
    } else {
      message.success('Switched to global view (all tenants)');
      
      // If user is on a tenant-specific page, redirect to global page
      const currentPath = location.pathname;
      const tenantSpecificPaths = ['/dashboard', '/sites', '/cameras', '/staff', '/customers', '/visits', '/reports'];
      if (tenantSpecificPaths.includes(currentPath)) {
        navigate('/tenants');
        return;
      }
    }
    
    // Refresh current page data for context switch
    window.location.reload();
  };

  const handleLogout = () => {
    apiClient.logout();
  };

  // Define menu items based on context
  const globalMenuItems = [
    {
      key: '/tenants',
      icon: <ShopOutlined />,
      label: 'Tenants',
    },
    {
      key: '/users',
      icon: <UsergroupAddOutlined />,
      label: 'Users',
    },
  ];

  const tenantSpecificMenuItems = [
    {
      key: '/dashboard',
      icon: <DashboardOutlined />,
      label: 'Dashboard',
    },
    {
      key: '/sites',
      icon: <ShopOutlined />,
      label: 'Sites',
    },
    {
      key: '/cameras',
      icon: <CameraOutlined />,
      label: 'Cameras',
    },
    {
      key: '/staff',
      icon: <TeamOutlined />,
      label: 'Staff',
    },
    {
      key: '/customers',
      icon: <UserOutlined />,
      label: 'Customers',
    },
    {
      key: '/visits',
      icon: <EyeOutlined />,
      label: 'Visits',
    },
    {
      key: '/reports',
      icon: <BarChartOutlined />,
      label: 'Reports',
    },
  ];

  // Filter menu items based on user role and tenant context
  const getFilteredMenuItems = () => {
    if (!user) return [];
    
    if (user.role === 'system_admin') {
      // System admin menu depends on tenant selection
      if (selectedTenantId) {
        // Tenant-specific view: show both global and tenant-specific features
        return [
          ...globalMenuItems,
          ...tenantSpecificMenuItems,
        ];
      } else {
        // Global view: only show global management features
        return globalMenuItems;
      }
    } else {
      // Non-system admin users only see tenant-specific features
      return tenantSpecificMenuItems;
    }
  };

  const userMenuItems = [
    {
      key: 'profile',
      icon: <UserOutlined />,
      label: `${user?.sub || 'User'} (${user?.role})`,
      disabled: true,
    },
    ...(user?.role === 'system_admin' && selectedTenantId ? [{
      key: 'tenant-context',
      icon: <ShopOutlined />,
      label: `Context: ${tenants.find(t => t.tenant_id === selectedTenantId)?.name || selectedTenantId}`,
      disabled: true,
    }] : user?.role === 'system_admin' ? [{
      key: 'tenant-context',
      icon: <ShopOutlined />,
      label: 'Context: Global View',
      disabled: true,
    }] : []),
    {
      type: 'divider' as const,
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: 'Logout',
      onClick: handleLogout,
    },
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <AntLayout className="min-h-screen">
      <Sider
        trigger={null}
        collapsible
        collapsed={collapsed}
        className="bg-white shadow-md"
      >
        <div className="p-4">
          <div className="text-center">
            <h1 className={`font-bold text-blue-600 transition-all ${
              collapsed ? 'text-sm' : 'text-lg'
            }`}>
              {collapsed ? 'CV' : 'Customer Visits'}
            </h1>
            {!collapsed && user?.role === 'system_admin' && (
              <div className="text-xs text-gray-500 mt-1">
                {selectedTenantId ? (
                  <span className="bg-blue-100 text-blue-700 px-2 py-1 rounded">
                    {tenants.find(t => t.tenant_id === selectedTenantId)?.name || 'Tenant View'}
                  </span>
                ) : (
                  <span className="bg-gray-100 text-gray-700 px-2 py-1 rounded">
                    Global View
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
        
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          items={getFilteredMenuItems()}
          onClick={({ key }) => navigate(key)}
          className="border-r-0"
        />
      </Sider>
      
      <AntLayout>
        <Header className="bg-white shadow-sm px-4 flex items-center justify-between">
          <Space>
            <Button
              type="text"
              onClick={() => setCollapsed(!collapsed)}
              className="text-gray-600"
            >
              {collapsed ? '→' : '←'}
            </Button>
            
            {user?.role === 'system_admin' ? (
              <Space>
                <Text strong className="text-gray-700">Tenant:</Text>
                <Select
                  value={selectedTenantId}
                  onChange={handleTenantChange}
                  placeholder="Select tenant"
                  style={{ minWidth: 200 }}
                  loading={tenants.length === 0}
                  allowClear
                  options={[
                    { value: null, label: 'All Tenants (Global View)' },
                    ...tenants.map(tenant => ({
                      value: tenant.tenant_id,
                      label: `${tenant.name} (${tenant.tenant_id})`,
                    }))
                  ]}
                />
              </Space>
            ) : (
              <Text strong className="text-gray-700">
                Tenant: {user?.tenant_id || 'N/A'}
              </Text>
            )}
          </Space>
          
          <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
            <Button type="text" className="flex items-center">
              <Avatar size="small" icon={<UserOutlined />} className="mr-2" />
              <span className="hidden sm:inline">{user?.sub}</span>
            </Button>
          </Dropdown>
        </Header>
        
        <Content className="p-6 bg-gray-50">
          <Outlet />
        </Content>
      </AntLayout>
    </AntLayout>
  );
};