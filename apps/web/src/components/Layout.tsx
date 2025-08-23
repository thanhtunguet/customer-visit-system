import React, { useState, useEffect } from 'react';
import { Layout as AntLayout, Menu, Avatar, Dropdown, Button, Typography, Space } from 'antd';
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
import { AuthUser } from '../types/api';

const { Header, Sider, Content } = AntLayout;
const { Text } = Typography;

export const AppLayout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadCurrentUser();
  }, []);

  const loadCurrentUser = async () => {
    try {
      const userData = await apiClient.getCurrentUser();
      setUser(userData);
    } catch (error) {
      console.error('Failed to load user:', error);
      navigate('/login');
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    apiClient.logout();
  };

  const menuItems = [
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

  // Filter menu items based on user role
  const getFilteredMenuItems = () => {
    if (!user) return [];
    
    if (user.role === 'system_admin') {
      return [
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
        ...menuItems,
      ];
    }
    
    return menuItems;
  };

  const userMenuItems = [
    {
      key: 'profile',
      icon: <UserOutlined />,
      label: `${user?.sub || 'User'} (${user?.role})`,
      disabled: true,
    },
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
            
            <Text strong className="text-gray-700">
              Tenant: {user?.tenant_id}
            </Text>
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