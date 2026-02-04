import { jsx as _jsx, jsxs as _jsxs } from 'react/jsx-runtime';
import { useState, useEffect, useCallback } from 'react';
import {
  Table,
  Button,
  Modal,
  Form,
  Input,
  Space,
  Popconfirm,
  Typography,
  Alert,
  Switch,
  Card,
  App,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  ShopOutlined,
} from '@ant-design/icons';
import { apiClient } from '../services/api';
import { useTenants } from '../contexts/useTenants';
const { Title } = Typography;
export const TenantsPage = () => {
  const { message } = App.useApp();
  const { tenants, loading, loadTenants, refreshTenants } = useTenants();
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [editingTenant, setEditingTenant] = useState(null);
  const [form] = Form.useForm();
  // Check if current user is system admin
  const [isSystemAdmin, setIsSystemAdmin] = useState(false);
  const [currentUser, setCurrentUser] = useState(null);
  useEffect(() => {
    if (isSystemAdmin) {
      loadTenants();
    }
  }, [isSystemAdmin, loadTenants]);
  const checkUserRole = useCallback(async () => {
    try {
      const user = await apiClient.getCurrentUser();
      setCurrentUser(user);
      setIsSystemAdmin(user.role === 'system_admin');
    } catch (error) {
      console.error('Failed to get current user:', error);
      message.error('Failed to verify user role');
    }
  }, [message]);
  useEffect(() => {
    checkUserRole();
  }, [checkUserRole]);
  const showModal = (tenant) => {
    setEditingTenant(tenant || null);
    setIsModalVisible(true);
    if (tenant) {
      form.setFieldsValue({
        tenant_id: tenant.tenant_id,
        name: tenant.name,
        description: tenant.description,
      });
    } else {
      form.resetFields();
    }
  };
  const handleCancel = () => {
    setIsModalVisible(false);
    setEditingTenant(null);
    form.resetFields();
  };
  const handleSubmit = async (values) => {
    try {
      if (editingTenant) {
        await apiClient.updateTenant(editingTenant.tenant_id, values);
        message.success('Tenant updated successfully');
      } else {
        await apiClient.createTenant(values);
        message.success('Tenant created successfully');
      }
      setIsModalVisible(false);
      setEditingTenant(null);
      form.resetFields();
      refreshTenants();
    } catch (error) {
      const axiosError = error;
      message.error(
        axiosError.response?.data?.detail || 'Failed to save tenant'
      );
    }
  };
  const handleDelete = async (tenantId) => {
    try {
      await apiClient.deleteTenant(tenantId);
      message.success('Tenant deleted successfully');
      refreshTenants();
    } catch (error) {
      const axiosError = error;
      message.error(
        axiosError.response?.data?.detail || 'Failed to delete tenant'
      );
    }
  };
  const handleToggleStatus = async (tenantId, currentStatus) => {
    const newStatus = !currentStatus;
    const action = newStatus ? 'activate' : 'deactivate';
    Modal.confirm({
      title: `${action.charAt(0).toUpperCase() + action.slice(1)} Tenant`,
      content: `Are you sure you want to ${action} this tenant? This will ${newStatus ? 'enable' : 'disable'} all operations for this tenant organization.`,
      okText: `Yes, ${action.charAt(0).toUpperCase() + action.slice(1)}`,
      cancelText: 'Cancel',
      okButtonProps: {
        danger: !newStatus, // Red button for deactivation
        type: newStatus ? 'primary' : 'default',
      },
      onOk: async () => {
        try {
          await apiClient.toggleTenantStatus(tenantId, newStatus);
          message.success(`Tenant ${action}d successfully`);
          refreshTenants();
        } catch (error) {
          const axiosError = error;
          message.error(
            axiosError.response?.data?.detail || `Failed to ${action} tenant`
          );
        }
      },
    });
  };
  // If not system admin, show access denied
  if (!isSystemAdmin) {
    return _jsx('div', {
      className: 'p-6',
      children: _jsxs(Card, {
        children: [
          _jsx(Alert, {
            message: 'Access Denied',
            description:
              'Only system administrators can manage tenants. Your current role is insufficient to access this page.',
            type: 'error',
            showIcon: true,
            className: 'mb-4',
          }),
          _jsxs('div', {
            className: 'text-sm text-gray-600',
            children: [
              _jsxs('p', {
                children: [
                  _jsx('strong', { children: 'Current User:' }),
                  ' ',
                  currentUser?.sub || 'Unknown',
                ],
              }),
              _jsxs('p', {
                children: [
                  _jsx('strong', { children: 'Role:' }),
                  ' ',
                  currentUser?.role || 'Unknown',
                ],
              }),
              _jsxs('p', {
                children: [
                  _jsx('strong', { children: 'Tenant:' }),
                  ' ',
                  currentUser?.tenant_id || 'Unknown',
                ],
              }),
            ],
          }),
        ],
      }),
    });
  }
  const columns = [
    {
      title: 'Tenant ID',
      dataIndex: 'tenant_id',
      key: 'tenant_id',
      render: (text) =>
        _jsx('span', { className: 'font-mono text-sm', children: text }),
    },
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (text) =>
        _jsx('span', { className: 'font-medium', children: text }),
    },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
      render: (text) =>
        text ||
        _jsx('span', { className: 'text-gray-400', children: '\u2014' }),
    },
    {
      title: 'Status',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (isActive, record) =>
        _jsx('div', {
          className: 'flex items-center gap-2',
          children: _jsx(Switch, {
            checked: isActive,
            onChange: () => handleToggleStatus(record.tenant_id, isActive),
            checkedChildren: 'Active',
            unCheckedChildren: 'Inactive',
            size: 'small',
          }),
        }),
    },
    {
      title: 'Created At',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (text) => new Date(text).toLocaleDateString(),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 150,
      render: (_, record) =>
        _jsxs(Space, {
          size: 'small',
          children: [
            _jsx(Button, {
              type: 'text',
              icon: _jsx(EditOutlined, {}),
              onClick: () => showModal(record),
              title: 'Edit Tenant',
            }),
            _jsx(Popconfirm, {
              title: 'Delete Tenant',
              description: `Are you sure you want to delete tenant "${record.name}"? This action cannot be undone and will affect all associated data.`,
              onConfirm: () => handleDelete(record.tenant_id),
              okText: 'Yes, Delete',
              cancelText: 'Cancel',
              okButtonProps: { danger: true },
              children: _jsx(Button, {
                type: 'text',
                danger: true,
                icon: _jsx(DeleteOutlined, {}),
                title: 'Delete Tenant',
              }),
            }),
          ],
        }),
    },
  ];
  return _jsxs('div', {
    className: 'p-6',
    children: [
      _jsxs('div', {
        className: 'flex justify-between items-center mb-6',
        children: [
          _jsxs('div', {
            children: [
              _jsxs(Title, {
                level: 2,
                className: 'flex items-center gap-2 mb-0',
                children: [_jsx(ShopOutlined, {}), 'Tenant Management'],
              }),
              _jsx('p', {
                className: 'text-gray-600 mt-1',
                children:
                  'Manage tenant organizations and their configurations',
              }),
            ],
          }),
          _jsx(Button, {
            type: 'primary',
            icon: _jsx(PlusOutlined, {}),
            onClick: () => showModal(),
            size: 'large',
            children: 'Create Tenant',
          }),
        ],
      }),
      _jsx(Card, {
        children: _jsx(Table, {
          columns: columns,
          dataSource: tenants,
          loading: loading,
          rowKey: 'tenant_id',
          pagination: {
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total, range) =>
              `${range[0]}-${range[1]} of ${total} tenants`,
          },
        }),
      }),
      _jsx(Modal, {
        title: _jsxs('div', {
          className: 'flex items-center gap-2',
          children: [
            _jsx(ShopOutlined, {}),
            editingTenant ? 'Edit Tenant' : 'Create New Tenant',
          ],
        }),
        open: isModalVisible,
        onCancel: handleCancel,
        footer: null,
        width: 600,
        children: _jsxs(Form, {
          form: form,
          layout: 'vertical',
          onFinish: handleSubmit,
          className: 'mt-4',
          children: [
            _jsx(Form.Item, {
              name: 'tenant_id',
              label: 'Tenant ID',
              rules: [
                { required: true, message: 'Please enter tenant ID' },
                {
                  pattern: /^[a-z0-9-]+$/,
                  message:
                    'Tenant ID can only contain lowercase letters, numbers, and hyphens',
                },
                { min: 2, message: 'Tenant ID must be at least 2 characters' },
                {
                  max: 50,
                  message: 'Tenant ID must be less than 50 characters',
                },
              ],
              extra:
                "Unique identifier for the tenant (e.g., 'acme-corp', 'demo-tenant')",
              children: _jsx(Input, {
                placeholder: 'e.g., acme-corp',
                disabled: !!editingTenant,
              }),
            }),
            _jsx(Form.Item, {
              name: 'name',
              label: 'Tenant Name',
              rules: [
                { required: true, message: 'Please enter tenant name' },
                { min: 2, message: 'Name must be at least 2 characters' },
                { max: 100, message: 'Name must be less than 100 characters' },
              ],
              children: _jsx(Input, { placeholder: 'e.g., Acme Corporation' }),
            }),
            _jsx(Form.Item, {
              name: 'description',
              label: 'Description',
              rules: [
                {
                  max: 500,
                  message: 'Description must be less than 500 characters',
                },
              ],
              children: _jsx(Input.TextArea, {
                placeholder: 'Brief description of the tenant organization...',
                rows: 3,
              }),
            }),
            _jsxs('div', {
              className: 'flex justify-end gap-2 pt-4',
              children: [
                _jsx(Button, { onClick: handleCancel, children: 'Cancel' }),
                _jsx(Button, {
                  type: 'primary',
                  htmlType: 'submit',
                  children: editingTenant ? 'Update Tenant' : 'Create Tenant',
                }),
              ],
            }),
          ],
        }),
      }),
    ],
  });
};
