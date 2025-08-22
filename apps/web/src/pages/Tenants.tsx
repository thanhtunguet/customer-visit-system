import React, { useState, useEffect, useCallback } from 'react';
import {
  Table, Button, Modal, Form, Input, Space, message, Popconfirm, 
  Tag, Typography, Alert, Switch, Card
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, ShopOutlined
} from '@ant-design/icons';
import { ColumnsType } from 'antd/es/table';
import { Tenant, TenantCreate } from '../types/api';
import { apiClient } from '../services/api';

const { Title } = Typography;

export const TenantsPage: React.FC = () => {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [editingTenant, setEditingTenant] = useState<Tenant | null>(null);
  const [form] = Form.useForm();

  // Check if current user is system admin
  const [isSystemAdmin, setIsSystemAdmin] = useState(false);
  const [currentUser, setCurrentUser] = useState<any>(null);

  useEffect(() => {
    checkUserRole();
  }, []);

  useEffect(() => {
    if (isSystemAdmin) {
      fetchTenants();
    }
  }, [isSystemAdmin]);

  const checkUserRole = async () => {
    try {
      const user = await apiClient.getCurrentUser();
      setCurrentUser(user);
      setIsSystemAdmin(user.role === 'system_admin');
    } catch (error) {
      console.error('Failed to get current user:', error);
      message.error('Failed to verify user role');
    }
  };

  const fetchTenants = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiClient.getTenants();
      setTenants(data);
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Failed to fetch tenants');
    } finally {
      setLoading(false);
    }
  }, []);

  const showModal = (tenant?: Tenant) => {
    setEditingTenant(tenant || null);
    setIsModalVisible(true);
    
    if (tenant) {
      form.setFieldsValue({
        tenant_id: tenant.tenant_id,
        name: tenant.name,
        description: tenant.description
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

  const handleSubmit = async (values: TenantCreate) => {
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
      fetchTenants();
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Failed to save tenant');
    }
  };

  const handleDelete = async (tenantId: string) => {
    try {
      await apiClient.deleteTenant(tenantId);
      message.success('Tenant deleted successfully');
      fetchTenants();
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Failed to delete tenant');
    }
  };

  const handleToggleStatus = async (tenantId: string, currentStatus: boolean) => {
    const newStatus = !currentStatus;
    const action = newStatus ? 'activate' : 'deactivate';
    
    Modal.confirm({
      title: `${action.charAt(0).toUpperCase() + action.slice(1)} Tenant`,
      content: `Are you sure you want to ${action} this tenant? This will ${newStatus ? 'enable' : 'disable'} all operations for this tenant organization.`,
      okText: `Yes, ${action.charAt(0).toUpperCase() + action.slice(1)}`,
      cancelText: 'Cancel',
      okButtonProps: { 
        danger: !newStatus,  // Red button for deactivation
        type: newStatus ? 'primary' : 'default'
      },
      onOk: async () => {
        try {
          await apiClient.toggleTenantStatus(tenantId, newStatus);
          message.success(`Tenant ${action}d successfully`);
          fetchTenants();
        } catch (error: any) {
          message.error(error.response?.data?.detail || `Failed to ${action} tenant`);
        }
      }
    });
  };

  // If not system admin, show access denied
  if (!isSystemAdmin) {
    return (
      <div className="p-6">
        <Card>
          <Alert
            message="Access Denied"
            description="Only system administrators can manage tenants. Your current role is insufficient to access this page."
            type="error"
            showIcon
            className="mb-4"
          />
          <div className="text-sm text-gray-600">
            <p><strong>Current User:</strong> {currentUser?.sub || 'Unknown'}</p>
            <p><strong>Role:</strong> {currentUser?.role || 'Unknown'}</p>
            <p><strong>Tenant:</strong> {currentUser?.tenant_id || 'Unknown'}</p>
          </div>
        </Card>
      </div>
    );
  }

  const columns: ColumnsType<Tenant> = [
    {
      title: 'Tenant ID',
      dataIndex: 'tenant_id',
      key: 'tenant_id',
      render: (text: string) => (
        <span className="font-mono text-sm">{text}</span>
      ),
    },
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (text: string) => (
        <span className="font-medium">{text}</span>
      ),
    },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
      render: (text?: string) => text || <span className="text-gray-400">—</span>,
    },
    {
      title: 'Status',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (isActive: boolean, record: Tenant) => (
        <div className="flex items-center gap-2">
          <Switch
            checked={isActive}
            onChange={() => handleToggleStatus(record.tenant_id, isActive)}
            checkedChildren="Active"
            unCheckedChildren="Inactive"
            size="small"
          />
        </div>
      ),
    },
    {
      title: 'Created At',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (text: string) => new Date(text).toLocaleDateString(),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 150,
      render: (_, record) => (
        <Space size="small">
          <Button
            type="text"
            icon={<EditOutlined />}
            onClick={() => showModal(record)}
            title="Edit Tenant"
          />
          <Popconfirm
            title="Delete Tenant"
            description={`Are you sure you want to delete tenant "${record.name}"? This action cannot be undone and will affect all associated data.`}
            onConfirm={() => handleDelete(record.tenant_id)}
            okText="Yes, Delete"
            cancelText="Cancel"
            okButtonProps={{ danger: true }}
          >
            <Button
              type="text"
              danger
              icon={<DeleteOutlined />}
              title="Delete Tenant"
            />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <Title level={2} className="flex items-center gap-2 mb-0">
            <ShopOutlined />
            Tenant Management
          </Title>
          <p className="text-gray-600 mt-1">
            Manage tenant organizations and their configurations
          </p>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => showModal()}
          size="large"
        >
          Create Tenant
        </Button>
      </div>

      <Card>
        <Table
          columns={columns}
          dataSource={tenants}
          loading={loading}
          rowKey="tenant_id"
          pagination={{
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total, range) =>
              `${range[0]}-${range[1]} of ${total} tenants`,
          }}
        />
      </Card>

      <Modal
        title={
          <div className="flex items-center gap-2">
            <ShopOutlined />
            {editingTenant ? 'Edit Tenant' : 'Create New Tenant'}
          </div>
        }
        open={isModalVisible}
        onCancel={handleCancel}
        footer={null}
        width={600}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          className="mt-4"
        >
          <Form.Item
            name="tenant_id"
            label="Tenant ID"
            rules={[
              { required: true, message: 'Please enter tenant ID' },
              { 
                pattern: /^[a-z0-9-]+$/, 
                message: 'Tenant ID can only contain lowercase letters, numbers, and hyphens' 
              },
              { min: 2, message: 'Tenant ID must be at least 2 characters' },
              { max: 50, message: 'Tenant ID must be less than 50 characters' }
            ]}
            extra="Unique identifier for the tenant (e.g., 'acme-corp', 'demo-tenant')"
          >
            <Input
              placeholder="e.g., acme-corp"
              disabled={!!editingTenant}
            />
          </Form.Item>

          <Form.Item
            name="name"
            label="Tenant Name"
            rules={[
              { required: true, message: 'Please enter tenant name' },
              { min: 2, message: 'Name must be at least 2 characters' },
              { max: 100, message: 'Name must be less than 100 characters' }
            ]}
          >
            <Input placeholder="e.g., Acme Corporation" />
          </Form.Item>

          <Form.Item
            name="description"
            label="Description"
            rules={[
              { max: 500, message: 'Description must be less than 500 characters' }
            ]}
          >
            <Input.TextArea
              placeholder="Brief description of the tenant organization..."
              rows={3}
            />
          </Form.Item>

          <div className="flex justify-end gap-2 pt-4">
            <Button onClick={handleCancel}>
              Cancel
            </Button>
            <Button type="primary" htmlType="submit">
              {editingTenant ? 'Update Tenant' : 'Create Tenant'}
            </Button>
          </div>
        </Form>
      </Modal>
    </div>
  );
};