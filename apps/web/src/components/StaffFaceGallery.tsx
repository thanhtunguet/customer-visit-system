import React, { useState } from 'react';
import {
  Upload,
  Button,
  Modal,
  Card,
  Image,
  Tag,
  Space,
  Popconfirm,
  message,
  Spin,
  Alert,
  Tooltip,
  Badge
} from 'antd';
import {
  UploadOutlined,
  DeleteOutlined,
  ReloadOutlined,
  EyeOutlined,
  StarOutlined,
  StarFilled
} from '@ant-design/icons';
import { StaffFaceImage } from '../types/api';
import { apiClient } from '../services/api';

interface StaffFaceGalleryProps {
  staffId: string;
  staffName: string;
  faceImages: StaffFaceImage[];
  onImagesChange: () => void;
}

interface LandmarksOverlayProps {
  landmarks: number[][];
  imageWidth: number;
  imageHeight: number;
  naturalWidth: number;
  naturalHeight: number;
  showConnections?: boolean;
}

const LandmarksOverlay: React.FC<LandmarksOverlayProps> = ({
  landmarks,
  imageWidth,
  imageHeight,
  naturalWidth,
  naturalHeight,
  showConnections = false
}) => {
  const scaleX = imageWidth / naturalWidth;
  const scaleY = imageHeight / naturalHeight;

  return (
    <svg
      style={{ 
        position: 'absolute', 
        left: 0, 
        top: 0, 
        width: imageWidth,
        height: imageHeight,
        pointerEvents: 'none'
      }}
      viewBox={`0 0 ${imageWidth} ${imageHeight}`}
    >
      {landmarks.map(([x, y], idx) => {
        const scaledX = x * scaleX;
        const scaledY = y * scaleY;
        
        return (
          <circle
            key={idx}
            cx={scaledX}
            cy={scaledY}
            r={showConnections ? 3 : 2}
            fill="rgba(34, 197, 94, 0.8)"
            stroke="white"
            strokeWidth={1}
          />
        );
      })}
      {/* Draw connections between landmark points for better visualization */}
      {showConnections && landmarks.length === 5 && (
        <g stroke="rgba(34, 197, 94, 0.6)" strokeWidth={1} fill="none">
          {/* Eye landmarks connection */}
          <line 
            x1={landmarks[0][0] * scaleX} 
            y1={landmarks[0][1] * scaleY}
            x2={landmarks[1][0] * scaleX} 
            y2={landmarks[1][1] * scaleY}
          />
          {/* Nose to mouth connection */}
          <line 
            x1={landmarks[2][0] * scaleX} 
            y1={landmarks[2][1] * scaleY}
            x2={landmarks[3][0] * scaleX} 
            y2={landmarks[3][1] * scaleY}
          />
          <line 
            x1={landmarks[2][0] * scaleX} 
            y1={landmarks[2][1] * scaleY}
            x2={landmarks[4][0] * scaleX} 
            y2={landmarks[4][1] * scaleY}
          />
        </g>
      )}
    </svg>
  );
};

