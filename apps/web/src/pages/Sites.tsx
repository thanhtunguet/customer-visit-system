import React, { useEffect, useState } from 'react';
import { 
  Table, 
  Button, 
  Modal, 
  Form, 
  Input, 
  Typography, 
  Space, 
  Alert,
  Tag
} from 'antd';
import { PlusOutlined, ShopOutlined } from '@ant-design/icons';
import { apiClient } from '../services/api';
import { Site } from '../types/api';
import dayjs from 'dayjs';

const { Title } = Typography;

export const Sites: React.FC = () => {
  const [sites, setSites] = useState<Site[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalVisible, setModalVisible] = useState(false);
  const [form] = Form.useForm();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadSites();
  }, []);

  const loadSites = async () => {
    try {
      setLoading(true);
      setError(null);
      const sitesData = await apiClient.getSites();
      setSites(sitesData);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load sites');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateSite = async (values: any) => {
    try {
      await apiClient.createSite(values);
      setModalVisible(false);
      form.resetFields();
      await loadSites();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create site');
    }
  };

  const columns = [
    {
      title: 'Site ID',
      dataIndex: 'site_id',
      key: 'site_id',
      render: (text: string) => (
        <Space>
          <ShopOutlined className="text-blue-600" />
          <span className="font-mono">{text}</span>
        </Space>
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
      title: 'Location',
      dataIndex: 'location',
      key: 'location',
      render: (text?: string) => text || <span className="text-gray-400">-</span>,
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => (
        <span className="text-gray-600">
          {dayjs(date).format('MMM D, YYYY')}
        </span>
      ),
    },
    {
      title: 'Status',
      key: 'status',
      render: () => (
        <Tag color="green">Active</Tag>
      ),
    },
  ];

  if (error && sites.length === 0) {
    return (
      <Alert
        message="Error Loading Sites"
        description={error}
        type="error"
        showIcon
        action={
          <Button onClick={loadSites}>
            Retry
          </Button>
        }
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Title level={2} className="mb-0">Sites</Title>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setModalVisible(true)}
          className="bg-blue-600"
        >
          Add Site
        </Button>
      </div>

      {error && (
        <Alert
          message={error}
          type="error"
          closable
          onClose={() => setError(null)}
        />
      )}

      <div className="bg-white rounded-lg shadow">
        <Table
          columns={columns}
          dataSource={sites}
          rowKey="site_id"
          loading={loading}
          pagination={{
            total: sites.length,
            pageSize: 10,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `Total ${total} sites`,
          }}
        />
      </div>

      <Modal
        title="Add New Site"
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false);
          form.resetFields();
        }}
        onOk={() => form.submit()}
        confirmLoading={loading}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleCreateSite}
        >
          <Form.Item
            name="site_id"
            label="Site ID"
            rules={[
              { required: true, message: 'Please input site ID!' },
              { pattern: /^[a-z0-9-]+$/, message: 'Site ID can only contain lowercase letters, numbers, and hyphens' }
            ]}
          >
            <Input placeholder="e.g. main-office" />
          </Form.Item>

          <Form.Item
            name="name"
            label="Site Name"
            rules={[{ required: true, message: 'Please input site name!' }]}
          >
            <Input placeholder="e.g. Main Office" />
          </Form.Item>

          <Form.Item
            name="location"
            label="Location"
          >
            <Input placeholder="e.g. 123 Main St, City, State" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};