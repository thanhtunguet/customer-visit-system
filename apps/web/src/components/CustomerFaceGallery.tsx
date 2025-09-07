import React, { useState, useEffect, useCallback, useRef } from 'react';
import { 
  Card,
  Row,
  Col,
  Button,
  Popconfirm,
  Spin,
  Alert,
  Typography,
  Space,
  Tag,
  Tooltip,
  App
} from 'antd';
import {
  DeleteOutlined,
  PictureOutlined,
  EyeOutlined,
  InfoCircleOutlined
} from '@ant-design/icons';
import { apiClient } from '../services/api';
import dayjs from 'dayjs';

const { Text } = Typography;

// SVG placeholder for missing images
const IMAGE_PLACEHOLDER = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZGRkIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCIgZm9udC1zaXplPSIxNCIgZmlsbD0iIzk5OSIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPkltYWdlIG5vdCBhdmFpbGFibGU8L3RleHQ+PC9zdmc+';

interface CustomerFaceImage {
  image_id: number;
  image_path: string;
  confidence_score: number;
  quality_score: number;
  created_at: string;
  visit_id?: string;
  face_bbox: number[];
  detection_metadata?: Record<string, any>;
}

interface CustomerFaceGalleryProps {
  customerId: number;
  customerName?: string;
  onImagesChange?: () => void;
}

