import React, { useState, useEffect } from 'react';
import { 
  Table, 
  Button, 
  Space, 
  Tag, 
  Popconfirm, 
  message, 
  Modal, 
  Form, 
  Input, 
  Select, 
  Switch,
  Tooltip,
  Card,
  Typography
} from 'antd';
import { 
  PlusOutlined, 
  EditOutlined, 
  DeleteOutlined, 
  KeyOutlined,
  StopOutlined,
  PlayCircleOutlined,
  UsergroupAddOutlined
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';

import { apiClient } from '../services/api';
import { User, UserCreate, UserUpdate, UserPasswordUpdate, UserRole, Tenant } from '../types/api';

const { Option } = Select;
const { Title } = Typography;

export const Users: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(false);
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [passwordModalVisible, setPasswordModalVisible] = useState(false);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);

  const [createForm] = Form.useForm<UserCreate>();
  const [editForm] = Form.useForm<UserUpdate>();
  const [passwordForm] = Form.useForm<UserPasswordUpdate>();

  useEffect(() => {
    loadUsers();
    loadTenants();
  }, []);

  const loadUsers = async () => {
    setLoading(true);
    try {
      const data = await apiClient.getUsers();
      setUsers(data);
    } catch (error) {
      message.error('Failed to load users');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const loadTenants = async () => {
    try {
      const data = await apiClient.getTenants();
      setTenants(data);
    } catch (error) {
      console.error('Failed to load tenants:', error);
    }
  };

  const handleCreateUser = async (values: UserCreate) => {
    try {
      await apiClient.createUser(values);
      message.success('User created successfully');
      setCreateModalVisible(false);
      createForm.resetFields();
      loadUsers();
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Failed to create user');
    }
  };

  const handleEditUser = async (values: UserUpdate) => {
    if (!selectedUser) return;

    try {
      await apiClient.updateUser(selectedUser.user_id, values);
      message.success('User updated successfully');
      setEditModalVisible(false);
      editForm.resetFields();
      setSelectedUser(null);
      loadUsers();
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Failed to update user');
    }
  };

  const handleChangePassword = async (values: UserPasswordUpdate) => {
    if (!selectedUser) return;

    try {
      await apiClient.changeUserPassword(selectedUser.user_id, values);
      message.success('Password changed successfully');
      setPasswordModalVisible(false);
      passwordForm.resetFields();
      setSelectedUser(null);
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Failed to change password');
    }
  };

  const handleToggleStatus = async (user: User) => {
    try {
      await apiClient.toggleUserStatus(user.user_id);
      message.success(`User ${user.is_active ? 'disabled' : 'enabled'} successfully`);
      loadUsers();
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Failed to toggle user status');
    }
  };

  const handleDeleteUser = async (user: User) => {
    try {
      await apiClient.deleteUser(user.user_id);
      message.success('User deleted successfully');
      loadUsers();
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Failed to delete user');
    }
  };

  const showEditModal = (user: User) => {
    setSelectedUser(user);
    editForm.setFieldsValue({
      username: user.username,
      email: user.email,
      first_name: user.first_name,
      last_name: user.last_name,
      role: user.role,
      tenant_id: user.tenant_id,
      is_active: user.is_active
    });
    setEditModalVisible(true);
  };

  const showPasswordModal = (user: User) => {
    setSelectedUser(user);
    setPasswordModalVisible(true);
  };

  const getRoleColor = (role: UserRole): string => {
    switch (role) {
      case UserRole.SYSTEM_ADMIN: return 'red';
      case UserRole.TENANT_ADMIN: return 'orange';
      case UserRole.SITE_MANAGER: return 'blue';
      case UserRole.WORKER: return 'green';
      default: return 'default';
    }
  };

  const getRoleLabel = (role: UserRole): string => {
    switch (role) {
      case UserRole.SYSTEM_ADMIN: return 'System Admin';
      case UserRole.TENANT_ADMIN: return 'Tenant Admin';
      case UserRole.SITE_MANAGER: return 'Site Manager';
      case UserRole.WORKER: return 'Worker';
      default: return role;
    }
  };

  const getTenantName = (tenantId?: string): string => {
    if (!tenantId) return 'N/A';
    const tenant = tenants.find(t => t.tenant_id === tenantId);
    return tenant ? tenant.name : tenantId;
  };

  const columns: ColumnsType<User> = [
    {
      title: 'Username',
      dataIndex: 'username',
      key: 'username',
      sorter: (a, b) => a.username.localeCompare(b.username),
    },
    {
      title: 'Name',
      key: 'name',
      render: (_, user) => user.full_name,
      sorter: (a, b) => a.full_name.localeCompare(b.full_name),
    },
    {
      title: 'Email',
      dataIndex: 'email',
      key: 'email',
    },
    {
      title: 'Role',
      key: 'role',
      render: (_, user) => (
        <Tag color={getRoleColor(user.role)}>
          {getRoleLabel(user.role)}
        </Tag>
      ),
      sorter: (a, b) => a.role.localeCompare(b.role),
    },
    {
      title: 'Tenant',
      key: 'tenant',
      render: (_, user) => getTenantName(user.tenant_id),
    },
    {
      title: 'Status',
      key: 'status',
      render: (_, user) => (
        <Tag color={user.is_active ? 'success' : 'error'}>
          {user.is_active ? 'Active' : 'Disabled'}
        </Tag>
      ),
      sorter: (a, b) => Number(b.is_active) - Number(a.is_active),
    },
    {
      title: 'Last Login',
      key: 'last_login',
      render: (_, user) => 
        user.last_login 
          ? new Date(user.last_login).toLocaleString()
          : 'Never',
      sorter: (a, b) => {
        if (!a.last_login && !b.last_login) return 0;
        if (!a.last_login) return 1;
        if (!b.last_login) return -1;
        return new Date(a.last_login).getTime() - new Date(b.last_login).getTime();
      },
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_, user) => (
        <Space size="small">
          <Tooltip title="Edit User">
            <Button
              icon={<EditOutlined />}
              size="small"
              onClick={() => showEditModal(user)}
            />
          </Tooltip>
          
          <Tooltip title="Change Password">
            <Button
              icon={<KeyOutlined />}
              size="small"
              onClick={() => showPasswordModal(user)}
            />
          </Tooltip>
          
          <Tooltip title={user.is_active ? 'Disable User' : 'Enable User'}>
            <Popconfirm
              title={`Are you sure you want to ${user.is_active ? 'disable' : 'enable'} this user?`}
              onConfirm={() => handleToggleStatus(user)}
              okText="Yes"
              cancelText="No"
            >
              <Button
                icon={user.is_active ? <StopOutlined /> : <PlayCircleOutlined />}
                size="small"
                danger={user.is_active}
              />
            </Popconfirm>
          </Tooltip>
          
          <Tooltip title="Delete User">
            <Popconfirm
              title="Are you sure you want to delete this user?"
              onConfirm={() => handleDeleteUser(user)}
              okText="Yes"
              cancelText="No"
            >
              <Button
                icon={<DeleteOutlined />}
                size="small"
                danger
              />
            </Popconfirm>
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <Title level={2} className="flex items-center gap-2 mb-0">
            <UsergroupAddOutlined />
            User Management
          </Title>
          <p className="text-gray-600 mt-1">
            Manage system users and their access permissions
          </p>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setCreateModalVisible(true)}
          size="large"
        >
          Create User
        </Button>
      </div>

      <Card>

        <Table
          columns={columns}
          dataSource={users}
          loading={loading}
          rowKey="user_id"
          pagination={{
            pageSize: 10,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `Total ${total} users`,
          }}
        />
      </Card>

      {/* Create User Modal */}
      <Modal
        title="Create New User"
        open={createModalVisible}
        onCancel={() => {
          setCreateModalVisible(false);
          createForm.resetFields();
        }}
        footer={null}
        width={600}
      >
        <Form
          form={createForm}
          layout="vertical"
          onFinish={handleCreateUser}
        >
          <Form.Item
            name="username"
            label="Username"
            rules={[
              { required: true, message: 'Please enter username' },
              { min: 3, message: 'Username must be at least 3 characters' }
            ]}
          >
            <Input placeholder="Enter username" />
          </Form.Item>

          <Form.Item
            name="email"
            label="Email"
            rules={[
              { required: true, message: 'Please enter email' },
              { type: 'email', message: 'Please enter a valid email' }
            ]}
          >
            <Input placeholder="Enter email address" />
          </Form.Item>

          <div style={{ display: 'flex', gap: 16 }}>
            <Form.Item
              name="first_name"
              label="First Name"
              rules={[{ required: true, message: 'Please enter first name' }]}
              style={{ flex: 1 }}
            >
              <Input placeholder="Enter first name" />
            </Form.Item>

            <Form.Item
              name="last_name"
              label="Last Name"
              rules={[{ required: true, message: 'Please enter last name' }]}
              style={{ flex: 1 }}
            >
              <Input placeholder="Enter last name" />
            </Form.Item>
          </div>

          <Form.Item
            name="password"
            label="Password"
            rules={[
              { required: true, message: 'Please enter password' },
              { min: 6, message: 'Password must be at least 6 characters' }
            ]}
          >
            <Input.Password placeholder="Enter password" />
          </Form.Item>

          <Form.Item
            name="role"
            label="Role"
            rules={[{ required: true, message: 'Please select role' }]}
          >
            <Select placeholder="Select user role">
              {Object.values(UserRole).map(role => (
                <Option key={role} value={role}>
                  {getRoleLabel(role)}
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="tenant_id"
            label="Tenant"
            dependencies={['role']}
            rules={[
              ({ getFieldValue }) => ({
                validator(_, value) {
                  const role = getFieldValue('role');
                  if (role !== UserRole.SYSTEM_ADMIN && !value) {
                    return Promise.reject(new Error('Tenant is required for non-system admin users'));
                  }
                  return Promise.resolve();
                },
              }),
            ]}
          >
            <Select placeholder="Select tenant (not required for System Admin)">
              {tenants.map(tenant => (
                <Option key={tenant.tenant_id} value={tenant.tenant_id}>
                  {tenant.name}
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="is_active"
            label="Status"
            valuePropName="checked"
            initialValue={true}
          >
            <Switch checkedChildren="Active" unCheckedChildren="Disabled" />
          </Form.Item>

          <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
            <Space>
              <Button onClick={() => {
                setCreateModalVisible(false);
                createForm.resetFields();
              }}>
                Cancel
              </Button>
              <Button type="primary" htmlType="submit">
                Create User
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* Edit User Modal */}
      <Modal
        title="Edit User"
        open={editModalVisible}
        onCancel={() => {
          setEditModalVisible(false);
          editForm.resetFields();
          setSelectedUser(null);
        }}
        footer={null}
        width={600}
      >
        <Form
          form={editForm}
          layout="vertical"
          onFinish={handleEditUser}
        >
          <Form.Item
            name="username"
            label="Username"
            rules={[
              { required: true, message: 'Please enter username' },
              { min: 3, message: 'Username must be at least 3 characters' }
            ]}
          >
            <Input placeholder="Enter username" />
          </Form.Item>

          <Form.Item
            name="email"
            label="Email"
            rules={[
              { required: true, message: 'Please enter email' },
              { type: 'email', message: 'Please enter a valid email' }
            ]}
          >
            <Input placeholder="Enter email address" />
          </Form.Item>

          <div style={{ display: 'flex', gap: 16 }}>
            <Form.Item
              name="first_name"
              label="First Name"
              rules={[{ required: true, message: 'Please enter first name' }]}
              style={{ flex: 1 }}
            >
              <Input placeholder="Enter first name" />
            </Form.Item>

            <Form.Item
              name="last_name"
              label="Last Name"
              rules={[{ required: true, message: 'Please enter last name' }]}
              style={{ flex: 1 }}
            >
              <Input placeholder="Enter last name" />
            </Form.Item>
          </div>

          <Form.Item
            name="role"
            label="Role"
            rules={[{ required: true, message: 'Please select role' }]}
          >
            <Select placeholder="Select user role">
              {Object.values(UserRole).map(role => (
                <Option key={role} value={role}>
                  {getRoleLabel(role)}
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="tenant_id"
            label="Tenant"
            dependencies={['role']}
            rules={[
              ({ getFieldValue }) => ({
                validator(_, value) {
                  const role = getFieldValue('role');
                  if (role !== UserRole.SYSTEM_ADMIN && !value) {
                    return Promise.reject(new Error('Tenant is required for non-system admin users'));
                  }
                  return Promise.resolve();
                },
              }),
            ]}
          >
            <Select placeholder="Select tenant (not required for System Admin)">
              {tenants.map(tenant => (
                <Option key={tenant.tenant_id} value={tenant.tenant_id}>
                  {tenant.name}
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="is_active"
            label="Status"
            valuePropName="checked"
          >
            <Switch checkedChildren="Active" unCheckedChildren="Disabled" />
          </Form.Item>

          <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
            <Space>
              <Button onClick={() => {
                setEditModalVisible(false);
                editForm.resetFields();
                setSelectedUser(null);
              }}>
                Cancel
              </Button>
              <Button type="primary" htmlType="submit">
                Update User
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* Change Password Modal */}
      <Modal
        title={`Change Password - ${selectedUser?.username}`}
        open={passwordModalVisible}
        onCancel={() => {
          setPasswordModalVisible(false);
          passwordForm.resetFields();
          setSelectedUser(null);
        }}
        footer={null}
        width={500}
      >
        <Form
          form={passwordForm}
          layout="vertical"
          onFinish={handleChangePassword}
        >
          <Form.Item
            name="new_password"
            label="New Password"
            rules={[
              { required: true, message: 'Please enter new password' },
              { min: 6, message: 'Password must be at least 6 characters' }
            ]}
          >
            <Input.Password placeholder="Enter new password" />
          </Form.Item>

          <Form.Item
            name="confirm_password"
            label="Confirm New Password"
            dependencies={['new_password']}
            rules={[
              { required: true, message: 'Please confirm new password' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('new_password') === value) {
                    return Promise.resolve();
                  }
                  return Promise.reject(new Error('Passwords do not match'));
                },
              }),
            ]}
          >
            <Input.Password placeholder="Confirm new password" />
          </Form.Item>

          <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
            <Space>
              <Button onClick={() => {
                setPasswordModalVisible(false);
                passwordForm.resetFields();
                setSelectedUser(null);
              }}>
                Cancel
              </Button>
              <Button type="primary" htmlType="submit">
                Change Password
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};