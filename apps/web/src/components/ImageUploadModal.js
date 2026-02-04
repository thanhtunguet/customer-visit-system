import { jsx as _jsx, jsxs as _jsxs } from 'react/jsx-runtime';
import { useState, useEffect, useCallback } from 'react';
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
  Select,
} from 'antd';
import {
  UploadOutlined,
  InboxOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  UserOutlined,
  UserAddOutlined,
} from '@ant-design/icons';
import { apiClient } from '../services/api';
const { Dragger } = Upload;
const { Text, Title } = Typography;
export const ImageUploadModal = ({ visible, onClose, onCustomersChange }) => {
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(null);
  const [results, setResults] = useState([]);
  const [processingComplete, setProcessingComplete] = useState(false);
  const [fileList, setFileList] = useState([]);
  const [sites, setSites] = useState([]);
  const [selectedSiteId, setSelectedSiteId] = useState(null);
  const [loadingSites, setLoadingSites] = useState(false);
  // Load sites when modal opens
  useEffect(() => {
    if (visible) {
      loadSites();
    }
  }, [visible]); // eslint-disable-line react-hooks/exhaustive-deps
  const loadSites = useCallback(async () => {
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
  }, [selectedSiteId]);
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
  const handleUpload = async (files) => {
    if (files.length === 0 || !selectedSiteId) return;
    setUploading(true);
    setUploadProgress({ current: 0, total: files.length });
    setResults([]);
    try {
      // Use the API to process all images at once
      const response = await apiClient.processUploadedImages(
        files,
        selectedSiteId
      );
      // Convert API response to our ProcessingResult format
      const processingResults = response.results.map((apiResult, index) => ({
        success: apiResult.success,
        customerId: apiResult.customer_id,
        customerName: apiResult.customer_name,
        confidence: apiResult.confidence,
        isNewCustomer: apiResult.is_new_customer,
        error: apiResult.error,
        imageName: files[index]?.name || `image_${index + 1}`,
      }));
      setResults(processingResults);
      // Update progress to complete
      setUploadProgress({
        current: files.length,
        total: files.length,
        currentFileName: 'Complete',
      });
      // Refresh customers list if any were created or updated
      if (response.successful_count > 0) {
        onCustomersChange();
      }
      // Clear file list to disable the Process Images button
      setFileList([]);
      setProcessingComplete(true);
    } catch (error) {
      console.error('Failed to process images:', error);
      // Create error results for all files
      const errorResults = files.map((file) => ({
        success: false,
        error:
          error instanceof Error
            ? error.message
            : error?.response?.data?.detail || 'Failed to process image',
        imageName: file.name,
      }));
      setResults(errorResults);
      setProcessingComplete(true);
    } finally {
      setUploading(false);
    }
  };
  const handleFileChange = ({ fileList: newFileList }) => {
    const files = newFileList
      .map((file) => file.originFileObj || file)
      .filter(Boolean);
    setFileList(files);
  };
  const startProcessing = () => {
    if (fileList.length > 0 && selectedSiteId) {
      handleUpload(fileList);
    }
  };
  const getResultIcon = (result) => {
    if (!result.success) {
      return _jsx(ExclamationCircleOutlined, { style: { color: '#ff4d4f' } });
    }
    if (result.isNewCustomer) {
      return _jsx(UserAddOutlined, { style: { color: '#52c41a' } });
    }
    return _jsx(UserOutlined, { style: { color: '#1890ff' } });
  };
  const getResultDescription = (result) => {
    if (!result.success) {
      return _jsx(Text, { type: 'danger', children: result.error });
    }
    if (result.isNewCustomer) {
      return _jsxs('div', {
        children: [
          _jsx(Text, {
            strong: true,
            style: { color: '#52c41a' },
            children: 'New Customer Created',
          }),
          _jsx('br', {}),
          _jsxs(Text, {
            type: 'secondary',
            children: [
              'Customer ID: ',
              result.customerId,
              ' \u2022 Confidence: ',
              ((result.confidence || 0) * 100).toFixed(1),
              '%',
            ],
          }),
        ],
      });
    }
    return _jsxs('div', {
      children: [
        _jsx(Text, {
          strong: true,
          style: { color: '#1890ff' },
          children: 'Existing Customer Recognized',
        }),
        _jsx('br', {}),
        _jsxs(Text, {
          children: [result.customerName, ' (ID: ', result.customerId, ')'],
        }),
        _jsx('br', {}),
        _jsxs(Text, {
          type: 'secondary',
          children: [
            'Confidence: ',
            ((result.confidence || 0) * 100).toFixed(1),
            '%',
          ],
        }),
      ],
    });
  };
  const successCount = results.filter((r) => r.success).length;
  const errorCount = results.filter((r) => !r.success).length;
  const newCustomersCount = results.filter(
    (r) => r.success && r.isNewCustomer
  ).length;
  const recognizedCount = results.filter(
    (r) => r.success && !r.isNewCustomer
  ).length;
  return _jsx(Modal, {
    title: 'Upload Images for Face Recognition',
    open: visible,
    onCancel: handleClose,
    width: 800,
    footer: [
      _jsx(
        Button,
        { onClick: handleClose, disabled: uploading, children: 'Close' },
        'close'
      ),
      _jsx(
        Button,
        {
          type: processingComplete ? 'default' : 'primary',
          onClick: startProcessing,
          loading: uploading,
          disabled:
            fileList.length === 0 || !selectedSiteId || processingComplete,
          icon: processingComplete
            ? _jsx(CheckCircleOutlined, {})
            : _jsx(UploadOutlined, {}),
          children: processingComplete
            ? 'Processing Complete'
            : 'Process Images',
        },
        'process'
      ),
    ],
    children: _jsxs('div', {
      className: 'space-y-4',
      children: [
        _jsx(Alert, {
          message: 'Face Recognition Pipeline',
          description:
            'Upload multiple images to test the face recognition system. Images will be processed to detect faces, create embeddings, and either recognize existing customers or create new customer records.',
          type: 'info',
          showIcon: true,
        }),
        _jsxs('div', {
          className: 'pb-2',
          children: [
            _jsx('label', {
              className: 'block text-sm font-medium mb-2',
              children: 'Select Site:',
            }),
            _jsx(Select, {
              value: selectedSiteId,
              onChange: setSelectedSiteId,
              loading: loadingSites,
              placeholder: 'Select a site',
              style: { width: '100%' },
              disabled: uploading,
              children: sites.map((site) =>
                _jsx(
                  Select.Option,
                  { value: site.site_id, children: site.name },
                  site.site_id
                )
              ),
            }),
          ],
        }),
        _jsxs(Dragger, {
          className: 'mt-4',
          multiple: true,
          accept: 'image/*',
          showUploadList: false,
          beforeUpload: () => false,
          onChange: handleFileChange,
          disabled: uploading,
          children: [
            _jsx('p', {
              className: 'ant-upload-drag-icon',
              children: _jsx(InboxOutlined, {}),
            }),
            _jsx('p', {
              className: 'ant-upload-text',
              children: 'Click or drag images to this area to upload',
            }),
            _jsx('p', {
              className: 'ant-upload-hint',
              children:
                'Support for multiple image selection. Images should contain clear faces for best results.',
            }),
          ],
        }),
        fileList.length > 0 &&
          !uploading &&
          _jsxs('div', {
            children: [
              _jsxs(Title, {
                level: 5,
                children: ['Selected Files (', fileList.length, ')'],
              }),
              _jsx(List, {
                size: 'small',
                dataSource: fileList,
                renderItem: (file) =>
                  _jsxs(List.Item, {
                    children: [
                      _jsx(Text, { children: file.name }),
                      _jsxs(Text, {
                        type: 'secondary',
                        className: 'ml-2',
                        children: [
                          '(',
                          (file.size / 1024 / 1024).toFixed(2),
                          ' MB)',
                        ],
                      }),
                    ],
                  }),
              }),
            ],
          }),
        uploadProgress &&
          _jsxs('div', {
            children: [
              _jsx(Title, { level: 5, children: 'Processing Images...' }),
              _jsx(Progress, {
                percent: Math.round(
                  (uploadProgress.current / uploadProgress.total) * 100
                ),
                status: uploading ? 'active' : 'success',
              }),
              _jsx(Text, {
                type: 'secondary',
                children:
                  uploadProgress.currentFileName && uploading
                    ? `Processing: ${uploadProgress.currentFileName}`
                    : `${uploadProgress.current} of ${uploadProgress.total} images processed`,
              }),
            ],
          }),
        results.length > 0 &&
          _jsxs('div', {
            children: [
              _jsxs('div', {
                className: 'flex items-center justify-between mb-3',
                children: [
                  _jsx(Title, { level: 5, children: 'Processing Results' }),
                  _jsxs(Space, {
                    children: [
                      successCount > 0 &&
                        _jsxs(Tag, {
                          color: 'success',
                          icon: _jsx(CheckCircleOutlined, {}),
                          children: [successCount, ' Successful'],
                        }),
                      newCustomersCount > 0 &&
                        _jsxs(Tag, {
                          color: 'green',
                          children: [newCustomersCount, ' New Customers'],
                        }),
                      recognizedCount > 0 &&
                        _jsxs(Tag, {
                          color: 'blue',
                          children: [recognizedCount, ' Recognized'],
                        }),
                      errorCount > 0 &&
                        _jsxs(Tag, {
                          color: 'error',
                          children: [errorCount, ' Failed'],
                        }),
                    ],
                  }),
                ],
              }),
              _jsx(List, {
                size: 'small',
                dataSource: results,
                renderItem: (result) =>
                  _jsx(List.Item, {
                    children: _jsx(List.Item.Meta, {
                      avatar: getResultIcon(result),
                      title: result.imageName,
                      description: getResultDescription(result),
                    }),
                  }),
              }),
            ],
          }),
      ],
    }),
  });
};
