import React, { useState, useEffect } from 'react';
import { Modal, Typography, Button, Slider, Alert, Space, Statistic, Row, Col, message, Spin } from 'antd';
import { DeleteOutlined, CleanupOutlined } from '@ant-design/icons';
import { apiClient } from '../services/api';
import { Customer } from '../types/api';

const { Title, Text } = Typography;

interface FaceCleanupModalProps {
  visible: boolean;
  customer: Customer | null;
  onClose: () => void;
  onCleanupComplete: () => void;
}

interface CustomerStats {
  customer_id: number;
  total_images: number;
  avg_confidence: number;
  max_confidence: number;
  min_confidence: number;
  avg_quality: number;
  first_image_date?: string;
  latest_image_date?: string;
}

export const FaceCleanupModal: React.FC<FaceCleanupModalProps> = ({
  visible,
  customer,
  onClose,
  onCleanupComplete
}) => {
  const [loading, setLoading] = useState(false);
  const [cleaning, setCleaning] = useState(false);
  const [stats, setStats] = useState<CustomerStats | null>(null);
  const [confidenceThreshold, setConfidenceThreshold] = useState(0.7);
  const [maxToRemove, setMaxToRemove] = useState(10);

  useEffect(() => {
    if (visible && customer) {
      loadCustomerStats();
    }
  }, [visible, customer]);

  const loadCustomerStats = async () => {
    if (!customer) return;
    
    try {
      setLoading(true);
      const result = await apiClient.getCustomerFaceImages(customer.customer_id);
      
      // Calculate stats from face images
      const images = result.images;
      if (images.length > 0) {
        const confidenceScores = images.map(img => img.confidence_score);
        const qualityScores = images.map(img => img.quality_score);
        
        const statsData: CustomerStats = {
          customer_id: customer.customer_id,
          total_images: images.length,
          avg_confidence: confidenceScores.reduce((a, b) => a + b, 0) / confidenceScores.length,
          max_confidence: Math.max(...confidenceScores),
          min_confidence: Math.min(...confidenceScores),
          avg_quality: qualityScores.reduce((a, b) => a + b, 0) / qualityScores.length,
          first_image_date: images[images.length - 1]?.created_at,
          latest_image_date: images[0]?.created_at
        };
        
        setStats(statsData);
      }
    } catch (error: any) {
      message.error('Failed to load customer statistics');
      console.error('Error loading customer stats:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCleanup = async () => {
    if (!customer) return;

    try {
      setCleaning(true);
      const result = await apiClient.cleanupLowConfidenceFaces(customer.customer_id, {
        min_confidence: confidenceThreshold,
        max_to_remove: maxToRemove
      });
      
      message.success(`Successfully removed ${result.removed_count} low-confidence face detections`);
      onCleanupComplete();
      onClose();
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Failed to cleanup face detections');
      console.error('Error cleaning up faces:', error);
    } finally {
      setCleaning(false);
    }
  };

  const estimateDeletions = () => {
    if (!stats) return 0;
    // This is an estimation - in practice you'd need an additional API call to get exact count
    const estimatedLowConfidence = Math.round(stats.total_images * 0.3); // Rough estimate
    return Math.min(estimatedLowConfidence, maxToRemove);
  };

  if (!customer) return null;

  return (
    <Modal
      title={
        <Space>
          <CleanupOutlined />
          <span>Cleanup Low-Quality Face Detections</span>
        </Space>
      }
      open={visible}
      onCancel={onClose}
      width={600}
      footer={[
        <Button key="cancel" onClick={onClose}>
          Cancel
        </Button>,
        <Button
          key="cleanup"
          type="primary"
          danger
          icon={<DeleteOutlined />}
          onClick={handleCleanup}
          loading={cleaning}
          disabled={!stats || stats.total_images === 0}
        >
          Remove Low-Quality Detections
        </Button>,
      ]}
    >
      <Space direction="vertical" style={{ width: '100%' }} size="large">
        <Alert
          message="Face Detection Cleanup"
          description={
            <div>
              <p><strong>Customer:</strong> {customer.name || `Customer ${customer.customer_id}`}</p>
              <p>Remove low-confidence face detections to improve data quality. This will delete both the detection records and associated images.</p>
            </div>
          }
          type="info"
          showIcon
        />

        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px' }}>
            <Spin size="large" />
            <p>Loading customer face statistics...</p>
          </div>
        ) : stats ? (
          <>
            <div>
              <Title level={4}>Current Face Gallery Statistics</Title>
              <Row gutter={16}>
                <Col span={8}>
                  <Statistic 
                    title="Total Images" 
                    value={stats.total_images}
                    valueStyle={{ color: '#1890ff' }}
                  />
                </Col>
                <Col span={8}>
                  <Statistic 
                    title="Avg Confidence" 
                    value={Math.round(stats.avg_confidence * 100)}
                    suffix="%"
                    valueStyle={{ color: stats.avg_confidence >= 0.8 ? '#52c41a' : stats.avg_confidence >= 0.6 ? '#faad14' : '#ff4d4f' }}
                  />
                </Col>
                <Col span={8}>
                  <Statistic 
                    title="Min Confidence" 
                    value={Math.round(stats.min_confidence * 100)}
                    suffix="%"
                    valueStyle={{ color: stats.min_confidence >= 0.7 ? '#52c41a' : '#ff4d4f' }}
                  />
                </Col>
              </Row>
            </div>

            <div>
              <Title level={5}>Cleanup Parameters</Title>
              <Space direction="vertical" style={{ width: '100%' }}>
                <div>
                  <Text strong>Confidence Threshold: {Math.round(confidenceThreshold * 100)}%</Text>
                  <Slider
                    min={0.3}
                    max={0.9}
                    step={0.05}
                    value={confidenceThreshold}
                    onChange={setConfidenceThreshold}
                    marks={{
                      0.3: '30%',
                      0.5: '50%',
                      0.7: '70%',
                      0.9: '90%'
                    }}
                    tooltip={{ formatter: (value) => `${Math.round((value || 0) * 100)}%` }}
                  />
                  <Text type="secondary">
                    Remove face detections with confidence below this threshold
                  </Text>
                </div>

                <div>
                  <Text strong>Maximum to Remove: {maxToRemove}</Text>
                  <Slider
                    min={1}
                    max={50}
                    step={1}
                    value={maxToRemove}
                    onChange={setMaxToRemove}
                    marks={{
                      1: '1',
                      10: '10',
                      25: '25',
                      50: '50'
                    }}
                  />
                  <Text type="secondary">
                    Limit the number of detections removed in one operation
                  </Text>
                </div>
              </Space>
            </div>

            <Alert
              message="Estimated Impact"
              description={
                <div>
                  <p><strong>Approximately {estimateDeletions()} detections</strong> will be removed based on current parameters.</p>
                  <p><strong>This action cannot be undone!</strong> Removed detections and their associated images will be permanently deleted.</p>
                </div>
              }
              type="warning"
              showIcon
            />
          </>
        ) : (
          <Alert
            message="No face images found"
            description="This customer has no face images to cleanup."
            type="info"
            showIcon
          />
        )}
      </Space>
    </Modal>
  );
};