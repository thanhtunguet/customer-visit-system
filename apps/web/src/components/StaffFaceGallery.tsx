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
  Badge,
  Progress
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
  const [uploadProgress, setUploadProgress] = useState<{
    current: number;
    total: number;
    currentFileName?: string;
    canCancel?: boolean;
  } | null>(null);
  const [uploadController, setUploadController] = useState<AbortController | null>(null);
  const [recalculatingId, setRecalculatingId] = useState<string | null>(null);
  const [recalculatingAll, setRecalculatingAll] = useState(false);
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
    const baseUrl = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8080';
    const token = localStorage.getItem('access_token');
    const url = new URL(`${baseUrl}/v1/files/${imagePath}`);
    if (token) {
      url.searchParams.set('access_token', token);
    }
    return url.toString();
  };

  // Handle single file upload
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

  // Handle multiple files upload with chunked processing
  const handleMultipleUpload = async (files: File[]) => {
    if (files.length === 0) return;

    const CHUNK_SIZE = 3; // Process 3 images at a time to avoid timeout
    const MAX_RETRIES = 2;
    
    const controller = new AbortController();
    
    try {
      setUploading(true);
      setUploadController(controller);
      setUploadProgress({ current: 0, total: files.length, canCancel: true });
      
      let successCount = 0;
      let errorCount = 0;
      const failedFiles: string[] = [];
      
      // Process files in chunks
      for (let chunkStart = 0; chunkStart < files.length; chunkStart += CHUNK_SIZE) {
        const chunk = files.slice(chunkStart, Math.min(chunkStart + CHUNK_SIZE, files.length));
        
        // Convert chunk to base64 with progress tracking
        const chunkPromises = chunk.map(async (file, index) => {
          const globalIndex = chunkStart + index;
          setUploadProgress({ 
            current: globalIndex, 
            total: files.length, 
            currentFileName: file.name 
          });
          
          return new Promise<{ data: string; name: string; originalFile: File }>((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve({ 
              data: reader.result as string, 
              name: file.name,
              originalFile: file
            });
            reader.onerror = reject;
            reader.readAsDataURL(file);
          });
        });

        const chunkData = await Promise.all(chunkPromises);
        
        // Try bulk upload for this chunk first, then fall back to individual
        let chunkProcessed = false;
        
        if (chunkData.length > 1) {
          try {
            const bulkData = chunkData.map((img, index) => ({
              image_data: img.data,
              is_primary: faceImages.length === 0 && chunkStart === 0 && index === 0
            }));
            
            const bulkResult = await apiClient.uploadMultipleStaffFaceImages(
              staffId, 
              bulkData.map(d => d.image_data)
            );
            
            // Check if bulk upload actually succeeded by verifying response
            if (bulkResult && Array.isArray(bulkResult) && bulkResult.length > 0) {
              successCount += bulkResult.length;
              chunkProcessed = true;
              
              console.log(`Bulk upload succeeded for ${bulkResult.length} out of ${chunkData.length} images`);
              
              // If bulk upload was partial, we need to track which ones failed
              if (bulkResult.length < chunkData.length) {
                const failedCount = chunkData.length - bulkResult.length;
                errorCount += failedCount;
                for (let i = bulkResult.length; i < chunkData.length; i++) {
                  failedFiles.push(`${chunkData[i].name} (bulk upload partial failure)`);
                }
              }
            } else {
              console.warn('Bulk upload returned invalid or empty response, falling back to individual uploads');
            }
          } catch (bulkError) {
            console.warn('Bulk upload failed for chunk, falling back to individual uploads:', bulkError);
            // Don't set chunkProcessed = true here, so we fall back to individual processing
          }
        }
        
        // If bulk upload failed completely or we have only one image, process individually
        if (!chunkProcessed) {
          for (let i = 0; i < chunkData.length; i++) {
            const img = chunkData[i];
            let uploaded = false;
            
            // Retry logic for individual uploads with exponential backoff
            for (let attempt = 0; attempt < MAX_RETRIES && !uploaded; attempt++) {
              try {
                setUploadProgress({ 
                  current: chunkStart + i, 
                  total: files.length, 
                  currentFileName: `${img.name}${attempt > 0 ? ` (retry ${attempt})` : ''}` 
                });
                
                const isPrimary = faceImages.length === 0 && chunkStart === 0 && i === 0;
                await apiClient.uploadStaffFaceImage(staffId, img.data, isPrimary);
                successCount++;
                uploaded = true;
              } catch (error: any) {
                const isTimeoutError = error.code === 'ECONNABORTED' || error.message.includes('timeout');
                const isServerError = error.response?.status >= 500;
                
                console.warn(`Upload attempt ${attempt + 1} failed for ${img.name}:`, error);
                
                if (attempt === MAX_RETRIES - 1) {
                  errorCount++;
                  failedFiles.push(`${img.name}${isTimeoutError ? ' (timeout)' : isServerError ? ' (server error)' : ''}`);
                } else {
                  // Exponential backoff: 1s, 2s, 4s...
                  const delay = Math.min(1000 * Math.pow(2, attempt), 10000);
                  await new Promise(resolve => setTimeout(resolve, delay));
                }
              }
            }
          }
        }
        
        // Small delay between chunks to prevent overwhelming the server
        if (chunkStart + CHUNK_SIZE < files.length) {
          await new Promise(resolve => setTimeout(resolve, 500));
        }
      }
      
      // Show final results
      if (successCount > 0 && errorCount === 0) {
        message.success(`All ${successCount} face images uploaded successfully`);
      } else if (successCount > 0) {
        message.warning(
          `${successCount} images uploaded successfully, ${errorCount} failed${
            failedFiles.length > 0 ? `: ${failedFiles.join(', ')}` : ''
          }`
        );
      } else {
        message.error(`Failed to upload all images${
          failedFiles.length > 0 ? `: ${failedFiles.join(', ')}` : ''
        }`);
      }
      
      onImagesChange();
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Failed to upload images');
    } finally {
      setUploading(false);
      setUploadProgress(null);
      setUploadController(null);
    }
  };

  // Cancel upload function
  const cancelUpload = () => {
    if (uploadController) {
      uploadController.abort();
      setUploading(false);
      setUploadProgress(null);
      setUploadController(null);
      message.info('Upload cancelled by user');
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

  // Handle recalculating all face images
  const handleRecalculateAll = async () => {
    if (faceImages.length === 0) {
      message.info('No face images to recalculate');
      return;
    }

    try {
      setRecalculatingAll(true);
      
      let successCount = 0;
      let failureCount = 0;
      const errors: string[] = [];

      // Process each image sequentially to avoid overwhelming the server
      for (const image of faceImages) {
        try {
          const result = await apiClient.recalculateFaceEmbedding(staffId, image.image_id);
          successCount++;
          
          // Show progress for each successful recalculation
          message.info(`Recalculated ${image.image_id.slice(0, 8)}... (${successCount}/${faceImages.length})`);
        } catch (error: any) {
          failureCount++;
          const errorMsg = error.response?.data?.detail || 'Failed to recalculate';
          errors.push(`${image.image_id.slice(0, 8)}: ${errorMsg}`);
        }

        // Small delay between requests to prevent rate limiting
        await new Promise(resolve => setTimeout(resolve, 500));
      }

      // Show final results
      if (successCount === faceImages.length) {
        message.success(`Successfully recalculated all ${successCount} face images`);
      } else if (successCount > 0) {
        message.warning(
          `Recalculated ${successCount} images successfully, ${failureCount} failed. ${
            errors.length > 0 ? `Errors: ${errors.join(', ')}` : ''
          }`
        );
      } else {
        message.error(`Failed to recalculate all images. ${
          errors.length > 0 ? `Errors: ${errors.join(', ')}` : ''
        }`);
      }

      // Refresh the image list
      onImagesChange();
      
    } catch (error: any) {
      message.error('Failed to recalculate face images');
    } finally {
      setRecalculatingAll(false);
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
          
          <Upload
            accept="image/*"
            multiple
            showUploadList={false}
            beforeUpload={(file, fileList) => {
              if (fileList.length > 1) {
                // Handle multiple files
                handleMultipleUpload(fileList);
              } else {
                // Handle single file
                handleUpload(file, faceImages.length === 0);
              }
              return false; // Prevent default upload
            }}
            disabled={uploading}
          >
            <Button type="primary" icon={<UploadOutlined />} loading={uploading}>
              Add Multiple Images
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
              <Button icon={<StarOutlined />} loading={uploading}>
                Add Primary Image
              </Button>
            </Upload>
          )}
          
          {faceImages.length > 0 && (
            <Tooltip title="Recalculate facial landmarks and embeddings for all images to improve accuracy">
              <Popconfirm
                title="Recalculate All Face Images"
                description={`This will recalculate facial landmarks and embeddings for all ${faceImages.length} images. This may take a while. Continue?`}
                onConfirm={handleRecalculateAll}
                okText="Yes, Recalculate All"
                cancelText="Cancel"
                okButtonProps={{ danger: true }}
              >
                <Button 
                  icon={<ReloadOutlined />} 
                  loading={recalculatingAll}
                  disabled={uploading || recalculatingId !== null}
                >
                  Recalculate All ({faceImages.length})
                </Button>
              </Popconfirm>
            </Tooltip>
          )}
        </Space>
      </div>

      {/* Upload Progress Indicator */}
      {uploadProgress && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-blue-900">
              Uploading Images ({uploadProgress.current + 1} of {uploadProgress.total})
            </span>
            <div className="flex items-center gap-2">
              <span className="text-xs text-blue-700">
                {Math.round(((uploadProgress.current + 1) / uploadProgress.total) * 100)}%
              </span>
              {uploadProgress.canCancel && (
                <Button 
                  size="small" 
                  danger 
                  onClick={cancelUpload}
                  className="text-xs px-2 py-1"
                >
                  Cancel
                </Button>
              )}
            </div>
          </div>
          <Progress 
            percent={Math.round(((uploadProgress.current + 1) / uploadProgress.total) * 100)}
            status="active"
            strokeColor="#3b82f6"
            className="mb-2"
          />
          {uploadProgress.currentFileName && (
            <div className="text-xs text-blue-600 truncate">
              Processing: {uploadProgress.currentFileName}
            </div>
          )}
        </div>
      )}

      {/* Recalculate All Progress Indicator */}
      {recalculatingAll && (
        <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-orange-900">
              Recalculating Face Images and Embeddings...
            </span>
            <div className="flex items-center gap-2">
              <Spin size="small" />
              <span className="text-xs text-orange-700">
                Processing {faceImages.length} images
              </span>
            </div>
          </div>
          <div className="text-xs text-orange-600">
            This process will update facial landmarks and regenerate embeddings for better accuracy.
            Please wait...
          </div>
        </div>
      )}

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
                    disabled={recalculatingAll || uploading}
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
                    <Tag color="gold">Primary</Tag>
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