export const StaffFaceGallery: React.FC<StaffFaceGalleryProps> = ({
  staffId,
  staffName,
  faceImages,
  onImagesChange
}) => {
  const [uploading, setUploading] = useState(false);
  const [recalculatingId, setRecalculatingId] = useState<string | null>(null);
  const [previewVisible, setPreviewVisible] = useState(false);
  const [previewImage, setPreviewImage] = useState<string>('');
  const [previewTitle, setPreviewTitle] = useState<string>('');
  const [previewLandmarks, setPreviewLandmarks] = useState<number[][] | null>(null);
  const [renderSize, setRenderSize] = useState<{ width: number; height: number; naturalWidth: number; naturalHeight: number }>({
    width: 0,
    height: 0,
    naturalWidth: 0,
    naturalHeight: 0,
  });
  const [thumbnailSizes, setThumbnailSizes] = useState<Record<string, { width: number; height: number; naturalWidth: number; naturalHeight: number }>>({});

  // Convert image path to full URL
  const getImageUrl = (imagePath: string) => {
    const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8080';
    const token = localStorage.getItem('access_token');
    const url = new URL(`${baseUrl}/v1/files/${imagePath}`);
    if (token) {
      url.searchParams.set('access_token', token);
    }
    return url.toString();
  };

  // Handle file upload
  const handleUpload = async (file: File, isPrimary: boolean = false) => {
    try {
      setUploading(true);
      
      // Convert file to base64
      const base64 = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result as string);
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });

      await apiClient.uploadStaffFaceImage(staffId, base64, isPrimary);
      message.success('Face image uploaded successfully');
      onImagesChange();
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Failed to upload image');
    } finally {
      setUploading(false);
    }
  };

  // Handle image deletion
  const handleDelete = async (imageId: string) => {
    try {
      await apiClient.deleteStaffFaceImage(staffId, imageId);
      message.success('Face image deleted successfully');
      onImagesChange();
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Failed to delete image');
    }
  };

  // Handle recalculation
  const handleRecalculate = async (imageId: string) => {
    try {
      setRecalculatingId(imageId);
      const result = await apiClient.recalculateFaceEmbedding(staffId, imageId);
      message.success(`${result.message} (Confidence: ${(result.processing_info.confidence * 100).toFixed(1)}%)`);
      onImagesChange();
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Failed to recalculate embedding');
    } finally {
      setRecalculatingId(null);
    }
  };

  // Handle image preview
  const handlePreview = (image: StaffFaceImage) => {
    setPreviewImage(getImageUrl(image.image_path));
    setPreviewTitle(`${staffName} - Image ${image.image_id.slice(0, 8)}`);
    setPreviewLandmarks(image.face_landmarks ?? null);
    setPreviewVisible(true);
  };

  const primaryImage = faceImages.find(img => img.is_primary);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium">Face Images ({faceImages.length})</h3>
        <Space>
          <Upload
            accept="image/*"
            showUploadList={false}
            beforeUpload={(file) => {
              handleUpload(file, false);
              return false; // Prevent default upload
            }}
            disabled={uploading}
          >
            <Button icon={<UploadOutlined />} loading={uploading}>
              Add Image
            </Button>
          </Upload>
          
          {faceImages.length === 0 && (
            <Upload
              accept="image/*"
              showUploadList={false}
              beforeUpload={(file) => {
                handleUpload(file, true);
                return false; // Prevent default upload
              }}
              disabled={uploading}
            >
              <Button type="primary" icon={<StarOutlined />} loading={uploading}>
                Add Primary Image
              </Button>
            </Upload>
          )}
        </Space>
      </div>

      {faceImages.length === 0 ? (
        <Alert
          message="No face images"
          description="Upload face images to enable face recognition for this staff member."
          type="info"
          showIcon
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {faceImages.map((image) => (
            <Card
              key={image.image_id}
              size="small"
              cover={
                <div className="relative">
                  <Image
                    src={getImageUrl(image.image_path)}
                    alt={`Face image ${image.image_id.slice(0, 8)}`}
                    className="object-cover"
                    height={200}
                    preview={false}
                    onClick={() => handlePreview(image)}
                    style={{ cursor: 'pointer' }}
                    onLoad={(e) => {
                      const img = e.currentTarget as HTMLImageElement;
                      setThumbnailSizes(prev => ({
                        ...prev,
                        [image.image_id]: {
                          width: img.clientWidth,
                          height: img.clientHeight,
                          naturalWidth: img.naturalWidth,
                          naturalHeight: img.naturalHeight,
                        }
                      }));
                    }}
                  />
                  {image.face_landmarks && thumbnailSizes[image.image_id] && (
                    <LandmarksOverlay
                      landmarks={image.face_landmarks}
                      imageWidth={thumbnailSizes[image.image_id].width}
                      imageHeight={thumbnailSizes[image.image_id].height}
                      naturalWidth={thumbnailSizes[image.image_id].naturalWidth}
                      naturalHeight={thumbnailSizes[image.image_id].naturalHeight}
                      showConnections={false}
                    />
                  )}
                  {image.is_primary && (
                    <Badge
                      count={<StarFilled className="text-yellow-500" />}
                      className="absolute top-2 right-2"
                    />
                  )}
                </div>
              }
              actions={[
                <Tooltip title="View Image">
                  <Button
                    type="text"
                    icon={<EyeOutlined />}
                    onClick={() => handlePreview(image)}
                  />
                </Tooltip>,
                <Tooltip title="Recalculate Landmarks & Embedding">
                  <Button
                    type="text"
                    icon={<ReloadOutlined />}
                    loading={recalculatingId === image.image_id}
                    onClick={() => handleRecalculate(image.image_id)}
                  />
                </Tooltip>,
                <Popconfirm
                  title="Delete Face Image"
                  description="Are you sure you want to delete this face image?"
                  onConfirm={() => handleDelete(image.image_id)}
                  okText="Yes"
                  cancelText="No"
                >
                  <Tooltip title="Delete Image">
                    <Button
                      type="text"
                      danger
                      icon={<DeleteOutlined />}
                    />
                  </Tooltip>
                </Popconfirm>
              ]}
            >
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-500 font-mono">
                    {image.image_id.slice(0, 8)}...
                  </span>
                  {image.is_primary && (
                    <Tag color="gold" size="small">Primary</Tag>
                  )}
                </div>
                
                <div className="text-xs text-gray-400">
                  Uploaded: {new Date(image.created_at).toLocaleDateString()}
                </div>
                
                {image.face_landmarks && (
                  <div className="text-xs text-green-600">
                    ✓ Landmarks detected ({image.face_landmarks.length} points)
                  </div>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Image Preview Modal */}
      <Modal
        open={previewVisible}
        title={previewTitle}
        footer={null}
        onCancel={() => setPreviewVisible(false)}
        width="auto"
        centered
      >
        <div className="relative inline-block" style={{ maxWidth: '100%', maxHeight: '70vh' }}>
          <img
            src={previewImage}
            alt="Preview"
            style={{
              display: 'block',
              maxWidth: '100%',
              maxHeight: '70vh',
            }}
            onLoad={(e) => {
              const img = e.currentTarget as HTMLImageElement;
              setRenderSize({
                width: img.clientWidth,
                height: img.clientHeight,
                naturalWidth: img.naturalWidth,
                naturalHeight: img.naturalHeight,
              });
            }}
          />

          {previewLandmarks && renderSize.width > 0 && renderSize.height > 0 && (
            <LandmarksOverlay
              landmarks={previewLandmarks}
              imageWidth={renderSize.width}
              imageHeight={renderSize.height}
              naturalWidth={renderSize.naturalWidth}
              naturalHeight={renderSize.naturalHeight}
              showConnections={true}
            />
          )}
        </div>
      </Modal>
    </div>
  );
};