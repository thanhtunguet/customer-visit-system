import React, { useEffect, useState } from 'react';
import { 
  Table, 
  Button, 
  Modal, 
  Form, 
  Input, 
  Typography, 
  Space, 
  Alert,
  Tag,
  Select,
  Radio,
  Popconfirm,
  Tooltip,
  message
} from 'antd';
import { PlusOutlined, VideoCameraOutlined, PlayCircleOutlined, StopOutlined, EyeOutlined } from '@ant-design/icons';
import { CameraStream } from '../components/CameraStream';
import { ViewAction, EditAction, DeleteAction } from '../components/TableActionButtons';
import { apiClient } from '../services/api';
import { Camera, Site, CameraType, WebcamInfo } from '../types/api';
import dayjs from 'dayjs';

const { Title } = Typography;

export const Cameras: React.FC = () => {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [sites, setSites] = useState<Site[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingCamera, setEditingCamera] = useState<Camera | null>(null);
  const [selectedSite, setSelectedSite] = useState<string>('');
  const [form] = Form.useForm();
  const [error, setError] = useState<string | null>(null);
  const [streamingCamera, setStreamingCamera] = useState<Camera | null>(null);
  const [streamModalVisible, setStreamModalVisible] = useState(false);
  const [streamStatuses, setStreamStatuses] = useState<Record<string, boolean>>({});
  const [streamConnectionState, setStreamConnectionState] = useState<'disconnected' | 'connecting' | 'connected' | 'error'>('disconnected');
  const [streamIntent, setStreamIntent] = useState<'view' | 'start'>('view');
  const [webcams, setWebcams] = useState<WebcamInfo[]>([]);
  const [webcamsLoading, setWebcamsLoading] = useState(false);

  useEffect(() => {
    loadSites();
  }, []);

  useEffect(() => {
    if (selectedSite) {
      loadCameras(selectedSite);
    }
  }, [selectedSite]);

  // Check stream statuses periodically
  useEffect(() => {
    let interval: NodeJS.Timeout;
    
    if (selectedSite && cameras.length > 0) {
      const checkStreamStatuses = async () => {
        const statuses: Record<string, boolean> = {};
        
        for (const camera of cameras) {
          try {
            const status = await apiClient.getCameraStreamStatus(selectedSite, camera.camera_id);
            statuses[camera.camera_id] = status.stream_active;
          } catch (err) {
            statuses[camera.camera_id] = false;
          }
        }
        
        setStreamStatuses(statuses);
      };
      
      // Check immediately
      checkStreamStatuses();
      
      // Then check every 10 seconds
      interval = setInterval(checkStreamStatuses, 10000);
    }
    
    return () => {
      if (interval) {
        clearInterval(interval);
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
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load sites');
    } finally {
      setLoading(false);
    }
  };

  const loadCameras = async (siteId: string) => {
    try {
      setLoading(true);
      setError(null);
      const camerasData = await apiClient.getCameras(siteId);
      setCameras(camerasData);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load cameras');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateCamera = async (values: any) => {
    try {
      if (editingCamera) {
        await apiClient.updateCamera(selectedSite, editingCamera.camera_id, values);
      } else {
        await apiClient.createCamera(selectedSite, values);
      }
      setModalVisible(false);
      setEditingCamera(null);
      form.resetFields();
      await loadCameras(selectedSite);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save camera');
    }
  };

  const handleEditCamera = (camera: Camera) => {
    setEditingCamera(camera);
    form.setFieldsValue({
      name: camera.name,
      camera_type: camera.camera_type,
      rtsp_url: camera.rtsp_url,
      device_index: camera.device_index,
    });
    setModalVisible(true);
  };

  const handleDeleteCamera = async (camera: Camera) => {
    try {
      await apiClient.deleteCamera(selectedSite, camera.camera_id);
      await loadCameras(selectedSite);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete camera');
    }
  };

  const handleStartStreaming = (camera: Camera) => {
    setStreamingCamera(camera);
    setStreamIntent('start');
    setStreamModalVisible(true);
  };

  const handleViewStream = async (camera: Camera) => {
    setStreamingCamera(camera);
    setStreamIntent('view');
    setStreamModalVisible(true);
    // Check and update stream status when opening modal
    try {
      const status = await apiClient.getCameraStreamStatus(selectedSite, camera.camera_id);
      setStreamStatuses(prev => ({ ...prev, [camera.camera_id]: status.stream_active }));
    } catch (err) {
      console.error('Failed to check stream status:', err);
    }
  };

  const handleStopStream = async (camera: Camera) => {
    try {
      await apiClient.stopCameraStream(selectedSite, camera.camera_id);
      setStreamStatuses(prev => ({ ...prev, [camera.camera_id]: false }));
      message.success(`Stopped stream for ${camera.name}`);
    } catch (err: any) {
      message.error(`Failed to stop stream: ${err.response?.data?.detail || err.message}`);
    }
  };

  // Callback to handle stream state changes from CameraStream component
  const handleStreamStateChange = (cameraId: string, isActive: boolean) => {
    setStreamStatuses(prev => ({ ...prev, [cameraId]: isActive }));
  };

  // Callback to handle connection state changes from CameraStream component
  const handleConnectionStateChange = (state: 'disconnected' | 'connecting' | 'connected' | 'error') => {
    setStreamConnectionState(state);
  };

  // Generate dynamic modal title with camera info and status
  const getStreamModalTitle = () => {
    if (!streamingCamera) return 'Camera Stream';
    
    const getStatusColor = () => {
      switch (streamConnectionState) {
        case 'connected': return '#52c41a';
        case 'connecting': return '#1890ff';
        case 'error': return '#ff4d4f';
        default: return '#d9d9d9';
      }
    };

    return (
      <Space>
        <VideoCameraOutlined style={{ color: '#1890ff' }} />
        <span>{streamingCamera.name}</span>
        <span style={{ color: '#8c8c8c', fontSize: '14px' }}>#{streamingCamera.camera_id}</span>
        <Tag color={getStatusColor().replace('#', '')} style={{ marginLeft: '8px' }}>
          {streamConnectionState.charAt(0).toUpperCase() + streamConnectionState.slice(1)}
        </Tag>
      </Space>
    );
  };

  const columns = [
    {
      title: 'Camera ID',
      dataIndex: 'camera_id',
      key: 'camera_id',
      render: (text: string) => (
        <Space>
          <VideoCameraOutlined className="text-blue-600" />
          <span className="font-mono">{text}</span>
        </Space>
      ),
    },
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (text: string) => (
        <span className="font-medium">{text}</span>
      ),
    },
    {
      title: 'Type',
      dataIndex: 'camera_type',
      key: 'camera_type',
      render: (type: string) => (
        <Tag color={type === 'rtsp' ? 'blue' : 'green'}>
          {type === 'rtsp' ? 'RTSP' : 'Webcam'}
        </Tag>
      ),
    },
    {
      title: 'RTSP URL',
      dataIndex: 'rtsp_url',
      key: 'rtsp_url',
      render: (text?: string) => text || <span className="text-gray-400">-</span>,
    },
    {
      title: 'Device Index',
      dataIndex: 'device_index', 
      key: 'device_index',
      render: (index?: number) => index !== null && index !== undefined ? (
        <Tooltip title={`OpenCV device index ${index} - matches system webcam enumeration`}>
          <span className="font-mono bg-gray-100 px-2 py-1 rounded">#{index}</span>
        </Tooltip>
      ) : (
        <span className="text-gray-400">-</span>
      ),
    },
    {
      title: 'Status',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (isActive: boolean) => (
        <Tag color={isActive ? 'green' : 'red'}>
          {isActive ? 'Active' : 'Inactive'}
        </Tag>
      ),
    },
    {
      title: 'Stream Status',
      key: 'stream_status',
      render: (_, camera: Camera) => {
        const isStreaming = streamStatuses[camera.camera_id];
        return (
          <Tag color={isStreaming ? 'blue' : 'default'}>
            {isStreaming ? 'Streaming' : 'Not Streaming'}
          </Tag>
        );
      },
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => (
        <span className="text-gray-600">
          {dayjs(date).format('MMM D, YYYY')}
        </span>
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 160,
      fixed: 'right' as const,
      render: (_, camera: Camera) => {
        const isStreaming = streamStatuses[camera.camera_id];
        
        return (
          <Space size="small">
            <Tooltip title="View camera stream">
              <Button
                type="text"
                icon={<EyeOutlined />}
                onClick={() => handleViewStream(camera)}
                size="small"
                disabled={!camera.is_active}
              />
            </Tooltip>
            {!isStreaming ? (
              <Tooltip title="Start live stream">
                <Button
                  type="text"
                  icon={<PlayCircleOutlined />}
                  onClick={() => handleStartStreaming(camera)}
                  size="small"
                  disabled={!camera.is_active}
                />
              </Tooltip>
            ) : (
              <Tooltip title="Stop camera stream">
                <Popconfirm
                  title="Stop Stream"
                  description="Are you sure you want to stop this camera stream?"
                  onConfirm={() => handleStopStream(camera)}
                  okText="Yes"
                  cancelText="No"
                >
                  <Button
                    type="text"
                    icon={<StopOutlined />}
                    size="small"
                    danger
                  />
                </Popconfirm>
              </Tooltip>
            )}
            <EditAction
              onClick={() => handleEditCamera(camera)}
              tooltip="Edit camera"
            />
            <DeleteAction
              onConfirm={() => handleDeleteCamera(camera)}
              title="Delete Camera"
              description="Are you sure you want to delete this camera?"
              tooltip="Delete camera"
            />
          </Space>
        );
      },
    },
  ];

  if (error && cameras.length === 0) {
    return (
      <Alert
        message="Error Loading Cameras"
        description={error}
        type="error"
        showIcon
        action={
          <Button onClick={() => selectedSite && loadCameras(selectedSite)}>
            Retry
          </Button>
        }
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Title level={2} className="mb-0">Cameras</Title>
        <Space>
          <Select
            value={selectedSite}
            onChange={setSelectedSite}
            placeholder="Select Site"
            style={{ width: 200 }}
            options={sites.map(site => ({ 
              value: site.site_id, 
              label: site.name 
            }))}
          />
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              setEditingCamera(null);
              form.resetFields();
              // Set default values when creating new camera
              form.setFieldsValue({
                camera_type: CameraType.RTSP
              });
              setModalVisible(true);
            }}
            className="bg-blue-600"
            disabled={!selectedSite}
          >
            Add Camera
          </Button>
        </Space>
      </div>

      {error && (
        <Alert
          message={error}
          type="error"
          closable
          onClose={() => setError(null)}
        />
      )}

      <div className="bg-white rounded-lg shadow">
        <Table
          columns={columns}
          dataSource={cameras}
          rowKey="camera_id"
          loading={loading}
          pagination={{
            total: cameras.length,
            pageSize: 10,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `Total ${total} cameras`,
          }}
        />
      </div>

      <Modal
        title={editingCamera ? "Edit Camera" : "Add New Camera"}
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false);
          setEditingCamera(null);
          form.resetFields();
        }}
        onOk={() => form.submit()}
        confirmLoading={loading}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleCreateCamera}
        >


          <Form.Item
            name="name"
            label="Camera Name"
            rules={[{ required: true, message: 'Please input camera name!' }]}
          >
            <Input placeholder="e.g. Entrance Camera" />
          </Form.Item>

          <Form.Item
            name="camera_type"
            label="Camera Type"
            rules={[{ required: true, message: 'Please select camera type!' }]}
          >
            <Radio.Group onChange={async (e) => {
              if (e.target.value === CameraType.WEBCAM) {
                try {
                  setWebcamsLoading(true);
                  const list = await apiClient.getWebcams();
                  setWebcams(list);
                } finally {
                  setWebcamsLoading(false);
                }
              }
            }}>
              <Radio value={CameraType.RTSP}>RTSP Camera</Radio>
              <Radio value={CameraType.WEBCAM}>Webcam</Radio>
            </Radio.Group>
          </Form.Item>

          <Form.Item
            noStyle
            shouldUpdate={true}
          >
            {({ getFieldValue }) => {
              const cameraType = getFieldValue('camera_type');
              
              if (cameraType === CameraType.RTSP) {
                return (
                  <Form.Item
                    name="rtsp_url"
                    label="RTSP URL"
                    rules={[{ required: true, message: 'Please input RTSP URL!' }]}
                  >
                    <Input placeholder="e.g. rtsp://192.168.1.100:554/stream" />
                  </Form.Item>
                );
              }
              
              if (cameraType === CameraType.WEBCAM) {
                return (
                  <Form.Item
                    name="device_index"
                    label="Webcam Device"
                    tooltip="Select the physical webcam device. Device index matches system enumeration."
                    rules={[{ required: true, message: 'Please select a webcam!' }]}
                  >
                    <Select
                      loading={webcamsLoading}
                      placeholder={webcamsLoading ? 'Scanning webcams...' : 'Select a webcam device'}
                      showSearch
                      filterOption={(input, option) => 
                        option?.label?.toString().toLowerCase().indexOf(input.toLowerCase()) >= 0
                      }
                      onDropdownVisibleChange={async (open) => {
                        if (open && webcams.length === 0) {
                          try {
                            setWebcamsLoading(true);
                            const list = await apiClient.getWebcams();
                            setWebcams(list);
                          } finally {
                            setWebcamsLoading(false);
                          }
                        }
                      }}
                      options={webcams.map((w) => ({
                        value: w.device_index,
                        disabled: !w.is_working || w.in_use,
                        label: `${w.in_use ? '🔒 ' : ''}Device ${w.device_index}${w.width && w.height ? ` (${w.width}x${w.height})` : ''}${w.fps ? ` ${Math.round(w.fps)}fps` : ''}${!w.is_working ? ' [Not Working]' : ''}`.trim()
                      }))}
                    />
                  </Form.Item>
                );
              }
              
              return null;
            }}
          </Form.Item>

          <Form.Item
            name="rtsp_url"
            label="RTSP URL (legacy)"
            style={{ display: 'none' }}
          >
            <Input placeholder="e.g. rtsp://192.168.1.100:554/stream" />
          </Form.Item>
        </Form>
      </Modal>

      {/* Camera Streaming Modal */}
      <Modal
        title={getStreamModalTitle()}
        open={streamModalVisible}
        onCancel={() => {
          setStreamModalVisible(false);
          setStreamingCamera(null);
          setStreamConnectionState('disconnected');
          setStreamIntent('view');
        }}
        footer={null}
        width="95%"
        style={{ maxWidth: '1200px' }}
        styles={{ body: { padding: '8px' } }}
        centered
      >
        {streamingCamera && (
          <CameraStream
            siteId={selectedSite}
            cameraId={streamingCamera.camera_id}
            cameraName={streamingCamera.name}
            onClose={() => {
              setStreamModalVisible(false);
              setStreamingCamera(null);
            }}
            onStreamStateChange={handleStreamStateChange}
            onConnectionStateChange={handleConnectionStateChange}
            autoStart={streamIntent === 'start'}
            autoReconnect={streamIntent === 'view'}
            currentStreamStatus={streamStatuses[streamingCamera.camera_id] || false}
          />
        )}
      </Modal>
    </div>
  );
};