import React, { useState, useEffect } from 'react';
import { App } from 'antd';
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
  DatePicker,
  Typography,
  Card,
  Alert,
  Tooltip,
  Switch
} from 'antd';
import { 
  PlusOutlined, 
  EditOutlined, 
  DeleteOutlined, 
  KeyOutlined,
  CopyOutlined,
  EyeOutlined,
  EyeInvisibleOutlined
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';

import { apiClient } from '../services/api';
import { ApiKey, ApiKeyCreate, ApiKeyCreateResponse, ApiKeyUpdate } from '../types/api';

const { Option } = Select;
const { Text } = Typography;

const ApiKeys: React.FC = () => {
  const { message } = App.useApp();
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(false);
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [keyDisplayModalVisible, setKeyDisplayModalVisible] = useState(false);
  const [selectedApiKey, setSelectedApiKey] = useState<ApiKey | null>(null);
  const [newApiKeyData, setNewApiKeyData] = useState<ApiKeyCreateResponse | null>(null);
  const [showApiKey, setShowApiKey] = useState(false);

  const [createForm] = Form.useForm<ApiKeyCreate>();
  const [editForm] = Form.useForm<ApiKeyUpdate>();

  useEffect(() => {
    // Add a small delay to ensure tenant context is properly set
    const timer = setTimeout(() => {
      loadApiKeys();
    }, 100);
    
    return () => clearTimeout(timer);
  }, []);

  const loadApiKeys = async () => {
    setLoading(true);
    try {

      
      const data = await apiClient.getApiKeys();
      setApiKeys(data);
    } catch (error: any) {
      console.error('API Keys load error:', error.response?.data || error.message);
      if (error.response?.status === 400) {
        message.error('Please switch to a tenant view to manage API keys');
      } else {
        message.error('Failed to load API keys: ' + (error.response?.data?.detail || error.message));
      }
    } finally {
      setLoading(false);
    }
  };

  const handleCreateApiKey = async (values: ApiKeyCreate) => {
    try {
      // Convert dayjs to ISO string if expires_at is provided
      const payload = {
        ...values,
        expires_at: values.expires_at ? values.expires_at.toISOString() : undefined
      };
      
      console.log('Creating API key with payload:', payload);
      const newApiKey = await apiClient.createApiKey(payload);
      setNewApiKeyData(newApiKey);
      setCreateModalVisible(false);
      setKeyDisplayModalVisible(true);
      createForm.resetFields();
      message.success('API key created successfully!');
      loadApiKeys();
    } catch (error: any) {
      console.error('API key creation error:', error);
      const errorMessage = error.response?.data?.detail || error.message || 'Unknown error';
      message.error('Failed to create API key: ' + errorMessage);
    }
  };

  const handleUpdateApiKey = async (values: ApiKeyUpdate) => {
    if (!selectedApiKey) return;
    
    try {
      await apiClient.updateApiKey(selectedApiKey.key_id, values);
      setEditModalVisible(false);
      setSelectedApiKey(null);
      editForm.resetFields();
      message.success('API key updated successfully!');
      loadApiKeys();
    } catch (error: any) {
      message.error('Failed to update API key: ' + error.message);
    }
  };

  const handleDeleteApiKey = async (keyId: string) => {
    try {
      await apiClient.deleteApiKey(keyId);
      message.success('API key deleted successfully!');
      loadApiKeys();
    } catch (error: any) {
      message.error('Failed to delete API key: ' + error.message);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text).then(() => {
      message.success('Copied to clipboard!');
    }).catch(() => {
      message.error('Failed to copy to clipboard');
    });
  };

  const formatLastUsed = (lastUsed: string | undefined) => {
    if (!lastUsed) return 'Never';
    return dayjs(lastUsed).format('MMM D, YYYY HH:mm');
  };

  const isExpired = (expiresAt: string | undefined) => {
    if (!expiresAt) return false;
    return dayjs(expiresAt).isBefore(dayjs());
  };

  const getStatusTag = (apiKey: ApiKey) => {
    if (!apiKey.is_active) {
      return <Tag color="red">Inactive</Tag>;
    }
    if (isExpired(apiKey.expires_at)) {
      return <Tag color="orange">Expired</Tag>;
    }
    return <Tag color="green">Active</Tag>;
  };

  const columns: ColumnsType<ApiKey> = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (text, record) => (
        <Space>
          <KeyOutlined />
          <strong>{text}</strong>
        </Space>
      ),
    },
    {
      title: 'Role',
      dataIndex: 'role',
      key: 'role',
      render: (role: string) => (
        <Tag color={role === 'worker' ? 'blue' : 'purple'}>
          {role.toUpperCase()}
        </Tag>
      ),
    },
    {
      title: 'Status',
      key: 'status',
      render: (_, record) => getStatusTag(record),
    },
    {
      title: 'Last Used',
      dataIndex: 'last_used',
      key: 'last_used',
      render: (lastUsed) => (
        <Text type={lastUsed ? 'default' : 'secondary'}>
          {formatLastUsed(lastUsed)}
        </Text>
      ),
    },
    {
      title: 'Expires',
      dataIndex: 'expires_at',
      key: 'expires_at',
      render: (expiresAt) => {
        if (!expiresAt) return <Text type="secondary">Never</Text>;
        const expired = isExpired(expiresAt);
        return (
          <Text type={expired ? 'danger' : 'default'}>
            {dayjs(expiresAt).format('MMM D, YYYY')}
          </Text>
        );
      },
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (createdAt) => dayjs(createdAt).format('MMM D, YYYY'),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_, record) => (
        <Space>
          <Tooltip title="Edit API Key" key="edit">
            <Button
              type="text"
              icon={<EditOutlined />}
              onClick={() => {
                setSelectedApiKey(record);
                editForm.setFieldsValue({
                  name: record.name,
                  is_active: record.is_active,
                  expires_at: record.expires_at ? dayjs(record.expires_at) : undefined,
                });
                setEditModalVisible(true);
              }}
            />
          </Tooltip>
          <Tooltip title="Delete API Key" key="delete">
            <Popconfirm
              title="Delete API Key"
              description="Are you sure you want to delete this API key? This action cannot be undone."
              onConfirm={() => handleDeleteApiKey(record.key_id)}
              okText="Yes"
              cancelText="No"
            >
              <Button
                type="text"
                danger
                icon={<DeleteOutlined />}
              />
            </Popconfirm>
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Card>
        {apiKeys.length === 0 && !loading && (
          <Alert
            message="No API Keys Found"
            description="If you're a system administrator, please switch to a tenant view to manage API keys. Only tenant administrators and system admins in tenant context can manage API keys."
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />
        )}
        
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div>
            <h2>API Key Management</h2>
            <p>Manage API keys for worker authentication and system integration.</p>
          </div>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setCreateModalVisible(true)}
          >
            Create API Key
          </Button>
        </div>

        <Table
          columns={columns}
          dataSource={apiKeys}
          rowKey="key_id"
          loading={loading}
          pagination={{
            pageSize: 10,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `Total ${total} API keys`,
          }}
        />
      </Card>

      {/* Create API Key Modal */}
      <Modal
        title="Create New API Key"
        open={createModalVisible}
        onCancel={() => {
          setCreateModalVisible(false);
          createForm.resetFields();
        }}
        footer={null}
      >
        <Form
          form={createForm}
          layout="vertical"
          onFinish={handleCreateApiKey}
        >
          <Form.Item
            name="name"
            label="API Key Name"
            rules={[{ required: true, message: 'Please enter API key name' }]}
          >
            <Input placeholder="e.g., Production Worker Key" />
          </Form.Item>

          <Form.Item
            name="role"
            label="Role"
            initialValue="worker"
          >
            <Select>
              <Option value="worker">Worker</Option>
            </Select>
          </Form.Item>

          <Form.Item
            name="expires_at"
            label="Expiration Date (Optional)"
          >
            <DatePicker
              style={{ width: '100%' }}
              placeholder="Select expiration date"
              disabledDate={(current) => current && current < dayjs().endOf('day')}
            />
          </Form.Item>

          <Form.Item>
            <Space>
              <Button key="create" type="primary" htmlType="submit">
                Create API Key
              </Button>
              <Button key="cancel" onClick={() => {
                setCreateModalVisible(false);
                createForm.resetFields();
              }}>
                Cancel
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* Edit API Key Modal */}
      <Modal
        title="Edit API Key"
        open={editModalVisible}
        onCancel={() => {
          setEditModalVisible(false);
          setSelectedApiKey(null);
          editForm.resetFields();
        }}
        footer={null}
      >
        <Form
          form={editForm}
          layout="vertical"
          onFinish={handleUpdateApiKey}
        >
          <Form.Item
            name="name"
            label="API Key Name"
            rules={[{ required: true, message: 'Please enter API key name' }]}
          >
            <Input placeholder="e.g., Production Worker Key" />
          </Form.Item>

          <Form.Item
            name="is_active"
            label="Status"
            valuePropName="checked"
          >
            <Switch checkedChildren="Active" unCheckedChildren="Inactive" />
          </Form.Item>

          <Form.Item
            name="expires_at"
            label="Expiration Date"
          >
            <DatePicker
              style={{ width: '100%' }}
              placeholder="Select expiration date"
              disabledDate={(current) => current && current < dayjs().endOf('day')}
            />
          </Form.Item>

          <Form.Item>
            <Space>
              <Button key="update" type="primary" htmlType="submit">
                Update API Key
              </Button>
              <Button key="cancel" onClick={() => {
                setEditModalVisible(false);
                setSelectedApiKey(null);
                editForm.resetFields();
              }}>
                Cancel
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* New API Key Display Modal */}
      <Modal
        title="API Key Created Successfully!"
        open={keyDisplayModalVisible}
        onCancel={() => {
          setKeyDisplayModalVisible(false);
          setNewApiKeyData(null);
          setShowApiKey(false);
        }}
        footer={[
          <Button key="close" onClick={() => {
            setKeyDisplayModalVisible(false);
            setNewApiKeyData(null);
            setShowApiKey(false);
          }}>
            Close
          </Button>
        ]}
        closable={false}
        maskClosable={false}
      >
        {newApiKeyData && (
          <div>
            <Alert
              message="Important: Save this API key now!"
              description="This is the only time you'll be able to see the complete API key. Store it in a secure location."
              type="warning"
              showIcon
              style={{ marginBottom: 16 }}
            />
            
            <div style={{ marginBottom: 16 }}>
              <strong>API Key Name:</strong> {newApiKeyData.name}
            </div>
            
            <div style={{ marginBottom: 16 }}>
              <strong>Role:</strong> <Tag color="blue">{newApiKeyData.role.toUpperCase()}</Tag>
            </div>
            
            <div style={{ marginBottom: 16 }}>
              <strong>API Key:</strong>
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: 8, 
                marginTop: 8,
                padding: 12,
                backgroundColor: '#f5f5f5',
                borderRadius: 6,
                border: '1px solid #d9d9d9'
              }}>
                <Input.Password
                  value={newApiKeyData.api_key}
                  readOnly
                  visibilityToggle={{
                    visible: showApiKey,
                    onVisibleChange: setShowApiKey,
                  }}
                  style={{ flex: 1 }}
                />
                <Button
                  icon={<CopyOutlined />}
                  onClick={() => copyToClipboard(newApiKeyData.api_key)}
                  title="Copy to clipboard"
                />
              </div>
            </div>
            
            {newApiKeyData.expires_at && (
              <div>
                <strong>Expires:</strong> {dayjs(newApiKeyData.expires_at).format('MMMM D, YYYY')}
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
};

export { ApiKeys };
export default ApiKeys;