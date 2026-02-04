import React, { useState, useEffect } from 'react';
import { Modal, Typography, Button, Table, Space, Alert, message, Tag, Image } from 'antd';
import { DeleteOutlined, EyeOutlined } from '@ant-design/icons';
import { apiClient } from '../services/api';
import { Visit } from '../types/api';
import dayjs from 'dayjs';

const { Text } = Typography;

interface VisitFaceRemovalModalProps {
  visible: boolean;
  customerId: number | null;
  onClose: () => void;
  onRemovalComplete: () => void;
}

interface VisitWithFace extends Visit {
  confidence_score: number;
  image_path?: string;
}

export const VisitFaceRemovalModal: React.FC<VisitFaceRemovalModalProps> = ({
  visible,
  customerId,
  onClose,
  onRemovalComplete
}) => {
  const [loading, setLoading] = useState(false);
  const [visits, setVisits] = useState<VisitWithFace[]>([]);
  const [selectedVisitIds, setSelectedVisitIds] = useState<string[]>([]);
  const [removing, setRemoving] = useState(false);

  useEffect(() => {
    if (visible && customerId) {
      loadCustomerVisits();
      setSelectedVisitIds([]);
    }
  }, [visible, customerId]);

  const loadCustomerVisits = async () => {
    if (!customerId) return;
    
    try {
      setLoading(true);
      const result = await apiClient.getVisits({
        person_id: customerId.toString(),
        limit: 100
      });
      
      // Filter to only visits with face images and sort by confidence
      const visitsWithFaces = result.visits
        .filter(visit => visit.image_path && visit.confidence_score !== undefined)
        .sort((a, b) => (a.confidence_score || 0) - (b.confidence_score || 0)) as VisitWithFace[];
      
      setVisits(visitsWithFaces);
    } catch (error) {
      message.error('Failed to load customer visits');
      console.error('Error loading visits:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleRemoveSelected = async () => {
    if (selectedVisitIds.length === 0) return;

    try {
      setRemoving(true);
      
      // Remove visits one by one to get detailed feedback
      let successCount = 0;
      let failCount = 0;
      
      for (const visitId of selectedVisitIds) {
        try {
          await apiClient.removeVisitFaceDetection(visitId);
          successCount++;
        } catch (error) {
          failCount++;
          console.error(`Failed to remove visit ${visitId}:`, error);
        }
      }
      
      if (successCount > 0) {
        message.success(`Successfully removed ${successCount} face detection(s)${failCount > 0 ? ` (${failCount} failed)` : ''}`);
        onRemovalComplete();
        onClose();
      } else {
        message.error('Failed to remove any face detections');
      }
    } catch (error) {
      message.error('Failed to remove face detections');
      console.error('Error removing visits:', error);
    } finally {
      setRemoving(false);
    }
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.9) return 'green';
    if (confidence >= 0.7) return 'orange';
    return 'red';
  };

  const columns = [
    {
      title: 'Image',
      key: 'image',
      width: 80,
      render: (record: VisitWithFace) => (
        record.image_path ? (
          <Image
            width={60}
            height={60}
            src={record.image_path}
            style={{ objectFit: 'cover', borderRadius: '4px' }}
            fallback="data:image/svg+xml,%3csvg width='60' height='60' xmlns='http://www.w3.org/2000/svg'%3e%3crect width='60' height='60' fill='%23f0f0f0'/%3e%3cpath d='M20 25h20v10H20z' fill='%23999'/%3e%3ccircle cx='22' cy='27' r='1' fill='%23666'/%3e%3ccircle cx='38' cy='27' r='1' fill='%23666'/%3e%3c/svg%3e"
          />
        ) : (
          <div style={{ width: 60, height: 60, background: '#f0f0f0', borderRadius: '4px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <EyeOutlined style={{ color: '#999' }} />
          </div>
        )
      ),
    },
    {
      title: 'Date',
      key: 'date',
      render: (record: VisitWithFace) => (
        <Text type="secondary">
          {dayjs(record.timestamp).format('MMM D, HH:mm')}
        </Text>
      ),
    },
    {
      title: 'Confidence',
      key: 'confidence',
      render: (record: VisitWithFace) => (
        <Tag color={getConfidenceColor(record.confidence_score)}>
          {Math.round(record.confidence_score * 100)}%
        </Tag>
      ),
    },
    {
      title: 'Site',
      dataIndex: 'site_id',
      key: 'site_id',
      render: (siteId: string) => `Site ${siteId}`,
    },
  ];

  const rowSelection = {
    selectedRowKeys: selectedVisitIds,
    onChange: (selectedRowKeys: React.Key[]) => {
      setSelectedVisitIds(selectedRowKeys as string[]);
    },
  };

  if (!customerId) return null;

  return (
    <Modal
      title={
        <Space>
          <DeleteOutlined />
          <span>Remove Face Detections</span>
        </Space>
      }
      open={visible}
      onCancel={onClose}
      width={900}
      footer={[
        <Button key="cancel" onClick={onClose}>
          Cancel
        </Button>,
        <Button
          key="remove"
          type="primary"
          danger
          icon={<DeleteOutlined />}
          onClick={handleRemoveSelected}
          loading={removing}
          disabled={selectedVisitIds.length === 0}
        >
          Remove Selected ({selectedVisitIds.length})
        </Button>,
      ]}
    >
      <Space direction="vertical" style={{ width: '100%' }} size="large">
        <Alert
          message="Face Detection Removal"
          description={
            <div>
              <p><strong>Customer ID:</strong> {customerId}</p>
              <p>Select individual face detections to remove. This will permanently delete the detection record, face image, and associated embedding from all systems.</p>
            </div>
          }
          type="warning"
          showIcon
        />

        <Table
          columns={columns}
          dataSource={visits}
          rowKey="visit_id"
          rowSelection={rowSelection}
          loading={loading}
          pagination={{
            pageSize: 10,
            showSizeChanger: false,
          }}
          scroll={{ y: 400 }}
          size="small"
        />

        {selectedVisitIds.length > 0 && (
          <Alert
            message={`${selectedVisitIds.length} detection(s) selected for removal`}
            description="This action cannot be undone. Selected face detections and their associated data will be permanently deleted."
            type="error"
            showIcon
          />
        )}
      </Space>
    </Modal>
  );
};
