import React, { useState, useEffect } from 'react';
import {
  Table,
  Card,
  Space,
  Typography,
  Button,
  Tag,
  Tooltip,
  Modal,
  Select,
  InputNumber,
  message,
  Statistic,
  Row,
  Col,
  Descriptions,
  Badge
} from 'antd';
import {
  CameraOutlined,
  PlayCircleOutlined,
  PauseCircleOutlined,
  ReloadOutlined,
  ClearOutlined,
  ThunderboltOutlined,
  ControlOutlined,
  CloseCircleOutlined,
  CheckCircleOutlined
} from '@ant-design/icons';
import { apiClient } from '../services/api';
import type { ColumnsType } from 'antd/es/table';

const { Title } = Typography;
const { Option } = Select;

interface CameraAssignment {
  camera_id: number;
  worker_id: string;
  worker_name: string;
  worker_status: string;
  is_healthy: boolean;
  site_id: number;
  assigned_at: string;
}

interface AssignmentsResponse {
  assignments: Record<string, CameraAssignment>;
  total_assignments: number;
  active_assignments: number;
  stale_assignments: number;
}

interface Worker {
  worker_id: string;
  worker_name: string;
  status: string;
  site_id?: number;
  camera_id?: number;
  is_healthy: boolean;
}

interface Site {
  site_id: number;
  name: string;
}

