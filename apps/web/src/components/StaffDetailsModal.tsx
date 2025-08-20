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
  ExperimentOutlined,
  EditOutlined
} from '@ant-design/icons';
import { StaffWithFaces } from '../types/api';
import { apiClient } from '../services/api';
import { StaffFaceGallery } from './StaffFaceGallery';
import { FaceRecognitionTest } from './FaceRecognitionTest';
import dayjs from 'dayjs';

const { Title } = Typography;

interface StaffDetailsModalProps {
  visible: boolean;
  staffId: string | null;
  onClose: () => void;
  onEdit?: (staffId: string) => void;
}

export const StaffDetailsModal: React.FC<StaffDetailsModalProps> = ({
  visible,
  staffId,
  onClose,
  onEdit
}) => {
  const [loading, setLoading] = useState(false);
  const [staffData, setStaffData] = useState<StaffWithFaces | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('details');

  useEffect(() => {
    if (visible && staffId) {
      loadStaffData();
    }
  }, [visible, staffId]);

  const loadStaffData = async () => {
    if (!staffId) return;

    try {
      setLoading(true);
      setError(null);
      const data = await apiClient.getStaffWithFaces(staffId);
      setStaffData(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load staff details');
      setStaffData(null);
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setStaffData(null);
    setError(null);
    setActiveTab('details');
    onClose();
  };

  const handleEdit = () => {
    if (staffData && onEdit) {
      onEdit(staffData.staff_id);
    }
  };

  const tabItems = [
    {
      key: 'details',
      label: (
        <Space>
          <UserOutlined />
          Staff Details
        </Space>
      ),
      children: staffData && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <Title level={4} className="mb-0">
              {staffData.name}
            </Title>
            {onEdit && (
              <Button
                icon={<EditOutlined />}
                onClick={handleEdit}
              >
                Edit Staff
              </Button>
            )}
          </div>

          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="Staff ID">
              <span className="font-mono">{staffData.staff_id}</span>
            </Descriptions.Item>
            
            <Descriptions.Item label="Name">
              <span className="font-medium">{staffData.name}</span>
            </Descriptions.Item>
            
            <Descriptions.Item label="Site Assignment">
              {staffData.site_id || (
                <span className="text-gray-400">All Sites</span>
              )}
            </Descriptions.Item>
            
            <Descriptions.Item label="Status">
              <Tag color={staffData.is_active ? 'green' : 'red'}>
                {staffData.is_active ? 'Active' : 'Inactive'}
              </Tag>
            </Descriptions.Item>
            
            <Descriptions.Item label="Face Images">
              <Space>
                <span>{staffData.face_images.length} images</span>
                {staffData.face_images.some(img => img.is_primary) && (
                  <Tag color="gold" size="small">Has Primary</Tag>
                )}
                {staffData.face_images.length === 0 && (
                  <Tag color="orange" size="small">No Face Data</Tag>
                )}
              </Space>
            </Descriptions.Item>
            
            <Descriptions.Item label="Created">
              {dayjs(staffData.created_at).format('MMMM D, YYYY [at] h:mm A')}
            </Descriptions.Item>
            
            <Descriptions.Item label="Recognition Status">
              {staffData.face_images.length > 0 ? (
                <Tag color="green">Enrolled</Tag>
              ) : (
                <Tag color="orange">Not Enrolled</Tag>
              )}
            </Descriptions.Item>
          </Descriptions>

          {staffData.face_images.length === 0 && (
            <Alert
              message="Face Recognition Not Enabled"
              description="This staff member has no face images uploaded. Upload face images in the Face Gallery tab to enable face recognition."
              type="warning"
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
          Face Gallery ({staffData?.face_images.length || 0})
        </Space>
      ),
      children: staffData && (
        <StaffFaceGallery
          staffId={staffData.staff_id}
          staffName={staffData.name}
          faceImages={staffData.face_images}
          onImagesChange={loadStaffData}
        />
      )
    },
    {
      key: 'test',
      label: (
        <Space>
          <ExperimentOutlined />
          Recognition Test
        </Space>
      ),
      disabled: !staffData?.face_images.length,
      children: staffData && staffData.face_images.length > 0 && (
        <FaceRecognitionTest
          staffId={staffData.staff_id}
          staffName={staffData.name}
        />
      )
    }
  ];

  return (
    <Modal
      title={staffData ? `Staff Details - ${staffData.name}` : 'Staff Details'}
      open={visible}
      onCancel={handleClose}
      width={900}
      footer={null}
      destroyOnClose
    >
      {loading && (
        <div className="flex justify-center items-center py-12">
          <Spin size="large" />
        </div>
      )}

      {error && (
        <Alert
          message="Error Loading Staff Details"
          description={error}
          type="error"
          showIcon
          action={
            <Button size="small" onClick={loadStaffData}>
              Retry
            </Button>
          }
        />
      )}

      {staffData && !loading && (
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={tabItems}
          size="small"
        />
      )}

      {!staffData && !loading && !error && (
        <div className="text-center py-12 text-gray-400">
          No staff selected
        </div>
      )}
    </Modal>
  );
};