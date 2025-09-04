import React, { useState, useEffect } from 'react';
import {
  Modal,
  Tabs,
  Descriptions,
  Tag,
  Spin,
  Alert,
  Button,
  Space,
  Typography
} from 'antd';
import {
  UserOutlined,
  PictureOutlined,
  EditOutlined,
  PhoneOutlined,
  MailOutlined
} from '@ant-design/icons';
import { Customer } from '../types/api';
import { apiClient } from '../services/api';
import { CustomerFaceGallery } from './CustomerFaceGallery';
import dayjs from 'dayjs';

const { Title, Text } = Typography;

interface CustomerDetailsModalProps {
  visible: boolean;
  customerId: number | null;
  onClose: () => void;
  onEdit?: (customerId: number) => void;
}

interface CustomerGalleryStats {
  customer_id: number;
  total_images: number;
  avg_confidence: number;
  max_confidence: number;
  min_confidence: number;
  avg_quality: number;
  first_image_date?: string;
  latest_image_date?: string;
  gallery_limit: number;
}

export const CustomerDetailsModal: React.FC<CustomerDetailsModalProps> = ({
  visible,
  customerId,
  onClose,
  onEdit
}) => {
  const [loading, setLoading] = useState(false);
  const [customerData, setCustomerData] = useState<Customer | null>(null);
  const [galleryStats, setGalleryStats] = useState<CustomerGalleryStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('details');

  useEffect(() => {
    if (visible && customerId) {
      loadCustomerData();
      loadGalleryStats();
    }
  }, [visible, customerId]);

  const loadCustomerData = async () => {
    if (!customerId) return;

    try {
      setLoading(true);
      setError(null);
      const data = await apiClient.getCustomer(customerId);
      setCustomerData(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load customer details');
      setCustomerData(null);
    } finally {
      setLoading(false);
    }
  };

  const loadGalleryStats = async () => {
    if (!customerId) return;

    try {
      const stats = await apiClient.get<CustomerGalleryStats>(`/customers/${customerId}/face-gallery-stats`);
      setGalleryStats(stats);
    } catch (err: any) {
      console.warn('Failed to load gallery stats:', err);
      // Don't show error for stats, it's optional
    }
  };

  const handleClose = () => {
    setCustomerData(null);
    setGalleryStats(null);
    setError(null);
    setActiveTab('details');
    onClose();
  };

  const handleEdit = () => {
    if (customerData && onEdit) {
      onEdit(customerData.customer_id);
    }
  };

  const handleGalleryChange = () => {
    // Reload gallery stats when images change
    loadGalleryStats();
  };

  const renderGenderTag = (gender?: string) => {
    if (!gender || gender === 'unknown') {
      return <Tag>Unknown</Tag>;
    }
    const color = gender === 'male' ? 'blue' : gender === 'female' ? 'pink' : 'gray';
    return <Tag color={color}>{gender.charAt(0).toUpperCase() + gender.slice(1)}</Tag>;
  };

  const tabItems = [
    {
      key: 'details',
      label: (
        <Space>
          <UserOutlined />
          Customer Details
        </Space>
      ),
      children: customerData && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <Title level={4} className="mb-0">
              {customerData.name || `Customer #${customerData.customer_id}`}
            </Title>
            {onEdit && (
              <Button
                icon={<EditOutlined />}
                onClick={handleEdit}
              >
                Edit Customer
              </Button>
            )}
          </div>

          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="Customer ID">
              <span className="font-mono">#{customerData.customer_id}</span>
            </Descriptions.Item>
            
            <Descriptions.Item label="Name">
              {customerData.name ? (
                <span className="font-medium">{customerData.name}</span>
              ) : (
                <span className="text-gray-400 italic">No name provided</span>
              )}
            </Descriptions.Item>
            
            <Descriptions.Item label="Gender">
              {renderGenderTag(customerData.gender)}
            </Descriptions.Item>
            
            <Descriptions.Item label="Age Range">
              {customerData.estimated_age_range || (
                <span className="text-gray-400">Unknown</span>
              )}
            </Descriptions.Item>
            
            <Descriptions.Item label="Contact">
              <Space direction="vertical" size="small">
                {customerData.phone && (
                  <Space>
                    <PhoneOutlined />
                    <Text copyable={{ text: customerData.phone }}>
                      {customerData.phone}
                    </Text>
                  </Space>
                )}
                {customerData.email && (
                  <Space>
                    <MailOutlined />
                    <Text copyable={{ text: customerData.email }}>
                      {customerData.email}
                    </Text>
                  </Space>
                )}
                {!customerData.phone && !customerData.email && (
                  <span className="text-gray-400">No contact information</span>
                )}
              </Space>
            </Descriptions.Item>
            
            <Descriptions.Item label="Visit Statistics">
              <Space direction="vertical" size="small">
                <div>
                  <Text strong>Total Visits:</Text> {customerData.visit_count}
                </div>
                <div>
                  <Text strong>First Seen:</Text> {' '}
                  {dayjs(customerData.first_seen).format('MMMM D, YYYY [at] h:mm A')}
                </div>
                {customerData.last_seen && (
                  <div>
                    <Text strong>Last Seen:</Text> {' '}
                    {dayjs(customerData.last_seen).format('MMMM D, YYYY [at] h:mm A')}
                  </div>
                )}
              </Space>
            </Descriptions.Item>
            
            <Descriptions.Item label="Recognition Status">
              {galleryStats && galleryStats.total_images > 0 ? (
                <Tag color="green">Enrolled ({galleryStats.total_images} faces)</Tag>
              ) : (
                <Tag color="orange">Limited Recognition Data</Tag>
              )}
            </Descriptions.Item>

            {galleryStats && galleryStats.total_images > 0 && (
              <Descriptions.Item label="Face Gallery Stats">
                <Space direction="vertical" size="small">
                  <div>
                    <Text strong>Images:</Text> {galleryStats.total_images} / {galleryStats.gallery_limit}
                  </div>
                  <div>
                    <Text strong>Avg Confidence:</Text> {(galleryStats.avg_confidence * 100).toFixed(1)}%
                  </div>
                  <div>
                    <Text strong>Best Match:</Text> {(galleryStats.max_confidence * 100).toFixed(1)}%
                  </div>
                  {galleryStats.first_image_date && (
                    <div>
                      <Text strong>First Image:</Text> {' '}
                      {dayjs(galleryStats.first_image_date).format('MMM D, YYYY')}
                    </div>
                  )}
                </Space>
              </Descriptions.Item>
            )}
          </Descriptions>

          {(!galleryStats || galleryStats.total_images === 0) && (
            <Alert
              message="Limited Face Recognition Data"
              description="This customer has few or no face images saved. Face images are automatically captured during visits to improve recognition accuracy."
              type="info"
              showIcon
            />
          )}
        </div>
      )
    },
    {
      key: 'faces',
      label: (
        <Space>
          <PictureOutlined />
          Face Gallery ({galleryStats?.total_images || 0})
        </Space>
      ),
      children: customerData && (
        <CustomerFaceGallery
          customerId={customerData.customer_id}
          customerName={customerData.name}
          onImagesChange={handleGalleryChange}
        />
      )
    }
  ];

  return (
    <Modal
      title={
        customerData 
          ? `Customer Details - ${customerData.name || `#${customerData.customer_id}`}`
          : 'Customer Details'
      }
      open={visible}
      onCancel={handleClose}
      width={900}
      footer={null}
      destroyOnClose={true}
      centered
    >
      {loading && (
        <div className="flex justify-center items-center py-12">
          <Spin size="large" />
        </div>
      )}

      {error && (
        <Alert
          message="Error Loading Customer Details"
          description={error}
          type="error"
          showIcon
          action={
            <Button size="small" onClick={loadCustomerData}>
              Retry
            </Button>
          }
        />
      )}

      {customerData && !loading && (
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={tabItems}
          size="small"
        />
      )}

      {!customerData && !loading && !error && (
        <div className="text-center py-12 text-gray-400">
          No customer selected
        </div>
      )}
    </Modal>
  );
};