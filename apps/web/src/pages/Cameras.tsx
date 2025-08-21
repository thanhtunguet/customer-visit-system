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
import { PlusOutlined, VideoCameraOutlined, EditOutlined, DeleteOutlined, PlayCircleOutlined, StopOutlined } from '@ant-design/icons';
import { CameraStream } from '../components/CameraStream';
import { apiClient } from '../services/api';
import { Camera, Site, CameraType } from '../types/api';
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
    setStreamModalVisible(true);
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
      title: 'Webcam Index',
      dataIndex: 'device_index',
      key: 'device_index',
      render: (index?: number) => index !== null && index !== undefined ? (
        <span className="font-mono bg-gray-100 px-2 py-1 rounded">{index}</span>
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
      render: (_, camera: Camera) => {
        const isStreaming = streamStatuses[camera.camera_id];
        
        return (
          <Space>
            {!isStreaming ? (
              <Tooltip title="View live stream">
                <Button
                  icon={<PlayCircleOutlined />}
                  onClick={() => handleStartStreaming(camera)}
                  size="small"
                  type="primary"
                  disabled={!camera.is_active}
                >
                  Stream
                </Button>
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
                    icon={<StopOutlined />}
                    size="small"
                    danger
                  >
                    Stop
                  </Button>
                </Popconfirm>
              </Tooltip>
            )}
            <Button
              icon={<EditOutlined />}
              onClick={() => handleEditCamera(camera)}
              size="small"
            >
              Edit
            </Button>
            <Popconfirm
              title="Delete Camera"
              description="Are you sure you want to delete this camera?"
              onConfirm={() => handleDeleteCamera(camera)}
              okText="Yes"
              cancelText="No"
            >
              <Button
                icon={<DeleteOutlined />}
                danger
                size="small"
              >
                Delete
              </Button>
            </Popconfirm>
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
            <Radio.Group>
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
                    label="Device Index"
                    rules={[{ required: true, message: 'Please input device index!' }]}
                  >
                    <Input 
                      type="number" 
                      placeholder="e.g. 0 for first webcam, 1 for second" 
                      min={0}
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
        title="Camera Stream"
        open={streamModalVisible}
        onCancel={() => {
          setStreamModalVisible(false);
          setStreamingCamera(null);
        }}
        footer={null}
        width="90%"
        style={{ maxWidth: '800px' }}
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
            autoStart={true}
          />
        )}
      </Modal>
    </div>
  );
};