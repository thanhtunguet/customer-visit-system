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
  Tag,
  Select,
  Popconfirm
} from 'antd';
import { PlusOutlined, TeamOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { apiClient } from '../services/api';
import { Staff, Site } from '../types/api';
import dayjs from 'dayjs';

const { Title } = Typography;

export const StaffPage: React.FC = () => {
  const [staff, setStaff] = useState<Staff[]>([]);
  const [sites, setSites] = useState<Site[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingStaff, setEditingStaff] = useState<Staff | null>(null);
  const [form] = Form.useForm();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [staffData, sitesData] = await Promise.all([
        apiClient.getStaff(),
        apiClient.getSites()
      ]);
      setStaff(staffData);
      setSites(sitesData);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateStaff = async (values: any) => {
    try {
      if (editingStaff) {
        await apiClient.updateStaff(editingStaff.staff_id, values);
      } else {
        await apiClient.createStaff(values);
      }
      setModalVisible(false);
      setEditingStaff(null);
      form.resetFields();
      await loadData();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save staff member');
    }
  };

  const handleEditStaff = (staffMember: Staff) => {
    setEditingStaff(staffMember);
    form.setFieldsValue({
      name: staffMember.name,
      site_id: staffMember.site_id,
    });
    setModalVisible(true);
  };

  const handleDeleteStaff = async (staffMember: Staff) => {
    try {
      await apiClient.deleteStaff(staffMember.staff_id);
      await loadData();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete staff member');
    }
  };

  const columns = [
    {
      title: 'Staff ID',
      dataIndex: 'staff_id',
      key: 'staff_id',
      render: (text: string) => (
        <Space>
          <TeamOutlined className="text-blue-600" />
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
      title: 'Site',
      dataIndex: 'site_id',
      key: 'site_id',
      render: (siteId?: string) => {
        if (!siteId) return <span className="text-gray-400">All Sites</span>;
        const site = sites.find(s => s.site_id === siteId);
        return site ? site.name : siteId;
      },
    },
    {
      title: 'Status',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (isActive: boolean) => (
        <Tag color={isActive ? 'green' : 'red'}>
          {isActive ? 'Active' : 'Inactive'}
        </Tag>
      ),
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
      title: 'Actions',
      key: 'actions',
      render: (_, staffMember: Staff) => (
        <Space>
          <Button
            icon={<EditOutlined />}
            onClick={() => handleEditStaff(staffMember)}
            size="small"
          >
            Edit
          </Button>
          <Popconfirm
            title="Delete Staff Member"
            description="Are you sure you want to delete this staff member? This will also remove their face recognition data."
            onConfirm={() => handleDeleteStaff(staffMember)}
            okText="Yes"
            cancelText="No"
          >
            <Button
              icon={<DeleteOutlined />}
              danger
              size="small"
            >
              Delete
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  if (error && staff.length === 0) {
    return (
      <Alert
        message="Error Loading Staff"
        description={error}
        type="error"
        showIcon
        action={
          <Button onClick={loadData}>
            Retry
          </Button>
        }
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Title level={2} className="mb-0">Staff</Title>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => {
            setEditingStaff(null);
            form.resetFields();
            setModalVisible(true);
          }}
          className="bg-blue-600"
        >
          Add Staff Member
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
          dataSource={staff}
          rowKey="staff_id"
          loading={loading}
          pagination={{
            total: staff.length,
            pageSize: 10,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `Total ${total} staff members`,
          }}
        />
      </div>

      <Modal
        title={editingStaff ? "Edit Staff Member" : "Add New Staff Member"}
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false);
          setEditingStaff(null);
          form.resetFields();
        }}
        onOk={() => form.submit()}
        confirmLoading={loading}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleCreateStaff}
        >


          <Form.Item
            name="name"
            label="Full Name"
            rules={[{ required: true, message: 'Please input staff name!' }]}
          >
            <Input placeholder="e.g. John Doe" />
          </Form.Item>

          <Form.Item
            name="site_id"
            label="Assigned Site"
          >
            <Select
              placeholder="Select a site (optional)"
              allowClear
              options={sites.map(site => ({ 
                value: site.site_id, 
                label: site.name 
              }))}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};