export const CustomerFaceGallery: React.FC<CustomerFaceGalleryProps> = ({
  customerId,
  customerName,
  onImagesChange
}) => {
  const [images, setImages] = useState<CustomerFaceImage[]>([]);
  const [loading, setLoading] = useState(false);
  const { message } = App.useApp();
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedImages, setSelectedImages] = useState<Set<number>>(new Set());
  const [lastSelectedIndex, setLastSelectedIndex] = useState<number | null>(null);
  const [imageUrls, setImageUrls] = useState<Record<number, string>>({});
  const [reassignVisible, setReassignVisible] = useState(false);
  const [reassignTarget, setReassignTarget] = useState<string>('');
  const [reassigning, setReassigning] = useState(false);
  
  // Ref to track if user is holding Shift/Ctrl/Cmd
  const isMultiSelectRef = useRef(false);

  useEffect(() => {
    loadImages();
  }, [customerId]);

  useEffect(() => {
    // Listen for keyboard events for multi-select
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Shift' || e.key === 'Control' || e.key === 'Meta') {
        isMultiSelectRef.current = true;
      }
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.key === 'Shift' || e.key === 'Control' || e.key === 'Meta') {
        isMultiSelectRef.current = false;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, []);

  const loadImageUrl = async (imageId: number, imagePath: string) => {
    try {
      const url = await apiClient.getImageUrl(imagePath);
      setImageUrls(prev => ({ ...prev, [imageId]: url }));
    } catch (error) {
      console.error('Failed to load image:', error);
      setImageUrls(prev => ({ ...prev, [imageId]: IMAGE_PLACEHOLDER }));
    }
  };

  const loadImages = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Clear cached image URLs to force refresh
      setImageUrls({});
      
      const response = await apiClient.getCustomerFaceImages(customerId);
      setImages(response.images || []);
      
      // Load image URLs for each image
      response.images?.forEach(image => {
        loadImageUrl(image.image_id, image.image_path);
      });
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load face images');
    } finally {
      setLoading(false);
    }
  };

  const handleImageClick = useCallback((imageId: number, index: number, event: React.MouseEvent) => {
    const isCtrlOrCmd = event.ctrlKey || event.metaKey;
    const isShift = event.shiftKey;

    if (isShift && lastSelectedIndex !== null) {
      // Shift+click: select range
      const start = Math.min(lastSelectedIndex, index);
      const end = Math.max(lastSelectedIndex, index);
      const newSelected = new Set(selectedImages);
      
      for (let i = start; i <= end; i++) {
        if (images[i]) {
          newSelected.add(images[i].image_id);
        }
      }
      setSelectedImages(newSelected);
    } else if (isCtrlOrCmd) {
      // Ctrl/Cmd+click: toggle individual selection
      const newSelected = new Set(selectedImages);
      if (newSelected.has(imageId)) {
        newSelected.delete(imageId);
      } else {
        newSelected.add(imageId);
      }
      setSelectedImages(newSelected);
      setLastSelectedIndex(index);
    } else {
      // Normal click: select only this image
      setSelectedImages(new Set([imageId]));
      setLastSelectedIndex(index);
    }
  }, [selectedImages, lastSelectedIndex, images]);

  const handleDeleteSelected = async () => {
    if (selectedImages.size === 0) return;

    try {
      setDeleting(true);
      const imageIds = Array.from(selectedImages);
      
      const response = await apiClient.deleteCustomerFaceImagesBatch(customerId, imageIds);
      
      // Log response for debugging
      console.log('Delete response:', response);
      
      message.success(`Successfully deleted ${response.deleted_count} face image${response.deleted_count > 1 ? 's' : ''}`);
      
      // Clear selection and cached URLs
      setSelectedImages(new Set());
      setLastSelectedIndex(null);
      
      // Clear cached image URLs for deleted images
      setImageUrls(prev => {
        const updated = { ...prev };
        imageIds.forEach(id => delete updated[id]);
        return updated;
      });
      
      // Force reload images
      await loadImages();
      
      if (onImagesChange) {
        onImagesChange();
      }
    } catch (err: any) {
      message.error(err.response?.data?.detail || 'Failed to delete images');
    } finally {
      setDeleting(false);
    }
  };

  const handleSelectAll = () => {
    if (selectedImages.size === images.length) {
      // Deselect all
      setSelectedImages(new Set());
    } else {
      // Select all
      setSelectedImages(new Set(images.map(img => img.image_id)));
    }
  };

  const handleViewImage = (image: CustomerFaceImage, event: React.MouseEvent) => {
    event.stopPropagation();
    const imageUrl = imageUrls[image.image_id];
    if (imageUrl && imageUrl !== IMAGE_PLACEHOLDER) {
      window.open(imageUrl, '_blank');
    } else {
      message.warning('Image is still loading, please try again in a moment');
    }
  };

  const getImageTooltip = (image: CustomerFaceImage) => (
    <div className="space-y-2 max-w-xs text-white">
      <div className="flex justify-between items-center">
        <span className="font-medium text-gray-200">Image ID:</span>
        <span className="text-white">#{image.image_id}</span>
      </div>
      <div className="flex justify-between items-center">
        <span className="font-medium text-gray-200">Confidence:</span>
        <span className={`px-2 py-0.5 rounded text-xs font-medium ${
          image.confidence_score > 0.8 ? 'bg-green-600 text-white' : 'bg-orange-600 text-white'
        }`}>
          {(image.confidence_score * 100).toFixed(1)}%
        </span>
      </div>
      {image.quality_score && (
        <div className="flex justify-between items-center">
          <span className="font-medium text-gray-200">Quality:</span>
          <span className={`px-2 py-0.5 rounded text-xs font-medium ${
            image.quality_score > 0.8 ? 'bg-green-600 text-white' : 'bg-orange-600 text-white'
          }`}>
            {(image.quality_score * 100).toFixed(1)}%
          </span>
        </div>
      )}
      <div className="flex justify-between items-center">
        <span className="font-medium text-gray-200">Captured:</span>
        <span className="text-xs text-gray-300">
          {dayjs(image.created_at).format('MMM D, YYYY HH:mm')}
        </span>
      </div>
      {image.visit_id && (
        <div className="flex justify-between items-center">
          <span className="font-medium text-gray-200">Visit ID:</span>
          <span className="text-xs font-mono text-gray-300">
            {image.visit_id.slice(-8)}
          </span>
        </div>
      )}
      {image.face_bbox && image.face_bbox.length >= 4 && (
        <div className="flex justify-between items-center">
          <span className="font-medium text-gray-200">Face Size:</span>
          <span className="text-xs text-gray-300">
            {Math.round(image.face_bbox[2])}×{Math.round(image.face_bbox[3])}px
          </span>
        </div>
      )}
    </div>
  );

  const renderImage = (image: CustomerFaceImage, index: number) => {
    const isSelected = selectedImages.has(image.image_id);
    
    return (
      <Col xs={24} sm={12} md={8} lg={6} key={image.image_id}>
        <Card
          hoverable
          className={`transition-all cursor-pointer ${
            isSelected 
              ? 'ring-2 ring-blue-500 ring-offset-2 bg-blue-50' 
              : 'hover:shadow-lg'
          }`}
          onClick={(e) => handleImageClick(image.image_id, index, e)}
          cover={
            <div className="relative overflow-hidden h-48">
              <img
                src={imageUrls[image.image_id] || IMAGE_PLACEHOLDER}
                alt={`Customer face ${image.image_id}`}
                className="w-full h-full object-cover"
                onError={(e) => {
                  const target = e.target as HTMLImageElement;
                  target.src = IMAGE_PLACEHOLDER;
                }}
              />
              {isSelected && (
                <div className="absolute inset-0 bg-blue-500 bg-opacity-20 flex items-center justify-center">
                  <div className="bg-blue-500 text-white rounded-full w-8 h-8 flex items-center justify-center">
                    ✓
                  </div>
                </div>
              )}
              <div className="absolute top-2 right-2">
                <Tag color="blue" size="small">
                  #{image.image_id}
                </Tag>
              </div>
            </div>
          }
          actions={[
            <Tooltip title={getImageTooltip(image)} key="details">
              <InfoCircleOutlined 
                onClick={(e) => {
                  e.stopPropagation();
                }}
                className="text-blue-500 hover:text-blue-600"
              />
            </Tooltip>,
            <Tooltip title="View image in new tab" key="view">
              <EyeOutlined 
                onClick={(e) => handleViewImage(image, e)}
                className="text-green-500 hover:text-green-600"
              />
            </Tooltip>
          ]}
        >
          {/* Removed Card.Meta to simplify layout - details are now in tooltip */}
        </Card>
      </Col>
    );
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center py-12">
        <Spin size="large" />
      </div>
    );
  }

  if (error) {
    return (
      <Alert
        message="Error Loading Face Images"
        description={error}
        type="error"
        showIcon
        action={
          <Button size="small" onClick={loadImages}>
            Retry
          </Button>
        }
      />
    );
  }

  return (
    <>
    <div className="space-y-4">
      {/* Header with selection controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Space>
            <PictureOutlined />
            <span className="font-medium">
              Face Gallery ({images.length} images)
            </span>
          </Space>
          
          {images.length > 0 && (
            <div className="flex items-center space-x-2">
              <Button 
                size="small" 
                onClick={handleSelectAll}
                type={selectedImages.size === images.length ? "default" : "link"}
              >
                {selectedImages.size === images.length ? 'Deselect All' : 'Select All'}
              </Button>
              
              {selectedImages.size > 0 && (
                <Tag color="blue">
                  {selectedImages.size} selected
                </Tag>
              )}
            </div>
          )}
        </div>

        {/* Delete selected button */}
        {selectedImages.size > 0 && (
          <Popconfirm
            title={`Delete ${selectedImages.size} face image${selectedImages.size > 1 ? 's' : ''}?`}
            description="This action cannot be undone."
            onConfirm={handleDeleteSelected}
            okText="Delete"
            cancelText="Cancel"
            okButtonProps={{ danger: true }}
          >
            <Button
              danger
              icon={<DeleteOutlined />}
              loading={deleting}
              size="small"
            >
              Delete Selected ({selectedImages.size})
            </Button>
          </Popconfirm>
        )}
        {selectedImages.size > 0 && (
          <Button
            size="small"
            onClick={() => setReassignVisible(true)}
          >
            Reassign Selected…
          </Button>
        )}
      </div>

      {/* Help text for multi-selection */}
      {images.length > 1 && (
        <Alert
          message="Multi-Selection Help"
          description="Click to select • Ctrl/⌘+Click to add to selection • Shift+Click to select range"
          type="info"
          showIcon
          className="text-sm"
        />
      )}

      {/* Images grid */}
      {images.length === 0 ? (
        <div className="text-center py-12">
          <PictureOutlined className="text-4xl text-gray-400 mb-4" />
          <div className="text-gray-500">
            <div className="font-medium">No face images yet</div>
            <div className="text-sm mt-1">
              Face images will be automatically captured and saved when this customer visits.
            </div>
          </div>
        </div>
      ) : (
        <Row gutter={[16, 16]}>
          {images.map(renderImage)}
        </Row>
      )}
    </div>
    <Modal
      open={reassignVisible}
      onCancel={() => setReassignVisible(false)}
      title={`Reassign ${selectedImages.size} image(s)`}
      okText={reassigning ? 'Reassigning…' : 'Reassign'}
      onOk={async () => {
        const targetId = parseInt(reassignTarget, 10);
        if (!targetId || selectedImages.size === 0) return;
        try {
          setReassigning(true);
          for (const imgId of Array.from(selectedImages)) {
            await apiClient.reassignFaceImage(imgId, targetId);
          }
          message.success('Images reassigned');
          setSelectedImages(new Set());
          setReassignVisible(false);
          setReassignTarget('');
          await loadImages();
          onImagesChange?.();
        } catch (e: any) {
          message.error(e.response?.data?.detail || 'Failed to reassign images');
        } finally {
          setReassigning(false);
        }
      }}
    >
      <div className="space-y-2">
        <div>New customer ID</div>
        <input
          value={reassignTarget}
          onChange={(e) => setReassignTarget(e.target.value)}
          className="w-full border rounded px-2 py-1"
          placeholder="Enter customer id"
        />
      </div>
    </Modal>
    </>
  );
};
