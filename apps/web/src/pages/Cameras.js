import { jsxs as _jsxs, jsx as _jsx } from 'react/jsx-runtime';
import { useEffect, useState } from 'react';
import {
  Table,
  Button,
  Modal,
  Form,
  Typography,
  Space,
  Alert,
  Tag,
  Select,
  Popconfirm,
  Tooltip,
  App,
} from 'antd';
import {
  PlusOutlined,
  PlayCircleOutlined,
  StopOutlined,
  EyeOutlined,
  RobotOutlined,
  PauseOutlined,
  WifiOutlined,
} from '@ant-design/icons';
import { WebRTCCameraStream } from '../components/WebRTCCameraStream';
import { MultiCameraStreamView } from '../components/MultiCameraStreamView';
import { EditAction, DeleteAction } from '../components/TableActionButtons';
import { CameraForm } from '../components/CameraForm';
import { apiClient } from '../services/api';
import { CameraType } from '../types/api';
import dayjs from 'dayjs';
const { Title } = Typography;
export const Cameras = () => {
  const { message } = App.useApp();
  const [cameras, setCameras] = useState([]);
  const [sites, setSites] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingCamera, setEditingCamera] = useState(null);
  const [selectedSite, setSelectedSite] = useState(null);
  const [form] = Form.useForm();
  const [error, setError] = useState(null);
  const [streamingCamera, setStreamingCamera] = useState(null);
  const [streamModalVisible, setStreamModalVisible] = useState(false);
  const [streamStatuses, setStreamStatuses] = useState({});
  const [, setStreamConnectionState] = useState('disconnected');
  const [streamIntent, setStreamIntent] = useState('view');
  const [multiStreamModalVisible, setMultiStreamModalVisible] = useState(false);
  const [processingStatuses, setProcessingStatuses] = useState({});
  // WebRTC streaming state
  useEffect(() => {
    loadSites();
  }, []);
  useEffect(() => {
    if (selectedSite) {
      loadCameras(selectedSite);
    }
  }, [selectedSite]);
  // Real-time camera status updates using Server-Sent Events
  useEffect(() => {
    let eventSource = null;
    if (selectedSite && cameras.length > 0) {
      const setupSSE = async () => {
        try {
          // Get initial status
          const response = await apiClient.get(
            `/sites/${selectedSite}/streaming/status`
          );
          const streamingData = response;
          const statuses = {};
          // Update stream and processing statuses from initial response
          const processingStatuses = {};
          if (streamingData.cameras && Array.isArray(streamingData.cameras)) {
            streamingData.cameras.forEach((cameraInfo) => {
              statuses[cameraInfo.camera_id] =
                cameraInfo.stream_active || false;
              processingStatuses[cameraInfo.camera_id] =
                cameraInfo.processing_active || false;
            });
          }
          setStreamStatuses(statuses);
          setProcessingStatuses(processingStatuses);
          // Set up SSE for real-time updates
          const token = localStorage.getItem('access_token');
          const sseUrl = new URL(
            `${apiClient.baseURL}/sites/${selectedSite}/cameras/status-stream`
          );
          if (token) {
            sseUrl.searchParams.set('access_token', token);
          }
          eventSource = new EventSource(sseUrl.toString());
          eventSource.onmessage = (event) => {
            try {
              const data = JSON.parse(event.data);
              if (data.type === 'camera_status_update') {
                // Update both streaming and processing status
                setStreamStatuses((prev) => ({
                  ...prev,
                  [data.camera_id]: data.data.stream_active,
                }));
                setProcessingStatuses((prev) => ({
                  ...prev,
                  [data.camera_id]: data.data.processing_active || false,
                }));
                console.log('Real-time camera status update:', data);
              } else if (data.type === 'site_status_update') {
                const newStatuses = {};
                const newProcessingStatuses = {};
                if (data.data.cameras && Array.isArray(data.data.cameras)) {
                  data.data.cameras.forEach((cameraInfo) => {
                    newStatuses[cameraInfo.camera_id] =
                      cameraInfo.stream_active || false;
                    newProcessingStatuses[cameraInfo.camera_id] =
                      cameraInfo.processing_active || false;
                  });
                }
                setStreamStatuses(newStatuses);
                setProcessingStatuses(newProcessingStatuses);
                console.log('Real-time site status update:', data.data);
              } else if (data.type === 'connected') {
                console.log(
                  'Connected to camera status stream for site:',
                  data.site_id
                );
              } else if (data.type === 'keepalive') {
                // Handle keepalive
              }
            } catch (err) {
              console.error('Error parsing SSE data:', err);
            }
          };
          eventSource.onerror = (error) => {
            console.error('SSE connection error:', error);
            eventSource?.close();
            // Fallback to polling on SSE failure
            setTimeout(setupSSE, 5000);
          };
        } catch (err) {
          console.error('Failed to setup real-time updates:', err);
          // Fallback to individual camera status checks
          const statuses = {};
          const processingStatuses = {};
          for (const camera of cameras) {
            try {
              const status = await apiClient.getCameraStreamStatus(
                selectedSite,
                camera.camera_id
              );
              statuses[camera.camera_id] = status.stream_active;
              processingStatuses[camera.camera_id] =
                status.processing_active || false;
            } catch (err) {
              statuses[camera.camera_id] = false;
              processingStatuses[camera.camera_id] = false;
            }
          }
          setStreamStatuses(statuses);
          setProcessingStatuses(processingStatuses);
        }
      };
      setupSSE();
    }
    return () => {
      if (eventSource) {
        eventSource.close();
      }
    };
  }, [selectedSite, cameras]);
  const loadSites = async () => {
    try {
      setLoading(true);
      setError(null);
      const sitesData = await apiClient.getSites();
      setSites(sitesData);
      if (sitesData.length > 0) {
        setSelectedSite(sitesData[0].site_id);
      }
    } catch (err) {
      const axiosError = err;
      setError(axiosError.response?.data?.detail || 'Failed to load sites');
    } finally {
      setLoading(false);
    }
  };
  const loadCameras = async (siteId) => {
    try {
      setLoading(true);
      setError(null);
      const camerasData = await apiClient.getCameras(siteId);
      setCameras(camerasData);
    } catch (err) {
      const axiosError = err;
      setError(axiosError.response?.data?.detail || 'Failed to load cameras');
    } finally {
      setLoading(false);
    }
  };
  const handleCreateCamera = async (values) => {
    try {
      if (editingCamera) {
        await apiClient.updateCamera(
          selectedSite,
          editingCamera.camera_id,
          values
        );
      } else {
        await apiClient.createCamera(selectedSite, values);
      }
      setModalVisible(false);
      setEditingCamera(null);
      form.resetFields();
      await loadCameras(selectedSite);
    } catch (err) {
      const axiosError = err;
      setError(axiosError.response?.data?.detail || 'Failed to save camera');
    }
  };
  const handleEditCamera = (camera) => {
    setEditingCamera(camera);
    form.setFieldsValue({
      name: camera.name,
      camera_type: camera.camera_type,
      rtsp_url: camera.rtsp_url,
      device_index: camera.device_index,
    });
    setModalVisible(true);
  };
  const handleDeleteCamera = async (camera) => {
    try {
      await apiClient.deleteCamera(selectedSite, camera.camera_id);
      await loadCameras(selectedSite);
    } catch (err) {
      const axiosError = err;
      setError(axiosError.response?.data?.detail || 'Failed to delete camera');
    }
  };
  const handleStartStreaming = (camera) => {
    setStreamingCamera(camera);
    setStreamIntent('start');
    setStreamModalVisible(true);
  };
  const handleViewAllStreams = () => {
    setMultiStreamModalVisible(true);
  };
  const handleCloseMultiStreamModal = () => {
    // Force cleanup by resetting modal state
    setMultiStreamModalVisible(false);
  };
  const handleViewStream = async (camera) => {
    console.log('🟢 WebRTC View Stream clicked - camera:', camera.camera_id);
    setStreamingCamera(camera);
    setStreamIntent('view');
    setStreamModalVisible(true);
  };
  const handleStopStream = async (camera) => {
    try {
      await apiClient.stopCameraStream(selectedSite, camera.camera_id);
      setStreamStatuses((prev) => ({ ...prev, [camera.camera_id]: false }));
      message.success(`Stopped stream for ${camera.name}`);
    } catch (err) {
      const axiosError = err;
      message.error(
        `Failed to stop stream: ${axiosError.response?.data?.detail || axiosError.message}`
      );
    }
  };
  const handleStartProcessing = async (camera) => {
    try {
      await apiClient.startCameraProcessing(selectedSite, camera.camera_id);
      setProcessingStatuses((prev) => ({ ...prev, [camera.camera_id]: true }));
      message.success(`Started face recognition processing for ${camera.name}`);
    } catch (err) {
      const axiosError = err;
      message.error(
        `Failed to start processing: ${axiosError.response?.data?.detail || axiosError.message}`
      );
    }
  };
  const handleStopProcessing = async (camera) => {
    try {
      await apiClient.stopCameraProcessing(selectedSite, camera.camera_id);
      setProcessingStatuses((prev) => ({ ...prev, [camera.camera_id]: false }));
      message.success(`Stopped face recognition processing for ${camera.name}`);
    } catch (err) {
      const axiosError = err;
      message.error(
        `Failed to stop processing: ${axiosError.response?.data?.detail || axiosError.message}`
      );
    }
  };
  // Callback to handle stream state changes from CameraStream component
  const handleStreamStateChange = (cameraId, isActive) => {
    setStreamStatuses((prev) => ({ ...prev, [cameraId]: isActive }));
  };
  // removed connection state tracking for now
  // removed unused getStreamModalTitle helper
  const columns = [
    {
      title: 'ID',
      dataIndex: 'camera_id',
      key: 'camera_id',
      width: 80,
      render: (id) =>
        _jsxs('span', {
          className: 'font-mono text-gray-600',
          children: ['#', id],
        }),
    },
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (text) =>
        _jsx('span', { className: 'font-medium', children: text }),
    },
    {
      title: 'Type',
      dataIndex: 'camera_type',
      key: 'camera_type',
      render: (type) =>
        _jsx(Tag, {
          color: type === 'rtsp' ? 'blue' : 'green',
          children: type === 'rtsp' ? 'RTSP' : 'Webcam',
        }),
    },
    {
      title: 'RTSP URL',
      dataIndex: 'rtsp_url',
      key: 'rtsp_url',
      render: (text) =>
        text || _jsx('span', { className: 'text-gray-400', children: '-' }),
    },
    {
      title: 'Device Index',
      dataIndex: 'device_index',
      key: 'device_index',
      render: (index) =>
        index !== null && index !== undefined
          ? _jsx(Tooltip, {
              title: `OpenCV device index ${index} - matches system webcam enumeration`,
              children: _jsxs('span', {
                className: 'font-mono bg-gray-100 px-2 py-1 rounded',
                children: ['#', index],
              }),
            })
          : _jsx('span', { className: 'text-gray-400', children: '-' }),
    },
    {
      title: 'Status',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (isActive) =>
        _jsx(Tag, {
          color: isActive ? 'green' : 'red',
          children: isActive ? 'Active' : 'Inactive',
        }),
    },
    {
      title: 'Stream Status',
      key: 'stream_status',
      render: (_, camera) => {
        const isStreaming = streamStatuses[camera.camera_id];
        return _jsx(Tag, {
          color: isStreaming ? 'blue' : 'default',
          children: isStreaming ? 'Streaming' : 'Not Streaming',
        });
      },
    },
    {
      title: 'Processing Status',
      key: 'processing_status',
      render: (_, camera) => {
        const isProcessing = processingStatuses[camera.camera_id];
        return _jsx(Tag, {
          color: isProcessing ? 'orange' : 'default',
          children: isProcessing ? 'Processing Faces' : 'Not Processing',
        });
      },
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date) =>
        _jsx('span', {
          className: 'text-gray-600',
          children: dayjs(date).format('MMM D, YYYY'),
        }),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 220,
      fixed: 'right',
      render: (_, camera) => {
        const isStreaming = streamStatuses[camera.camera_id];
        const isProcessing = processingStatuses[camera.camera_id];
        return _jsxs(Space, {
          size: 'small',
          children: [
            _jsx(Tooltip, {
              title: 'View WebRTC P2P stream',
              children: _jsx(Button, {
                type: 'text',
                icon: _jsx(WifiOutlined, {}),
                onClick: () => handleViewStream(camera),
                size: 'small',
                disabled: !camera.is_active,
                style: { color: '#1890ff' },
              }),
            }),
            !isStreaming
              ? _jsx(Tooltip, {
                  title: 'Start WebRTC P2P stream',
                  children: _jsx(Button, {
                    type: 'text',
                    icon: _jsx(PlayCircleOutlined, {}),
                    onClick: () => handleStartStreaming(camera),
                    size: 'small',
                    disabled: !camera.is_active,
                    style: { color: '#1890ff' },
                  }),
                })
              : _jsx(Tooltip, {
                  title: 'Stop WebRTC stream',
                  children: _jsx(Popconfirm, {
                    title: 'Stop Stream',
                    description: 'Stop WebRTC P2P stream?',
                    onConfirm: () => handleStopStream(camera),
                    okText: 'Yes',
                    cancelText: 'No',
                    children: _jsx(Button, {
                      type: 'text',
                      icon: _jsx(StopOutlined, {}),
                      size: 'small',
                      danger: true,
                    }),
                  }),
                }),
            !isProcessing
              ? _jsx(Tooltip, {
                  title: 'Start face recognition processing',
                  children: _jsx(Button, {
                    type: 'text',
                    icon: _jsx(RobotOutlined, {}),
                    onClick: () => handleStartProcessing(camera),
                    size: 'small',
                    disabled: !camera.is_active,
                    style: { color: '#52c41a' },
                  }),
                })
              : _jsx(Tooltip, {
                  title: 'Stop face recognition processing',
                  children: _jsx(Popconfirm, {
                    title: 'Stop Processing',
                    description:
                      'Are you sure you want to stop face recognition processing?',
                    onConfirm: () => handleStopProcessing(camera),
                    okText: 'Yes',
                    cancelText: 'No',
                    children: _jsx(Button, {
                      type: 'text',
                      icon: _jsx(PauseOutlined, {}),
                      size: 'small',
                      style: { color: '#fa8c16' },
                    }),
                  }),
                }),
            _jsx(EditAction, {
              onClick: () => handleEditCamera(camera),
              tooltip: 'Edit camera',
            }),
            _jsx(DeleteAction, {
              onConfirm: () => handleDeleteCamera(camera),
              title: 'Delete Camera',
              description: 'Are you sure you want to delete this camera?',
              tooltip: 'Delete camera',
            }),
          ],
        });
      },
    },
  ];
  if (error && cameras.length === 0) {
    return _jsx(Alert, {
      message: 'Error Loading Cameras',
      description: error,
      type: 'error',
      showIcon: true,
      action: _jsx(Button, {
        onClick: () => selectedSite && loadCameras(selectedSite),
        children: 'Retry',
      }),
    });
  }
  return _jsxs('div', {
    className: 'space-y-6',
    children: [
      _jsxs('div', {
        className: 'flex items-center justify-between',
        children: [
          _jsx(Title, { level: 2, className: 'mb-0', children: 'Cameras' }),
          _jsxs(Space, {
            children: [
              _jsx(Select, {
                value: selectedSite,
                onChange: setSelectedSite,
                placeholder: 'Select Site',
                style: { width: 200 },
                options: sites.map((site) => ({
                  value: site.site_id,
                  label: site.name,
                })),
              }),
              _jsx(Button, {
                type: 'primary',
                icon: _jsx(PlusOutlined, {}),
                onClick: () => {
                  setEditingCamera(null);
                  form.resetFields();
                  // Set default values when creating new camera
                  form.setFieldsValue({
                    camera_type: CameraType.RTSP,
                  });
                  setModalVisible(true);
                },
                className: 'bg-blue-600',
                disabled: !selectedSite,
                children: 'Add Camera',
              }),
              _jsxs(Button, {
                icon: _jsx(EyeOutlined, {}),
                onClick: handleViewAllStreams,
                disabled:
                  !selectedSite ||
                  cameras.filter((cam) => streamStatuses[cam.camera_id])
                    .length === 0,
                children: [
                  'View All Streams (',
                  cameras.filter((cam) => streamStatuses[cam.camera_id]).length,
                  ')',
                ],
              }),
            ],
          }),
        ],
      }),
      error &&
        _jsx(Alert, {
          message: error,
          type: 'error',
          closable: true,
          onClose: () => setError(null),
        }),
      _jsx('div', {
        className: 'bg-white rounded-lg shadow',
        children: _jsx(Table, {
          columns: columns,
          dataSource: cameras,
          rowKey: 'camera_id',
          loading: loading,
          pagination: {
            total: cameras.length,
            pageSize: 10,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `Total ${total} cameras`,
          },
        }),
      }),
      _jsx(Modal, {
        title: editingCamera ? 'Edit Camera' : 'Add New Camera',
        open: modalVisible,
        onCancel: () => {
          setModalVisible(false);
          setEditingCamera(null);
          form.resetFields();
        },
        onOk: () => form.submit(),
        confirmLoading: loading,
        children: _jsx(Form, {
          form: form,
          layout: 'vertical',
          onFinish: handleCreateCamera,
          children: _jsx(CameraForm, {
            form: form,
            selectedSite: selectedSite,
          }),
        }),
      }),
      _jsx(Modal, {
        title: _jsxs(Space, {
          children: [
            _jsx(WifiOutlined, { style: { color: '#1890ff' } }),
            _jsxs('span', {
              children: [streamingCamera?.name, ' - WebRTC P2P Stream'],
            }),
            _jsxs('span', {
              style: { color: '#8c8c8c', fontSize: '14px' },
              children: ['#', streamingCamera?.camera_id],
            }),
            _jsx(Tag, {
              color: 'blue',
              style: { marginLeft: '8px' },
              children: 'Peer-to-Peer',
            }),
          ],
        }),
        open: streamModalVisible,
        onCancel: () => {
          setStreamModalVisible(false);
          setStreamingCamera(null);
          setStreamConnectionState('disconnected');
          setStreamIntent('view');
        },
        footer: null,
        width: '95%',
        style: { maxWidth: '1200px' },
        styles: { body: { padding: '8px' } },
        centered: true,
        children:
          streamingCamera &&
          _jsx(
            WebRTCCameraStream,
            {
              siteId: selectedSite,
              cameraId: streamingCamera.camera_id,
              cameraName: streamingCamera.name,
              onClose: () => {
                setStreamModalVisible(false);
                setStreamingCamera(null);
              },
              onStreamStateChange: handleStreamStateChange,
              onConnectionStateChange: () => {},
              autoStart: streamIntent === 'start',
              autoReconnect: streamIntent === 'view',
              currentStreamStatus:
                streamStatuses[streamingCamera.camera_id] || false,
            },
            `webrtc-${selectedSite}-${streamingCamera.camera_id}`
          ),
      }),
      _jsx(Modal, {
        title: null,
        open: multiStreamModalVisible,
        onCancel: handleCloseMultiStreamModal,
        footer: null,
        width: '98%',
        style: { maxWidth: '1920px' },
        styles: { body: { padding: '0' } },
        centered: true,
        destroyOnHidden: true,
        children: _jsx(
          MultiCameraStreamView,
          {
            siteId: selectedSite,
            cameras: cameras,
            streamStatuses: streamStatuses,
            onStreamStateChange: handleStreamStateChange,
            onStopStream: handleStopStream,
          },
          `multi-stream-${selectedSite}-${multiStreamModalVisible}`
        ),
      }),
    ],
  });
};
