import { jsx as _jsx, jsxs as _jsxs } from 'react/jsx-runtime';
import { useState, useEffect, useCallback } from 'react';
import {
  Modal,
  Typography,
  Button,
  Table,
  Space,
  Alert,
  message,
  Tag,
  Image,
} from 'antd';
import { DeleteOutlined, EyeOutlined } from '@ant-design/icons';
import { apiClient } from '../services/api';
import dayjs from 'dayjs';
const { Text } = Typography;
export const VisitFaceRemovalModal = ({
  visible,
  customerId,
  onClose,
  onRemovalComplete,
}) => {
  const [loading, setLoading] = useState(false);
  const [visits, setVisits] = useState([]);
  const [selectedVisitIds, setSelectedVisitIds] = useState([]);
  const [removing, setRemoving] = useState(false);
  const loadCustomerVisits = useCallback(async () => {
    if (!customerId) return;
    try {
      setLoading(true);
      const result = await apiClient.getVisits({
        person_id: customerId.toString(),
        limit: 100,
      });
      // Filter to only visits with face images and sort by confidence
      const visitsWithFaces = result.visits
        .filter(
          (visit) => visit.image_path && visit.confidence_score !== undefined
        )
        .sort((a, b) => (a.confidence_score || 0) - (b.confidence_score || 0));
      setVisits(visitsWithFaces);
    } catch (error) {
      message.error('Failed to load customer visits');
      console.error('Error loading visits:', error);
    } finally {
      setLoading(false);
    }
  }, [customerId]);
  useEffect(() => {
    if (visible && customerId) {
      loadCustomerVisits();
      setSelectedVisitIds([]);
    }
  }, [visible, customerId, loadCustomerVisits]);
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
        message.success(
          `Successfully removed ${successCount} face detection(s)${failCount > 0 ? ` (${failCount} failed)` : ''}`
        );
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
  const getConfidenceColor = (confidence) => {
    if (confidence >= 0.9) return 'green';
    if (confidence >= 0.7) return 'orange';
    return 'red';
  };
  const columns = [
    {
      title: 'Image',
      key: 'image',
      width: 80,
      render: (record) =>
        record.image_path
          ? _jsx(Image, {
              width: 60,
              height: 60,
              src: record.image_path,
              style: { objectFit: 'cover', borderRadius: '4px' },
              fallback:
                "data:image/svg+xml,%3csvg width='60' height='60' xmlns='http://www.w3.org/2000/svg'%3e%3crect width='60' height='60' fill='%23f0f0f0'/%3e%3cpath d='M20 25h20v10H20z' fill='%23999'/%3e%3ccircle cx='22' cy='27' r='1' fill='%23666'/%3e%3ccircle cx='38' cy='27' r='1' fill='%23666'/%3e%3c/svg%3e",
            })
          : _jsx('div', {
              style: {
                width: 60,
                height: 60,
                background: '#f0f0f0',
                borderRadius: '4px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              },
              children: _jsx(EyeOutlined, { style: { color: '#999' } }),
            }),
    },
    {
      title: 'Date',
      key: 'date',
      render: (record) =>
        _jsx(Text, {
          type: 'secondary',
          children: dayjs(record.timestamp).format('MMM D, HH:mm'),
        }),
    },
    {
      title: 'Confidence',
      key: 'confidence',
      render: (record) =>
        _jsxs(Tag, {
          color: getConfidenceColor(record.confidence_score),
          children: [Math.round(record.confidence_score * 100), '%'],
        }),
    },
    {
      title: 'Site',
      dataIndex: 'site_id',
      key: 'site_id',
      render: (siteId) => `Site ${siteId}`,
    },
  ];
  const rowSelection = {
    selectedRowKeys: selectedVisitIds,
    onChange: (selectedRowKeys) => {
      setSelectedVisitIds(selectedRowKeys);
    },
  };
  if (!customerId) return null;
  return _jsx(Modal, {
    title: _jsxs(Space, {
      children: [
        _jsx(DeleteOutlined, {}),
        _jsx('span', { children: 'Remove Face Detections' }),
      ],
    }),
    open: visible,
    onCancel: onClose,
    width: 900,
    footer: [
      _jsx(Button, { onClick: onClose, children: 'Cancel' }, 'cancel'),
      _jsxs(
        Button,
        {
          type: 'primary',
          danger: true,
          icon: _jsx(DeleteOutlined, {}),
          onClick: handleRemoveSelected,
          loading: removing,
          disabled: selectedVisitIds.length === 0,
          children: ['Remove Selected (', selectedVisitIds.length, ')'],
        },
        'remove'
      ),
    ],
    children: _jsxs(Space, {
      direction: 'vertical',
      style: { width: '100%' },
      size: 'large',
      children: [
        _jsx(Alert, {
          message: 'Face Detection Removal',
          description: _jsxs('div', {
            children: [
              _jsxs('p', {
                children: [
                  _jsx('strong', { children: 'Customer ID:' }),
                  ' ',
                  customerId,
                ],
              }),
              _jsx('p', {
                children:
                  'Select individual face detections to remove. This will permanently delete the detection record, face image, and associated embedding from all systems.',
              }),
            ],
          }),
          type: 'warning',
          showIcon: true,
        }),
        _jsx(Table, {
          columns: columns,
          dataSource: visits,
          rowKey: 'visit_id',
          rowSelection: rowSelection,
          loading: loading,
          pagination: {
            pageSize: 10,
            showSizeChanger: false,
          },
          scroll: { y: 400 },
          size: 'small',
        }),
        selectedVisitIds.length > 0 &&
          _jsx(Alert, {
            message: `${selectedVisitIds.length} detection(s) selected for removal`,
            description:
              'This action cannot be undone. Selected face detections and their associated data will be permanently deleted.',
            type: 'error',
            showIcon: true,
          }),
      ],
    }),
  });
};
