import React, { useState, useEffect, useCallback } from 'react';
import { Modal, Typography, Button, Table, Space, Alert, Spin, Input, message } from 'antd';
import { MergeOutlined, UserOutlined } from '@ant-design/icons';
import { apiClient } from '../services/api';
import { Customer } from '../types/api';
import { AuthenticatedAvatar } from './AuthenticatedAvatar';
import dayjs from 'dayjs';

const { Title, Text } = Typography;
const { TextArea } = Input;

interface ApiError {
  response?: {
    data?: {
      detail?: string;
    };
  };
  message?: string;
}

interface CustomerMergeModalProps {
  visible: boolean;
  customer: Customer | null;
  onClose: () => void;
  onMergeComplete: () => void;
}

interface SimilarCustomer {
  customer_id: number;
  name?: string;
  visit_count: number;
  first_seen?: string;
  last_seen?: string;
  max_similarity: number;
  gender?: string;
  estimated_age_range?: string;
}

export const CustomerMergeModal: React.FC<CustomerMergeModalProps> = ({
  visible,
  customer,
  onClose,
  onMergeComplete
}) => {
  const [loading, setLoading] = useState(false);
  const [merging, setMerging] = useState(false);
  const [similarCustomers, setSimilarCustomers] = useState<SimilarCustomer[]>([]);
  const [selectedCustomer, setSelectedCustomer] = useState<SimilarCustomer | null>(null);
  const [mergeNotes, setMergeNotes] = useState('');

  const loadSimilarCustomers = useCallback(async () => {
    if (!customer) return;

    try {
      setLoading(true);
      const result = await apiClient.findSimilarCustomers(customer.customer_id, {
        threshold: 0.85,
        limit: 10
      });
      setSimilarCustomers(result.similar_customers);
    } catch (error: unknown) {
      message.error('Failed to find similar customers');
      console.error('Error finding similar customers:', error);
    } finally {
      setLoading(false);
    }
  }, [customer]);

  useEffect(() => {
    if (visible && customer) {
      loadSimilarCustomers();
      setSelectedCustomer(null);
      setMergeNotes('');
    }
  }, [visible, customer, loadSimilarCustomers]);

  const handleMerge = async () => {
    if (!customer || !selectedCustomer) return;

    try {
      setMerging(true);
      const result = await apiClient.mergeCustomers(
        customer.customer_id,
        selectedCustomer.customer_id,
        mergeNotes || undefined
      );
      
      message.success(`Successfully merged customers. Combined ${result.merged_visits} visits and ${result.merged_face_images} face images.`);
      onMergeComplete();
      onClose();
    } catch (error: unknown) {
      message.error((error as ApiError)?.response?.data?.detail || 'Failed to merge customers');
      console.error('Error merging customers:', error);
    } finally {
      setMerging(false);
    }
  };

  const columns = [
    {
      title: 'Avatar',
      key: 'avatar',
      width: 60,
      render: () => (
        <AuthenticatedAvatar
          size={40}
          icon={<UserOutlined />}
        />
      ),
    },
    {
      title: 'Customer Info',
      key: 'info',
      render: (record: SimilarCustomer) => (
        <div>
          <Text strong>{record.name || `Customer ${record.customer_id}`}</Text>
          <br />
          <Text type="secondary" style={{ fontSize: '12px' }}>
            {record.visit_count} visits • {record.gender} • {record.estimated_age_range}
          </Text>
        </div>
      ),
    },
    {
      title: 'Last Seen',
      key: 'last_seen',
      render: (record: SimilarCustomer) => (
        <Text type="secondary">
          {record.last_seen ? dayjs(record.last_seen).format('MMM D, YYYY') : 'Unknown'}
        </Text>
      ),
    },
    {
      title: 'Similarity',
      key: 'similarity',
      render: (record: SimilarCustomer) => {
        const similarity = Math.round(record.max_similarity * 100);
        const color = similarity >= 95 ? '#52c41a' : similarity >= 90 ? '#faad14' : '#1890ff';
        return (
          <Text style={{ color, fontWeight: 'bold' }}>
            {similarity}%
          </Text>
        );
      },
    },
    {
      title: 'Action',
      key: 'action',
      render: (record: SimilarCustomer) => (
        <Button
          type={selectedCustomer?.customer_id === record.customer_id ? 'primary' : 'default'}
          size="small"
          onClick={() => setSelectedCustomer(
            selectedCustomer?.customer_id === record.customer_id ? null : record
          )}
        >
          {selectedCustomer?.customer_id === record.customer_id ? 'Selected' : 'Select'}
        </Button>
      ),
    },
  ];

  if (!customer) return null;

  return (
    <Modal
      title={
        <Space>
          <MergeOutlined />
          <span>Merge Similar Customers</span>
        </Space>
      }
      open={visible}
      onCancel={onClose}
      width={800}
      footer={[
        <Button key="cancel" onClick={onClose}>
          Cancel
        </Button>,
        <Button
          key="merge"
          type="primary"
          danger
          icon={<MergeOutlined />}
          onClick={handleMerge}
          loading={merging}
          disabled={!selectedCustomer}
        >
          Merge Selected Customer
        </Button>,
      ]}
    >
      <Space direction="vertical" style={{ width: '100%' }} size="large">
        <Alert
          message="Customer Merge"
          description={
            <div>
              <p><strong>Primary Customer:</strong> {customer.name || `Customer ${customer.customer_id}`} ({customer.visit_count} visits)</p>
              <p>The selected customer will be merged into this primary customer. All visits and face images will be transferred, and the selected customer will be marked as merged.</p>
            </div>
          }
          type="info"
          showIcon
        />

        <div>
          <Title level={4}>Similar Customers Found</Title>
          {loading ? (
            <div style={{ textAlign: 'center', padding: '40px' }}>
              <Spin size="large" />
              <p>Finding similar customers...</p>
            </div>
          ) : similarCustomers.length === 0 ? (
            <Alert
              message="No similar customers found"
              description="No customers with high similarity scores were found. Try adjusting the similarity threshold or check if the customer has sufficient face images for comparison."
              type="warning"
              showIcon
            />
          ) : (
            <Table
              columns={columns}
              dataSource={similarCustomers}
              rowKey="customer_id"
              pagination={false}
              size="small"
            />
          )}
        </div>

        {selectedCustomer && (
          <div>
            <Title level={5}>Merge Notes (Optional)</Title>
            <TextArea
              rows={3}
              placeholder="Add any notes about why these customers are being merged..."
              value={mergeNotes}
              onChange={(e) => setMergeNotes(e.target.value)}
            />
          </div>
        )}

        {selectedCustomer && (
          <Alert
            message="Merge Confirmation"
            description={
              <div>
                <p><strong>This action cannot be undone!</strong></p>
                <p>Merging will:</p>
                <ul>
                  <li>Transfer all visits from <strong>{selectedCustomer.name || `Customer ${selectedCustomer.customer_id}`}</strong> to <strong>{customer.name || `Customer ${customer.customer_id}`}</strong></li>
                  <li>Transfer all face images and embeddings</li>
                  <li>Update visit counts and date ranges</li>
                  <li>Mark the selected customer as merged (soft delete)</li>
                </ul>
              </div>
            }
            type="warning"
            showIcon
          />
        )}
      </Space>
    </Modal>
  );
};