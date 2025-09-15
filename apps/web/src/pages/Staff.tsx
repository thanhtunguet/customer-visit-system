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
} from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { apiClient } from '../services/api';
import { Staff, Site, StaffCreate } from '../types/api';
import { StaffDetailsModal } from '../components/StaffDetailsModal';
import { ViewAction, EditAction, DeleteAction } from '../components/TableActionButtons';
import dayjs from 'dayjs';

const { Title } = Typography;

export const StaffPage: React.FC = () => {
  const [staff, setStaff] = useState<Staff[]>([]);
  const [sites, setSites] = useState<Site[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalVisible, setModalVisible] = useState(false);
  const [detailsModalVisible, setDetailsModalVisible] = useState(false);
  const [selectedStaffId, setSelectedStaffId] = useState<number | null>(null);
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

  const handleCreateStaff = async (values: StaffCreate) => {
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

  const handleViewDetails = (staffMember: Staff) => {
    setSelectedStaffId(staffMember.staff_id);
    setDetailsModalVisible(true);
  };

  const handleEditStaff = (staffMember: Staff) => {
    setEditingStaff(staffMember);
    form.setFieldsValue({
      name: staffMember.name,
      site_id: staffMember.site_id,
    });
    setModalVisible(true);
  };

  const handleEditFromDetails = (staffId: number) => {
    const staffMember = staff.find(s => s.staff_id === staffId);
    if (staffMember) {
      setDetailsModalVisible(false);
      handleEditStaff(staffMember);
    }
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
      title: 'ID',
      dataIndex: 'staff_id',
      key: 'staff_id',
      width: 80,
      render: (id: number) => (
        <span className="font-mono text-gray-600">#{id}</span>
      ),
    },
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: Staff) => (
        <Button 
          type="link" 
          className="p-0 h-auto font-medium text-left"
          onClick={() => handleViewDetails(record)}
        >
          {text}
        </Button>
      ),
    },
    {
      title: 'Site',
      dataIndex: 'site_id',
      key: 'site_id',
      render: (siteId?: number) => {
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
      width: 120,
      fixed: 'right' as const,
      render: (_, staffMember: Staff) => (
        <Space size="small">
          <ViewAction
            onClick={() => handleViewDetails(staffMember)}
            tooltip="View details & manage face images"
          />
          <EditAction
            onClick={() => handleEditStaff(staffMember)}
            tooltip="Edit staff member"
          />
          <DeleteAction
            onConfirm={() => handleDeleteStaff(staffMember)}
            title="Delete Staff Member"
            description="Are you sure you want to delete this staff member? This will also remove their face recognition data."
            tooltip="Delete staff member"
          />
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
        <Title level={2} className="mb-0">Staff Management</Title>
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

      {/* Add/Edit Staff Modal */}
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

      {/* Staff Details Modal */}
      <StaffDetailsModal
        visible={detailsModalVisible}
        staffId={selectedStaffId}
        onClose={() => {
          setDetailsModalVisible(false);
          setSelectedStaffId(null);
        }}
        onEdit={handleEditFromDetails}
      />
    </div>
  );
};