const WorkerCameraManagement: React.FC = () => {
  const [assignments, setAssignments] = useState<CameraAssignment[]>([]);
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [sites, setSites] = useState<Site[]>([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    total_assignments: 0,
    active_assignments: 0,
    stale_assignments: 0,
  });
  
  // Modal states
  const [assignModalVisible, setAssignModalVisible] = useState(false);
  const [commandModalVisible, setCommandModalVisible] = useState(false);
  const [selectedWorker, setSelectedWorker] = useState<Worker | null>(null);
  
  // Form states
  const [selectedWorkerId, setSelectedWorkerId] = useState<string>('');
  const [selectedSiteId, setSelectedSiteId] = useState<number | undefined>();
  const [selectedCommand, setSelectedCommand] = useState<string>('');
  const [commandTimeout, setCommandTimeout] = useState<number>(5);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      
      // Load assignments, workers, and sites in parallel
      const [assignmentsRes, workersRes, sitesRes] = await Promise.all([
        apiClient.get('/worker-management/assignments'),
        apiClient.get('/registry/workers'),
        apiClient.get('/sites')
      ]);
      
      // Process assignments
      const assignmentsList = Object.values(assignmentsRes.assignments) as CameraAssignment[];
      setAssignments(assignmentsList);
      setStats({
        total_assignments: assignmentsRes.total_assignments,
        active_assignments: assignmentsRes.active_assignments,
        stale_assignments: assignmentsRes.stale_assignments,
      });
      
      // Process workers
      setWorkers(workersRes.workers);
      
      // Process sites
      setSites(sitesRes);
      
    } catch (error) {
      console.error('Failed to load data:', error);
      message.error('Failed to load worker camera management data');
    } finally {
      setLoading(false);
    }
  };

  const handleAssignCamera = async () => {
    if (!selectedWorkerId || !selectedSiteId) {
      message.error('Please select both worker and site');
      return;
    }
    
    try {
      const response = await apiClient.post('/worker-management/assign-camera', {
        worker_id: selectedWorkerId,
        site_id: selectedSiteId
      });
      
      if (response.success) {
        message.success(response.message);
        setAssignModalVisible(false);
        setSelectedWorkerId('');
        setSelectedSiteId(undefined);
        await loadData();
      } else {
        message.warning(response.message);
      }
    } catch (error) {
      console.error('Failed to assign camera:', error);
      message.error('Failed to assign camera');
    }
  };

  const handleReleaseCamera = async (workerId: string, workerName: string) => {
    Modal.confirm({
      title: 'Release Camera',
      content: `Release camera assignment from worker "${workerName}"?`,
      okText: 'Release',
      okType: 'danger',
      onOk: async () => {
        try {
          const response = await apiClient.post(`/worker-management/release-camera/${workerId}`);
          
          if (response.success) {
            message.success(response.message);
            await loadData();
          } else {
            message.warning(response.message);
          }
        } catch (error) {
          console.error('Failed to release camera:', error);
          message.error('Failed to release camera');
        }
      },
    });
  };

  const handleSendCommand = async () => {
    if (!selectedWorker || !selectedCommand) {
      message.error('Please select command');
      return;
    }
    
    try {
      const response = await apiClient.post(`/worker-management/send-command/${selectedWorker.worker_id}`, {
        command: selectedCommand,
        priority: 'high',
        timeout_minutes: commandTimeout
      });
      
      if (response.success) {
        message.success(response.message);
        setCommandModalVisible(false);
        setSelectedCommand('');
        setSelectedWorker(null);
      } else {
        message.error('Failed to send command');
      }
    } catch (error) {
      console.error('Failed to send command:', error);
      message.error('Failed to send command');
    }
  };

  const handleCleanupStale = async () => {
    try {
      const response = await apiClient.post('/worker-management/assignments/cleanup');
      message.success(response.message);
      await loadData();
    } catch (error) {
      console.error('Failed to cleanup stale assignments:', error);
      message.error('Failed to cleanup stale assignments');
    }
  };

  const handleAutoAssign = async () => {
    try {
      const response = await apiClient.post('/worker-management/assignments/auto-assign');
      message.success(response.message);
      await loadData();
    } catch (error) {
      console.error('Failed to auto-assign cameras:', error);
      message.error('Failed to auto-assign cameras');
    }
  };

  const getWorkerStatusColor = (status: string, isHealthy: boolean) => {
    if ((status === 'idle' || status === 'processing') && isHealthy) return 'success';
    if ((status === 'idle' || status === 'processing') && !isHealthy) return 'warning';
    if (status === 'error') return 'error';
    return 'default';
  };

  const getWorkerStatusIcon = (status: string, isHealthy: boolean) => {
    if ((status === 'idle' || status === 'processing') && isHealthy) return <CheckCircleOutlined />;
    if ((status === 'idle' || status === 'processing') && !isHealthy) return <CloseCircleOutlined />;
    return <CloseCircleOutlined />;
  };

  // Get unassigned workers
  const unassignedWorkers = workers.filter(w => !assignments.some(a => a.worker_id === w.worker_id) && w.site_id);

  const columns: ColumnsType<CameraAssignment> = [
    {
      title: 'Camera',
      key: 'camera',
      render: (_, record) => (
        <div className="flex items-center space-x-2">
          <CameraOutlined className="text-blue-500" />
          <div>
            <div className="font-medium">Camera {record.camera_id}</div>
            <div className="text-sm text-gray-500">Site {record.site_id}</div>
          </div>
        </div>
      ),
    },
    {
      title: 'Worker',
      key: 'worker',
      render: (_, record) => (
        <div>
          <div className="font-medium">{record.worker_name}</div>
          <div className="text-sm text-gray-500">{record.worker_id}</div>
        </div>
      ),
    },
    {
      title: 'Status',
      key: 'status',
      render: (_, record) => (
        <Badge 
          status={getWorkerStatusColor(record.worker_status, record.is_healthy) as any}
          text={
            <Space size={4}>
              {getWorkerStatusIcon(record.worker_status, record.is_healthy)}
              <span className={`font-medium ${
                record.is_healthy ? 'text-green-600' : 'text-orange-500'
              }`}>
                {record.is_healthy ? record.worker_status : 'Stale'}
              </span>
            </Space>
          }
        />
      ),
    },
    {
      title: 'Assigned At',
      dataIndex: 'assigned_at',
      key: 'assigned_at',
      render: (dateString: string) => new Date(dateString).toLocaleString(),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_, record) => (
        <Space size="small">
          <Tooltip title="Send Command">
            <Button
              type="text"
              icon={<ControlOutlined />}
              onClick={() => {
                const worker = workers.find(w => w.worker_id === record.worker_id);
                setSelectedWorker(worker || null);
                setCommandModalVisible(true);
              }}
            />
          </Tooltip>
          <Tooltip title="Release Camera">
            <Button
              type="text"
              danger
              icon={<CloseCircleOutlined />}
              onClick={() => handleReleaseCamera(record.worker_id, record.worker_name)}
            />
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <div className="p-6">
      <div className="mb-6">
        <Title level={2} className="mb-4">
          <CameraOutlined className="mr-2" />
          Worker Camera Management
        </Title>
        
        {/* Summary Statistics */}
        <Row gutter={16} className="mb-6">
          <Col span={8}>
            <Card>
              <Statistic
                title="Total Assignments"
                value={stats.total_assignments}
                valueStyle={{ color: '#1890ff' }}
                prefix={<CameraOutlined />}
              />
            </Card>
          </Col>
          <Col span={8}>
            <Card>
              <Statistic
                title="Active Assignments"
                value={stats.active_assignments}
                valueStyle={{ color: '#52c41a' }}
                prefix={<CheckCircleOutlined />}
              />
            </Card>
          </Col>
          <Col span={8}>
            <Card>
              <Statistic
                title="Stale Assignments"
                value={stats.stale_assignments}
                valueStyle={{ color: '#faad14' }}
                prefix={<CloseCircleOutlined />}
              />
            </Card>
          </Col>
        </Row>

        {/* Controls */}
        <div className="flex justify-between items-center mb-4">
          <div>
            <Space>
              <Button
                type="primary"
                icon={<CameraOutlined />}
                onClick={() => setAssignModalVisible(true)}
                disabled={unassignedWorkers.length === 0}
              >
                Assign Camera
              </Button>
              <Button
                icon={<ThunderboltOutlined />}
                onClick={handleAutoAssign}
              >
                Auto Assign
              </Button>
            </Space>
          </div>
          <Space>
            <Button
              icon={<ClearOutlined />}
              onClick={handleCleanupStale}
              disabled={stats.stale_assignments === 0}
            >
              Cleanup Stale
            </Button>
            <Button
              type="primary"
              icon={<ReloadOutlined />}
              loading={loading}
              onClick={loadData}
            >
              Refresh
            </Button>
          </Space>
        </div>

        {/* Assignments Table */}
        <Card title="Camera Assignments">
          <Table
            columns={columns}
            dataSource={assignments}
            rowKey="camera_id"
            loading={loading}
            pagination={{
              showSizeChanger: true,
              showQuickJumper: true,
              showTotal: (total, range) => `${range[0]}-${range[1]} of ${total} assignments`,
            }}
            size="middle"
          />
        </Card>

        {/* Assign Camera Modal */}
        <Modal
          title="Assign Camera to Worker"
          open={assignModalVisible}
          onOk={handleAssignCamera}
          onCancel={() => {
            setAssignModalVisible(false);
            setSelectedWorkerId('');
            setSelectedSiteId(undefined);
          }}
          okText="Assign"
        >
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">Select Worker</label>
              <Select
                style={{ width: '100%' }}
                placeholder="Choose an unassigned worker"
                value={selectedWorkerId}
                onChange={setSelectedWorkerId}
              >
                {unassignedWorkers.map(worker => (
                  <Option key={worker.worker_id} value={worker.worker_id}>
                    {worker.worker_name} - Site {worker.site_id} ({worker.status})
                  </Option>
                ))}
              </Select>
              {unassignedWorkers.length === 0 && (
                <div className="text-gray-500 text-sm mt-2">
                  No unassigned workers available
                </div>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Select Site</label>
              <Select
                style={{ width: '100%' }}
                placeholder="Choose site for camera assignment"
                value={selectedSiteId}
                onChange={setSelectedSiteId}
              >
                {sites.map(site => (
                  <Option key={site.site_id} value={site.site_id}>
                    {site.name} (ID: {site.site_id})
                  </Option>
                ))}
              </Select>
            </div>
          </div>
        </Modal>

        {/* Send Command Modal */}
        <Modal
          title={`Send Command to ${selectedWorker?.worker_name}`}
          open={commandModalVisible}
          onOk={handleSendCommand}
          onCancel={() => {
            setCommandModalVisible(false);
            setSelectedCommand('');
            setSelectedWorker(null);
          }}
          okText="Send Command"
        >
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">Command</label>
              <Select
                style={{ width: '100%' }}
                placeholder="Select command to send"
                value={selectedCommand}
                onChange={setSelectedCommand}
              >
                <Option value="start_processing">Start Processing</Option>
                <Option value="stop_processing">Stop Processing</Option>
                <Option value="start_streaming">Start Streaming</Option>
                <Option value="stop_streaming">Stop Streaming</Option>
                <Option value="status_report">Status Report</Option>
                <Option value="restart">Restart</Option>
              </Select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Timeout (minutes)</label>
              <InputNumber
                style={{ width: '100%' }}
                min={1}
                max={60}
                value={commandTimeout}
                onChange={(value) => setCommandTimeout(value || 5)}
              />
            </div>
            {selectedWorker && (
              <Descriptions size="small" bordered>
                <Descriptions.Item label="Worker" span={3}>{selectedWorker.worker_name}</Descriptions.Item>
                <Descriptions.Item label="Status">{selectedWorker.status}</Descriptions.Item>
                <Descriptions.Item label="Site">{selectedWorker.site_id}</Descriptions.Item>
                <Descriptions.Item label="Camera">{selectedWorker.camera_id || 'None'}</Descriptions.Item>
              </Descriptions>
            )}
          </div>
        </Modal>
      </div>
    </div>
  );
};

export default WorkerCameraManagement;