import React, { useState, useEffect } from 'react';
import {
  Modal,
  Upload,
  Button,
  Alert,
  Progress,
  Space,
  List,
  Typography,
  Tag,
  Image,
  Divider,
  Select
} from 'antd';
import {
  UploadOutlined,
  InboxOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  UserOutlined,
  UserAddOutlined
} from '@ant-design/icons';
import { apiClient } from '../services/api';

const { Dragger } = Upload;
const { Text, Title } = Typography;

interface ProcessingResult {
  success: boolean;
  customerId?: number;
  customerName?: string;
  confidence?: number;
  isNewCustomer?: boolean;
  error?: string;
  imageName: string;
}

interface ImageUploadModalProps {
  visible: boolean;
  onClose: () => void;
  onCustomersChange: () => void;
}

export const ImageUploadModal: React.FC<ImageUploadModalProps> = ({
  visible,
  onClose,
  onCustomersChange
}) => {
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<{
    current: number;
    total: number;
    currentFileName?: string;
  } | null>(null);
  const [results, setResults] = useState<ProcessingResult[]>([]);
  const [processingComplete, setProcessingComplete] = useState(false);
  const [fileList, setFileList] = useState<File[]>([]);
  const [sites, setSites] = useState<any[]>([]);
  const [selectedSiteId, setSelectedSiteId] = useState<number | null>(null);
  const [loadingSites, setLoadingSites] = useState(false);

  // Load sites when modal opens
  useEffect(() => {
    if (visible) {
      loadSites();
    }
  }, [visible]);

  const loadSites = async () => {
    try {
      setLoadingSites(true);
      const sitesData = await apiClient.getSites();
      setSites(sitesData);
      if (sitesData.length > 0 && !selectedSiteId) {
        setSelectedSiteId(sitesData[0].site_id);
      }
    } catch (error) {
      console.error('Failed to load sites:', error);
    } finally {
      setLoadingSites(false);
    }
  };

  const resetState = () => {
    setUploading(false);
    setUploadProgress(null);
    setResults([]);
    setFileList([]);
    setProcessingComplete(false);
    // Don't reset selectedSiteId to keep user's choice
  };

  const handleClose = () => {
    if (uploading) {
      // Don't allow closing while uploading
      return;
    }
    resetState();
    onClose();
  };



  const handleUpload = async (files: File[]) => {
    if (files.length === 0 || !selectedSiteId) return;

    setUploading(true);
    setUploadProgress({ current: 0, total: files.length });
    setResults([]);

    try {
      // Use the API to process all images at once
      const response = await apiClient.processUploadedImages(files, selectedSiteId);
      
      // Convert API response to our ProcessingResult format
      const processingResults: ProcessingResult[] = response.results.map((apiResult, index) => ({
        success: apiResult.success,
        customerId: apiResult.customer_id,
        customerName: apiResult.customer_name,
        confidence: apiResult.confidence,
        isNewCustomer: apiResult.is_new_customer,
        error: apiResult.error,
        imageName: files[index]?.name || `image_${index + 1}`
      }));
      
      setResults(processingResults);
      
      // Update progress to complete
      setUploadProgress({
        current: files.length,
        total: files.length,
        currentFileName: 'Complete'
      });
      
      // Refresh customers list if any were created or updated
      if (response.successful_count > 0) {
        onCustomersChange();
      }
      
      // Clear file list to disable the Process Images button
      setFileList([]);
      setProcessingComplete(true);
      
    } catch (error: any) {
      console.error('Failed to process images:', error);
      
      // Create error results for all files
      const errorResults: ProcessingResult[] = files.map((file) => ({
        success: false,
        error: error.response?.data?.detail || error.message || 'Failed to process image',
        imageName: file.name
      }));
      
      setResults(errorResults);
      setProcessingComplete(true);
    } finally {
      setUploading(false);
    }
  };

  const handleFileChange = ({ fileList: newFileList }: any) => {
    const files = newFileList.map((file: any) => file.originFileObj || file).filter(Boolean);
    setFileList(files);
  };

  const startProcessing = () => {
    if (fileList.length > 0 && selectedSiteId) {
      handleUpload(fileList);
    }
  };

  const getResultIcon = (result: ProcessingResult) => {
    if (!result.success) {
      return <ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />;
    }
    if (result.isNewCustomer) {
      return <UserAddOutlined style={{ color: '#52c41a' }} />;
    }
    return <UserOutlined style={{ color: '#1890ff' }} />;
  };

  const getResultDescription = (result: ProcessingResult) => {
    if (!result.success) {
      return <Text type="danger">{result.error}</Text>;
    }
    
    if (result.isNewCustomer) {
      return (
        <div>
          <Text strong style={{ color: '#52c41a' }}>New Customer Created</Text>
          <br />
          <Text type="secondary">
            Customer ID: {result.customerId} • Confidence: {((result.confidence || 0) * 100).toFixed(1)}%
          </Text>
        </div>
      );
    }

    return (
      <div>
        <Text strong style={{ color: '#1890ff' }}>Existing Customer Recognized</Text>
        <br />
        <Text>{result.customerName} (ID: {result.customerId})</Text>
        <br />
        <Text type="secondary">Confidence: {((result.confidence || 0) * 100).toFixed(1)}%</Text>
      </div>
    );
  };

  const successCount = results.filter(r => r.success).length;
  const errorCount = results.filter(r => !r.success).length;
  const newCustomersCount = results.filter(r => r.success && r.isNewCustomer).length;
  const recognizedCount = results.filter(r => r.success && !r.isNewCustomer).length;

  return (
    <Modal
      title="Upload Images for Face Recognition"
      open={visible}
      onCancel={handleClose}
      width={800}
      footer={[
        <Button key="close" onClick={handleClose} disabled={uploading}>
          Close
        </Button>,
        <Button
          key="process"
          type={processingComplete ? "default" : "primary"}
          onClick={startProcessing}
          loading={uploading}
          disabled={fileList.length === 0 || !selectedSiteId || processingComplete}
          icon={processingComplete ? <CheckCircleOutlined /> : <UploadOutlined />}
        >
          {processingComplete ? "Processing Complete" : "Process Images"}
        </Button>
      ]}
    >
      <div className="space-y-4">
        <Alert
          message="Face Recognition Pipeline"
          description="Upload multiple images to test the face recognition system. Images will be processed to detect faces, create embeddings, and either recognize existing customers or create new customer records."
          type="info"
          showIcon
        />

        <div className="pb-2">
          <label className="block text-sm font-medium mb-2">Select Site:</label>
          <Select
            value={selectedSiteId}
            onChange={setSelectedSiteId}
            loading={loadingSites}
            placeholder="Select a site"
            style={{ width: '100%' }}
            disabled={uploading}
          >
            {sites.map(site => (
              <Select.Option key={site.site_id} value={site.site_id}>
                {site.name}
              </Select.Option>
            ))}
          </Select>
        </div>

        <Dragger
          className="mt-4"
          multiple
          accept="image/*"
          showUploadList={false}
          beforeUpload={() => false} // Prevent automatic upload
          onChange={handleFileChange}
          disabled={uploading}
        >
          <p className="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p className="ant-upload-text">Click or drag images to this area to upload</p>
          <p className="ant-upload-hint">
            Support for multiple image selection. Images should contain clear faces for best results.
          </p>
        </Dragger>

        {fileList.length > 0 && !uploading && (
          <div>
            <Title level={5}>Selected Files ({fileList.length})</Title>
            <List
              size="small"
              dataSource={fileList}
              renderItem={(file) => (
                <List.Item>
                  <Text>{file.name}</Text>
                  <Text type="secondary" className="ml-2">
                    ({(file.size / 1024 / 1024).toFixed(2)} MB)
                  </Text>
                </List.Item>
              )}
            />
          </div>
        )}

        {uploadProgress && (
          <div>
            <Title level={5}>Processing Images...</Title>
            <Progress
              percent={Math.round((uploadProgress.current / uploadProgress.total) * 100)}
              status={uploading ? "active" : "success"}
            />
            <Text type="secondary">
              {uploadProgress.currentFileName && uploading 
                ? `Processing: ${uploadProgress.currentFileName}` 
                : `${uploadProgress.current} of ${uploadProgress.total} images processed`
              }
            </Text>
          </div>
        )}

        {results.length > 0 && (
          <div>
            <div className="flex items-center justify-between mb-3">
              <Title level={5}>Processing Results</Title>
              <Space>
                {successCount > 0 && (
                  <Tag color="success" icon={<CheckCircleOutlined />}>
                    {successCount} Successful
                  </Tag>
                )}
                {newCustomersCount > 0 && (
                  <Tag color="green">
                    {newCustomersCount} New Customers
                  </Tag>
                )}
                {recognizedCount > 0 && (
                  <Tag color="blue">
                    {recognizedCount} Recognized
                  </Tag>
                )}
                {errorCount > 0 && (
                  <Tag color="error">
                    {errorCount} Failed
                  </Tag>
                )}
              </Space>
            </div>
            
            <List
              size="small"
              dataSource={results}
              renderItem={(result) => (
                <List.Item>
                  <List.Item.Meta
                    avatar={getResultIcon(result)}
                    title={result.imageName}
                    description={getResultDescription(result)}
                  />
                </List.Item>
              )}
            />
          </div>
        )}
      </div>
    </Modal>
  );
};