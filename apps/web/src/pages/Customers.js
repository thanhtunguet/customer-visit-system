import { jsx as _jsx, jsxs as _jsxs } from 'react/jsx-runtime';
import {
  PlusOutlined,
  UserOutlined,
  EyeOutlined,
  ReloadOutlined,
  UploadOutlined,
  TeamOutlined,
  MergeCellsOutlined,
  DeleteOutlined,
  SwapOutlined,
} from '@ant-design/icons';
import {
  Typography,
  Form,
  Input,
  Button,
  Table,
  Modal,
  Select,
  Space,
  Alert,
  List,
  Tag,
} from 'antd';
import { apiClient } from '../services/api';
import { EditAction, DeleteAction } from '../components/TableActionButtons';
import { CustomerDetailsModal } from '../components/CustomerDetailsModal';
import { BulkCustomerMergeModal } from '../components/BulkCustomerMergeModal';
import { AuthenticatedAvatar } from '../components/AuthenticatedAvatar';
import { ImageUploadModal } from '../components/ImageUploadModal';
import dayjs from 'dayjs';
import { useState, useEffect } from 'react';
const { Title } = Typography;
export const Customers = () => {
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingCustomer, setEditingCustomer] = useState(null);
  const [form] = Form.useForm();
  const [error, setError] = useState(null);
  // Details modal state
  const [detailsModalVisible, setDetailsModalVisible] = useState(false);
  const [selectedCustomerId, setSelectedCustomerId] = useState(null);
  // Backfill state
  const [backfillLoading, setBackfillLoading] = useState(new Set());
  // Upload images modal state
  const [uploadModalVisible, setUploadModalVisible] = useState(false);
  // Merge/similar modal
  const [similarVisible, setSimilarVisible] = useState(false);
  const [similarLoading, setSimilarLoading] = useState(false);
  const [similarList, setSimilarList] = useState([]);
  const [similarSourceId, setSimilarSourceId] = useState(null);
  // Multi-select state
  const [selectedRowKeys, setSelectedRowKeys] = useState([]);
  const [bulkDeleteLoading, setBulkDeleteLoading] = useState(false);
  // Bulk merge state
  const [bulkMergeModalVisible, setBulkMergeModalVisible] = useState(false);
  const [bulkMergeLoading, setBulkMergeLoading] = useState(false);
  useEffect(() => {
    loadCustomers();
  }, []);
  const loadCustomers = async () => {
    try {
      setLoading(true);
      setError(null);
      const customersData = await apiClient.getCustomers({ limit: 1000 });
      setCustomers(customersData);
    } catch (err) {
      const axiosError = err;
      setError(axiosError.response?.data?.detail || 'Failed to load customers');
    } finally {
      setLoading(false);
    }
  };
  const handleCreateCustomer = async (values) => {
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
    } catch (err) {
      const axiosError = err;
      setError(axiosError.response?.data?.detail || 'Failed to save customer');
    }
  };
  const handleEditCustomer = (customer) => {
    setEditingCustomer(customer);
    form.setFieldsValue({
      name: customer.name,
      gender: customer.gender,
      phone: customer.phone,
      email: customer.email,
    });
    setModalVisible(true);
  };
  const handleDeleteCustomer = async (customer) => {
    try {
      await apiClient.deleteCustomer(customer.customer_id);
      await loadCustomers();
    } catch (err) {
      const axiosError = err;
      setError(
        axiosError.response?.data?.detail || 'Failed to delete customer'
      );
    }
  };
  const handleViewDetails = (customer) => {
    setSelectedCustomerId(customer.customer_id);
    setDetailsModalVisible(true);
  };
  const openSimilar = async (customer) => {
    setSimilarSourceId(customer.customer_id);
    setSimilarVisible(true);
    setSimilarLoading(true);
    try {
      const res = await apiClient.findSimilarCustomers(customer.customer_id, {
        threshold: 0.85,
        limit: 10,
      });
      setSimilarList(res.similar_customers || []);
    } catch (e) {
      setSimilarList([]);
    } finally {
      setSimilarLoading(false);
    }
  };
  const doMerge = async (targetId) => {
    if (!similarSourceId) return;
    Modal.confirm({
      title: `Merge Customer #${targetId} into #${similarSourceId}?`,
      icon: null,
      content:
        'All visits and face images from the secondary will be moved to the primary.',
      okText: 'Merge',
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await apiClient.mergeCustomers(similarSourceId, targetId);
          setSimilarVisible(false);
          await loadCustomers();
        } catch (err) {
          const axiosError = err;
          setError(
            axiosError.response?.data?.detail || 'Failed to merge customers'
          );
        }
      },
    });
  };
  const handleDetailsModalEdit = (customerId) => {
    // Find customer and open edit modal
    const customer = customers.find((c) => c.customer_id === customerId);
    if (customer) {
      setDetailsModalVisible(false);
      handleEditCustomer(customer);
    }
  };
  const handleBulkDelete = async () => {
    if (selectedRowKeys.length === 0) return;
    Modal.confirm({
      title: 'Delete Selected Customers',
      icon: _jsx(DeleteOutlined, { className: 'text-red-500' }),
      content: _jsxs('div', {
        children: [
          _jsxs('p', {
            children: [
              'Are you sure you want to delete ',
              _jsx('strong', { children: selectedRowKeys.length }),
              ' selected customers?',
            ],
          }),
          _jsx('p', {
            className: 'text-red-600 text-sm',
            children:
              'This will permanently remove their recognition data, face images, and visit history.',
          }),
        ],
      }),
      okText: 'Delete All',
      okButtonProps: { danger: true },
      cancelText: 'Cancel',
      onOk: async () => {
        setBulkDeleteLoading(true);
        try {
          await apiClient.bulkDeleteCustomers(selectedRowKeys);
          setSelectedRowKeys([]);
          await loadCustomers();
        } catch (err) {
          const axiosError = err;
          setError(
            axiosError.response?.data?.detail ||
              'Failed to delete selected customers'
          );
        } finally {
          setBulkDeleteLoading(false);
        }
      },
    });
  };
  const handleBulkMerge = async (mergeOperations) => {
    setBulkMergeLoading(true);
    try {
      const result = await apiClient.bulkMergeCustomers(mergeOperations);
      // Show success message with job information
      Modal.success({
        title: 'Bulk Merge Started',
        content: _jsxs('div', {
          children: [
            _jsx('p', {
              children:
                'Bulk customer merge has been started in the background.',
            }),
            _jsxs('p', {
              children: [
                _jsx('strong', { children: 'Job ID:' }),
                ' ',
                result.job_id,
              ],
            }),
            _jsxs('p', {
              children: [
                _jsx('strong', { children: 'Operations:' }),
                ' ',
                result.total_operations,
              ],
            }),
            _jsxs('p', {
              children: [
                _jsx('strong', { children: 'Customers:' }),
                ' ',
                result.total_customers,
              ],
            }),
            _jsx('p', {
              className: 'text-gray-600 text-sm mt-2',
              children:
                'You can monitor the progress in the background jobs section or refresh the customer list after completion.',
            }),
          ],
        }),
      });
      setSelectedRowKeys([]);
      setBulkMergeModalVisible(false);
      // Optionally refresh customers after a delay
      setTimeout(async () => {
        await loadCustomers();
      }, 5000);
    } catch (err) {
      const axiosError = err;
      setError(
        axiosError.response?.data?.detail || 'Failed to start bulk merge'
      );
    } finally {
      setBulkMergeLoading(false);
    }
  };
  const getSelectedCustomers = () => {
    return customers.filter((customer) =>
      selectedRowKeys.includes(customer.customer_id)
    );
  };
  const handleBackfillAvatar = async (customer) => {
    setBackfillLoading((prev) => new Set([...prev, customer.customer_id]));
    try {
      const result = await apiClient.backfillCustomerFaceImages(
        customer.customer_id
      );
      if (result.visits_processed > 0) {
        setError(null);
        // Reload customers to show updated avatars
        await loadCustomers();
        // You could also show a success message here
        console.log(
          `✅ Backfilled ${result.visits_processed} face images for customer ${customer.customer_id}`
        );
      } else {
        setError(
          `No face images found to backfill for customer ${customer.name || customer.customer_id}`
        );
      }
    } catch (err) {
      console.error('Backfill failed:', err);
      const axiosError = err;
      setError(
        axiosError.response?.data?.detail ||
          `Failed to backfill avatar for customer ${customer.name || customer.customer_id}`
      );
    } finally {
      setBackfillLoading((prev) => {
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
      render: (avatar_url, customer) =>
        _jsx(AuthenticatedAvatar, {
          src: avatar_url,
          size: 40,
          className: 'flex-shrink-0',
          alt: `${customer.name || 'Customer'} Avatar`,
          icon: _jsx(UserOutlined, {}),
        }),
    },
    {
      title: 'ID',
      dataIndex: 'customer_id',
      key: 'customer_id',
      width: 80,
      render: (id) =>
        _jsxs('span', {
          className: 'font-mono text-gray-600',
          children: ['#', id],
        }),
    },
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (text) =>
        _jsx('span', {
          className: 'font-medium',
          children:
            text ||
            _jsx('span', {
              className: 'text-gray-400 italic',
              children: 'Unknown',
            }),
        }),
    },
    {
      title: 'Gender',
      dataIndex: 'gender',
      key: 'gender',
      render: (gender) => {
        if (!gender)
          return _jsx('span', { className: 'text-gray-400', children: '-' });
        const color =
          gender === 'male' ? 'blue' : gender === 'female' ? 'pink' : 'gray';
        return _jsx('span', {
          className: `text-${color}-600 capitalize`,
          children: gender,
        });
      },
    },
    {
      title: 'Phone',
      dataIndex: 'phone',
      key: 'phone',
      render: (text) =>
        text || _jsx('span', { className: 'text-gray-400', children: '-' }),
    },
    {
      title: 'Email',
      dataIndex: 'email',
      key: 'email',
      render: (text) =>
        text || _jsx('span', { className: 'text-gray-400', children: '-' }),
    },
    {
      title: 'Visit Count',
      dataIndex: 'visit_count',
      key: 'visit_count',
      render: (count) =>
        _jsx('span', { className: 'font-semibold', children: count }),
    },
    {
      title: 'First Seen',
      dataIndex: 'first_seen',
      key: 'first_seen',
      render: (date) =>
        _jsx('span', {
          className: 'text-gray-600',
          children: dayjs(date).format('MMM D, YYYY HH:mm'),
        }),
    },
    {
      title: 'Last Seen',
      dataIndex: 'last_seen',
      key: 'last_seen',
      render: (date) => {
        if (!date)
          return _jsx('span', { className: 'text-gray-400', children: '-' });
        return _jsx('span', {
          className: 'text-gray-600',
          children: dayjs(date).format('MMM D, YYYY HH:mm'),
        });
      },
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 160,
      fixed: 'right',
      render: (_, customer) =>
        _jsxs(Space, {
          size: 'small',
          children: [
            _jsx(Button, {
              type: 'link',
              size: 'small',
              icon: _jsx(TeamOutlined, {}),
              onClick: () => openSimilar(customer),
              title: 'Find similar customers',
              className: 'p-0',
            }),
            _jsx(Button, {
              type: 'link',
              size: 'small',
              icon: _jsx(EyeOutlined, {}),
              onClick: () => handleViewDetails(customer),
              title: 'View details',
              className: 'p-0',
            }),
            _jsx(Button, {
              type: 'link',
              size: 'small',
              icon: _jsx(ReloadOutlined, {}),
              loading: backfillLoading.has(customer.customer_id),
              onClick: () => handleBackfillAvatar(customer),
              title: 'Backfill avatar from visits',
              className: 'p-0 text-blue-600',
              disabled: backfillLoading.has(customer.customer_id),
            }),
            _jsx(EditAction, {
              onClick: () => handleEditCustomer(customer),
              tooltip: 'Edit customer',
            }),
            _jsx(DeleteAction, {
              onConfirm: () => handleDeleteCustomer(customer),
              title: 'Delete Customer',
              description:
                'Are you sure you want to delete this customer? This will also remove their recognition data and visit history.',
              tooltip: 'Delete customer',
            }),
          ],
        }),
    },
  ];
  if (error && customers.length === 0) {
    return _jsx(Alert, {
      message: 'Error Loading Customers',
      description: error,
      type: 'error',
      showIcon: true,
      action: _jsx(Button, { onClick: loadCustomers, children: 'Retry' }),
    });
  }
  return _jsxs('div', {
    className: 'space-y-6',
    children: [
      _jsxs('div', {
        className: 'flex items-center justify-between',
        children: [
          _jsx(Title, { level: 2, className: 'mb-0', children: 'Customers' }),
          _jsxs(Space, {
            children: [
              selectedRowKeys.length > 1 &&
                _jsxs(Button, {
                  type: 'default',
                  icon: _jsx(SwapOutlined, {}),
                  loading: bulkMergeLoading,
                  onClick: () => setBulkMergeModalVisible(true),
                  className: 'border-blue-500 text-blue-600 hover:bg-blue-50',
                  children: ['Bulk Merge (', selectedRowKeys.length, ')'],
                }),
              selectedRowKeys.length > 0 &&
                _jsxs(Button, {
                  type: 'primary',
                  danger: true,
                  icon: _jsx(DeleteOutlined, {}),
                  loading: bulkDeleteLoading,
                  onClick: handleBulkDelete,
                  children: ['Delete Selected (', selectedRowKeys.length, ')'],
                }),
              _jsx(Button, {
                type: 'default',
                icon: _jsx(UploadOutlined, {}),
                onClick: () => setUploadModalVisible(true),
                children: 'Upload Images',
              }),
              _jsx(Button, {
                type: 'primary',
                icon: _jsx(PlusOutlined, {}),
                onClick: () => {
                  setEditingCustomer(null);
                  form.resetFields();
                  setModalVisible(true);
                },
                className: 'bg-blue-600',
                children: 'Add Customer',
              }),
            ],
          }),
        ],
      }),
      error &&
        _jsx(Alert, {
          message: error,
          type: 'error',
          closable: true,
          onClose: () => setError(null),
        }),
      _jsx('div', {
        className: 'bg-white rounded-lg shadow',
        children: _jsx(Table, {
          columns: columns,
          dataSource: customers,
          rowKey: 'customer_id',
          loading: loading,
          rowSelection: {
            selectedRowKeys,
            onChange: (keys) => setSelectedRowKeys(keys),
            getCheckboxProps: (record) => ({
              name: `customer-${record.customer_id}`,
            }),
          },
          pagination: {
            total: customers.length,
            pageSize: 10,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `Total ${total} customers`,
          },
        }),
      }),
      _jsx(Modal, {
        title: editingCustomer ? 'Edit Customer' : 'Add New Customer',
        open: modalVisible,
        onCancel: () => {
          setModalVisible(false);
          setEditingCustomer(null);
          form.resetFields();
        },
        onOk: () => form.submit(),
        confirmLoading: loading,
        children: _jsxs(Form, {
          form: form,
          layout: 'vertical',
          onFinish: handleCreateCustomer,
          children: [
            _jsx(Form.Item, {
              name: 'name',
              label: 'Customer Name',
              children: _jsx(Input, {
                placeholder: 'e.g. John Smith (optional)',
              }),
            }),
            _jsx(Form.Item, {
              name: 'gender',
              label: 'Gender',
              children: _jsx(Select, {
                placeholder: 'Select gender (optional)',
                allowClear: true,
                options: [
                  { value: 'male', label: 'Male' },
                  { value: 'female', label: 'Female' },
                  { value: 'unknown', label: 'Unknown' },
                ],
              }),
            }),
            _jsx(Form.Item, {
              name: 'phone',
              label: 'Phone',
              children: _jsx(Input, { placeholder: 'e.g. +1 555 123 4567' }),
            }),
            _jsx(Form.Item, {
              name: 'email',
              label: 'Email',
              children: _jsx(Input, {
                type: 'email',
                placeholder: 'e.g. john@example.com',
              }),
            }),
          ],
        }),
      }),
      _jsx(CustomerDetailsModal, {
        visible: detailsModalVisible,
        customerId: selectedCustomerId,
        onClose: () => {
          setDetailsModalVisible(false);
          setSelectedCustomerId(null);
        },
        onEdit: handleDetailsModalEdit,
      }),
      _jsx(ImageUploadModal, {
        visible: uploadModalVisible,
        onClose: () => setUploadModalVisible(false),
        onCustomersChange: loadCustomers,
      }),
      _jsx(Modal, {
        title: similarSourceId
          ? `Similar to Customer #${similarSourceId}`
          : 'Similar Customers',
        open: similarVisible,
        onCancel: () => setSimilarVisible(false),
        footer: null,
        children: similarLoading
          ? _jsx('div', {
              className: 'py-8 text-center',
              children: 'Loading\u2026',
            })
          : similarList.length === 0
            ? _jsx('div', {
                className: 'py-8 text-center text-gray-500',
                children: 'No similar customers found above threshold.',
              })
            : _jsx(List, {
                dataSource: similarList,
                renderItem: (item) =>
                  _jsx(List.Item, {
                    actions: [
                      _jsx(
                        Button,
                        {
                          type: 'primary',
                          icon: _jsx(MergeCellsOutlined, {}),
                          className: 'bg-blue-600',
                          onClick: () => doMerge(item.customer_id),
                          children: 'Merge into Source',
                        },
                        'merge'
                      ),
                    ],
                    children: _jsx(List.Item.Meta, {
                      title: _jsxs('span', {
                        children: [
                          '#',
                          item.customer_id,
                          ' ',
                          item.name ? `— ${item.name}` : '',
                        ],
                      }),
                      description: _jsxs(Space, {
                        children: [
                          _jsxs(Tag, {
                            color: 'blue',
                            children: ['visits: ', item.visit_count],
                          }),
                          _jsxs(Tag, {
                            color: 'green',
                            children: [
                              'similarity: ',
                              (item.max_similarity * 100).toFixed(1),
                              '%',
                            ],
                          }),
                        ],
                      }),
                    }),
                  }),
              }),
      }),
      _jsx(BulkCustomerMergeModal, {
        visible: bulkMergeModalVisible,
        selectedCustomers: getSelectedCustomers(),
        onClose: () => setBulkMergeModalVisible(false),
        onMerge: handleBulkMerge,
      }),
    ],
  });
};
