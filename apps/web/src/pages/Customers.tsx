import { PlusOutlined, UserOutlined, EyeOutlined, ReloadOutlined, UploadOutlined } from '@ant-design/icons';
import { Typography, Form, Input, Button, Table, Modal, Select, Space, Alert } from 'antd';
import { apiClient } from '../services/api';
import { EditAction, DeleteAction } from '../components/TableActionButtons';
import { CustomerDetailsModal } from '../components/CustomerDetailsModal';
import { AuthenticatedAvatar } from '../components/AuthenticatedAvatar';
import { ImageUploadModal } from '../components/ImageUploadModal';
import { Customer, CustomerCreate } from '../types/api';
import dayjs from 'dayjs';
import { useState, useEffect } from 'react';
const { Title } = Typography;

export const Customers: React.FC = () => {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingCustomer, setEditingCustomer] = useState<Customer | null>(null);
  const [form] = Form.useForm();
  const [error, setError] = useState<string | null>(null);
  
  // Details modal state
  const [detailsModalVisible, setDetailsModalVisible] = useState(false);
  const [selectedCustomerId, setSelectedCustomerId] = useState<number | null>(null);
  
  // Backfill state
  const [backfillLoading, setBackfillLoading] = useState<Set<number>>(new Set());
  
  // Upload images modal state
  const [uploadModalVisible, setUploadModalVisible] = useState(false);

  useEffect(() => {
    loadCustomers();
  }, []);

  const loadCustomers = async () => {
    try {
      setLoading(true);
      setError(null);
      const customersData = await apiClient.getCustomers({ limit: 1000 });
      setCustomers(customersData);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load customers');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateCustomer = async (values: CustomerCreate) => {
    try {
      if (editingCustomer) {
        await apiClient.updateCustomer(editingCustomer.customer_id, values);
      } else {
        await apiClient.createCustomer(values);
      }
      setModalVisible(false);
      setEditingCustomer(null);
      form.resetFields();
      await loadCustomers();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save customer');
    }
  };

  const handleEditCustomer = (customer: Customer) => {
    setEditingCustomer(customer);
    form.setFieldsValue({
      name: customer.name,
      gender: customer.gender,
      phone: customer.phone,
      email: customer.email,
    });
    setModalVisible(true);
  };

  const handleDeleteCustomer = async (customer: Customer) => {
    try {
      await apiClient.deleteCustomer(customer.customer_id);
      await loadCustomers();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete customer');
    }
  };

  const handleViewDetails = (customer: Customer) => {
    setSelectedCustomerId(customer.customer_id);
    setDetailsModalVisible(true);
  };

  const handleDetailsModalEdit = (customerId: number) => {
    // Find customer and open edit modal
    const customer = customers.find(c => c.customer_id === customerId);
    if (customer) {
      setDetailsModalVisible(false);
      handleEditCustomer(customer);
    }
  };

  const handleBackfillAvatar = async (customer: Customer) => {
    setBackfillLoading(prev => new Set([...prev, customer.customer_id]));
    
    try {
      const result = await apiClient.backfillCustomerFaceImages(customer.customer_id);
      
      if (result.visits_processed > 0) {
        setError(null);
        // Reload customers to show updated avatars
        await loadCustomers();
        // You could also show a success message here
        console.log(`✅ Backfilled ${result.visits_processed} face images for customer ${customer.customer_id}`);
      } else {
        setError(`No face images found to backfill for customer ${customer.name || customer.customer_id}`);
      }
    } catch (err: any) {
      console.error('Backfill failed:', err);
      setError(err.response?.data?.detail || `Failed to backfill avatar for customer ${customer.name || customer.customer_id}`);
    } finally {
      setBackfillLoading(prev => {
        const newSet = new Set(prev);
        newSet.delete(customer.customer_id);
        return newSet;
      });
    }
  };

  const columns = [
    {
      title: 'Avatar',
      dataIndex: 'avatar_url',
      key: 'avatar',
      width: 60,
      render: (avatar_url: string, customer: Customer) => (
        <AuthenticatedAvatar
          src={avatar_url}
          size={40}
          className="flex-shrink-0"
          alt={`${customer.name || 'Customer'} Avatar`}
          icon={<UserOutlined />}
        />
      ),
    },
    {
      title: 'ID',
      dataIndex: 'customer_id',
      key: 'customer_id',
      width: 80,
      render: (id: number) => (
        <span className="font-mono text-gray-600">#{id}</span>
      ),
    },
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (text?: string) => (
        <span className="font-medium">{text || <span className="text-gray-400 italic">Unknown</span>}</span>
      ),
    },
    {
      title: 'Gender',
      dataIndex: 'gender',
      key: 'gender',
      render: (gender?: string) => {
        if (!gender) return <span className="text-gray-400">-</span>;
        const color = gender === 'male' ? 'blue' : gender === 'female' ? 'pink' : 'gray';
        return <span className={`text-${color}-600 capitalize`}>{gender}</span>;
      },
    },
    {
      title: 'Phone',
      dataIndex: 'phone',
      key: 'phone',
      render: (text?: string) => text || <span className="text-gray-400">-</span>,
    },
    {
      title: 'Email',
      dataIndex: 'email',
      key: 'email',
      render: (text?: string) => text || <span className="text-gray-400">-</span>,
    },
    {
      title: 'Visit Count',
      dataIndex: 'visit_count',
      key: 'visit_count',
      render: (count: number) => (
        <span className="font-semibold">{count}</span>
      ),
    },
    {
      title: 'First Seen',
      dataIndex: 'first_seen',
      key: 'first_seen',
      render: (date: string) => (
        <span className="text-gray-600">
          {dayjs(date).format('MMM D, YYYY HH:mm')}
        </span>
      ),
    },
    {
      title: 'Last Seen',
      dataIndex: 'last_seen',
      key: 'last_seen',
      render: (date?: string) => {
        if (!date) return <span className="text-gray-400">-</span>;
        return (
          <span className="text-gray-600">
            {dayjs(date).format('MMM D, YYYY HH:mm')}
          </span>
        );
      },
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 160,
      fixed: 'right' as const,
      render: (_, customer: Customer) => (
        <Space size="small">
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handleViewDetails(customer)}
            title="View details"
            className="p-0"
          />
          <Button
            type="link"
            size="small"
            icon={<ReloadOutlined />}
            loading={backfillLoading.has(customer.customer_id)}
            onClick={() => handleBackfillAvatar(customer)}
            title="Backfill avatar from visits"
            className="p-0 text-blue-600"
            disabled={backfillLoading.has(customer.customer_id)}
          />
          <EditAction
            onClick={() => handleEditCustomer(customer)}
            tooltip="Edit customer"
          />
          <DeleteAction
            onConfirm={() => handleDeleteCustomer(customer)}
            title="Delete Customer"
            description="Are you sure you want to delete this customer? This will also remove their recognition data and visit history."
            tooltip="Delete customer"
          />
        </Space>
      ),
    },
  ];

  if (error && customers.length === 0) {
    return (
      <Alert
        message="Error Loading Customers"
        description={error}
        type="error"
        showIcon
        action={
          <Button onClick={loadCustomers}>
            Retry
          </Button>
        }
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Title level={2} className="mb-0">Customers</Title>
        <Space>
          <Button
            type="default"
            icon={<UploadOutlined />}
            onClick={() => setUploadModalVisible(true)}
          >
            Upload Images
          </Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              setEditingCustomer(null);
              form.resetFields();
              setModalVisible(true);
            }}
            className="bg-blue-600"
          >
            Add Customer
          </Button>
        </Space>
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
          dataSource={customers}
          rowKey="customer_id"
          loading={loading}
          pagination={{
            total: customers.length,
            pageSize: 10,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `Total ${total} customers`,
          }}
        />
      </div>

      <Modal
        title={editingCustomer ? "Edit Customer" : "Add New Customer"}
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false);
          setEditingCustomer(null);
          form.resetFields();
        }}
        onOk={() => form.submit()}
        confirmLoading={loading}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleCreateCustomer}
        >
          <Form.Item
            name="name"
            label="Customer Name"
          >
            <Input placeholder="e.g. John Smith (optional)" />
          </Form.Item>

          <Form.Item
            name="gender"
            label="Gender"
          >
            <Select
              placeholder="Select gender (optional)"
              allowClear
              options={[
                { value: 'male', label: 'Male' },
                { value: 'female', label: 'Female' },
                { value: 'unknown', label: 'Unknown' },
              ]}
            />
          </Form.Item>

          <Form.Item
            name="phone"
            label="Phone"
          >
            <Input placeholder="e.g. +1 555 123 4567" />
          </Form.Item>

          <Form.Item
            name="email"
            label="Email"
          >
            <Input type="email" placeholder="e.g. john@example.com" />
          </Form.Item>
        </Form>
      </Modal>

      <CustomerDetailsModal
        visible={detailsModalVisible}
        customerId={selectedCustomerId}
        onClose={() => {
          setDetailsModalVisible(false);
          setSelectedCustomerId(null);
        }}
        onEdit={handleDetailsModalEdit}
      />

      <ImageUploadModal
        visible={uploadModalVisible}
        onClose={() => setUploadModalVisible(false)}
        onCustomersChange={loadCustomers}
      />
    </div>
  );
};