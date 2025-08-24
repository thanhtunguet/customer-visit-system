import React, { useState, useEffect, useRef } from 'react';
import {
  Table,
  Card,
  Space,
  Typography,
  Button,
  Tag,
  Tooltip,
  Modal,
  Descriptions,
  Alert,
  Statistic,
  Row,
  Col,
  Badge,
  Select,
  Input,
  message
} from 'antd';
import {
  CloudServerOutlined,
  ReloadOutlined,
  DeleteOutlined,
  InfoCircleOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined
} from '@ant-design/icons';
import { apiClient } from '../services/api';
import type { ColumnsType } from 'antd/es/table';
import { WorkerStatus, WorkerStatusHelper } from '@shared/common';

const { Title, Text } = Typography;
const { Search } = Input;

interface Worker {
  worker_id: string;
  tenant_id: string;
  hostname: string;
  ip_address?: string;
  worker_name: string;
  worker_version?: string;
  capabilities?: Record<string, any>;
  status: WorkerStatus;
  site_id?: number;
  camera_id?: number;
  last_heartbeat?: string;
  last_error?: string;
  error_count: number;
  total_faces_processed: number;
  uptime_minutes?: number;
  registration_time: string;
  is_healthy: boolean;
}

interface WorkersResponse {
  workers: Worker[];
  total_count: number;
  online_count: number;
  offline_count: number;
  error_count: number;
  processing_count: number;
}

const Workers: React.FC = () => {
  const [workers, setWorkers] = useState<Worker[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [summaryStats, setSummaryStats] = useState<{
    total_count: number;
    online_count: number;
    offline_count: number;
    error_count: number;
  }>({ total_count: 0, online_count: 0, offline_count: 0, error_count: 0 });
  
  const [selectedWorker, setSelectedWorker] = useState<Worker | null>(null);
  const [detailsModalVisible, setDetailsModalVisible] = useState(false);
  
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);
  const [searchText, setSearchText] = useState('');

  useEffect(() => {
    loadWorkers();
    setupWebSocket();
    
    // Auto-refresh every 30 seconds (fallback)
    const interval = setInterval(loadWorkers, 30000);
    
    return () => {
      clearInterval(interval);
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [statusFilter]);

  const setupWebSocket = () => {
    const token = localStorage.getItem('access_token');
    const currentTenant = apiClient.getCurrentTenant();
    
    if (!token || !currentTenant) {
      console.warn('No token or tenant for WebSocket connection');
      return;
    }

    try {
      const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/v1/registry/workers/ws/${currentTenant}?token=${token}`;
      const ws = new WebSocket(wsUrl);
      
      ws.onopen = () => {
        console.log('WebSocket connected');
        setWsConnected(true);
      };
      
      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          
          if (message.type === 'initial_data') {
            setWorkers(message.data);
            // Update summary stats
            const total = message.data.length;
            const online = message.data.filter((w: Worker) => WorkerStatusHelper.isActive(w.status) && w.is_healthy).length;
            const offline = message.data.filter((w: Worker) => w.status === WorkerStatus.OFFLINE || !w.is_healthy).length;
            const error = message.data.filter((w: Worker) => w.status === WorkerStatus.ERROR).length;
            
            setSummaryStats({
              total_count: total,
              online_count: online,
              offline_count: offline,
              error_count: error
            });
            
          } else if (message.type === 'worker_registered' || message.type === 'worker_updated' || message.type === 'worker_status_changed') {
            const updatedWorker = message.data;
            
            setWorkers(prev => {
              const newWorkers = prev.map(w => 
                w.worker_id === updatedWorker.worker_id ? updatedWorker : w
              );
              
              // If worker doesn't exist, add it
              if (!prev.find(w => w.worker_id === updatedWorker.worker_id)) {
                newWorkers.push(updatedWorker);
              }
              
              // Update summary stats
              const total = newWorkers.length;
              const online = newWorkers.filter(w => WorkerStatusHelper.isActive(w.status) && w.is_healthy).length;
              const offline = newWorkers.filter(w => w.status === WorkerStatus.OFFLINE || !w.is_healthy).length;
              const error = newWorkers.filter(w => w.status === WorkerStatus.ERROR).length;
              
              setSummaryStats({
                total_count: total,
                online_count: online,
                offline_count: offline,
                error_count: error
              });
              
              return newWorkers;
            });
          } else if (message.type === 'worker_removed') {
            const removedWorkerId = message.data.worker_id;
            
            setWorkers(prev => {
              const newWorkers = prev.filter(w => w.worker_id !== removedWorkerId);
              
              // Update summary stats
              const total = newWorkers.length;
              const online = newWorkers.filter(w => WorkerStatusHelper.isActive(w.status) && w.is_healthy).length;
              const offline = newWorkers.filter(w => w.status === WorkerStatus.OFFLINE || !w.is_healthy).length;
              const error = newWorkers.filter(w => w.status === WorkerStatus.ERROR).length;
              
              setSummaryStats({
                total_count: total,
                online_count: online,
                offline_count: offline,
                error_count: error
              });
              
              return newWorkers;
            });
          } else if (message.type === 'ping') {
            // Respond to ping
            ws.send('pong');
          }
          
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };
      
      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setWsConnected(false);
        
        // Reconnect after 5 seconds
        setTimeout(setupWebSocket, 5000);
      };
      
      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setWsConnected(false);
      };
      
      wsRef.current = ws;
      
    } catch (error) {
      console.error('Error setting up WebSocket:', error);
    }
  };

  const loadWorkers = async () => {
    try {
      setLoading(true);
      
      const response = await apiClient.getWorkers({
        status: statusFilter,
        include_offline: true
      });
      setWorkers(response.workers);
      setSummaryStats({
        total_count: response.total_count,
        online_count: response.online_count,
        offline_count: response.offline_count,
        error_count: response.error_count,
      });
    } catch (error) {
      console.error('Failed to load workers:', error);
      message.error('Failed to load workers');
    } finally {
      setLoading(false);
    }
  };

  const handleCleanupStaleWorkers = async () => {
    try {
      const response = await apiClient.cleanupStaleWorkers(300); // 5 minutes in seconds
      message.success(response.message);
      await loadWorkers();
    } catch (error) {
      console.error('Failed to cleanup stale workers:', error);
      message.error('Failed to cleanup stale workers');
    }
  };

  const handleDeleteWorker = async (workerId: string, workerName: string) => {
    Modal.confirm({
      title: 'Delete Worker',
      content: `Are you sure you want to delete worker "${workerName}"?`,
      okText: 'Delete',
      okType: 'danger',
      onOk: async () => {
        try {
          await apiClient.deleteWorker(workerId);
          message.success('Worker deleted successfully');
          await loadWorkers();
        } catch (error) {
          console.error('Failed to delete worker:', error);
          message.error('Failed to delete worker');
        }
      },
    });
  };

  const getStatusColor = (status: WorkerStatus, isHealthy: boolean) => {
    if (WorkerStatusHelper.isActive(status) && isHealthy) return 'success';
    if (WorkerStatusHelper.isActive(status) && !isHealthy) return 'warning';
    if (status === WorkerStatus.ERROR) return 'error';
    if (status === WorkerStatus.MAINTENANCE) return 'processing';
    return 'default';
  };

  const getStatusIcon = (status: WorkerStatus, isHealthy: boolean) => {
    if (WorkerStatusHelper.isActive(status) && isHealthy) return <CheckCircleOutlined />;
    if (WorkerStatusHelper.isActive(status) && !isHealthy) return <ExclamationCircleOutlined />;
    if (status === WorkerStatus.ERROR) return <CloseCircleOutlined />;
    if (status === WorkerStatus.MAINTENANCE) return <SyncOutlined spin />;
    return <CloseCircleOutlined />;
  };

  const formatUptime = (minutes?: number) => {
    if (!minutes) return 'N/A';
    if (minutes < 60) return `${minutes}m`;
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return `${hours}h ${mins}m`;
  };

  const formatDateTime = (dateString?: string) => {
    if (!dateString) return 'Never';
    return new Date(dateString).toLocaleString();
  };

  const filteredWorkers = workers.filter(worker => {
    if (!searchText) return true;
    return (
      worker.worker_name.toLowerCase().includes(searchText.toLowerCase()) ||
      worker.hostname.toLowerCase().includes(searchText.toLowerCase()) ||
      (worker.ip_address?.toLowerCase().includes(searchText.toLowerCase()))
    );
  });

  const columns: ColumnsType<Worker> = [
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: WorkerStatus, record: Worker) => (
        <div className="text-center">
          <Badge 
            status={getStatusColor(status, record.is_healthy) as any}
            text={
              <Space size={4}>
                {getStatusIcon(status, record.is_healthy)}
                <span className={`font-medium ${
                  WorkerStatusHelper.isActive(status) && record.is_healthy ? 'text-green-600' :
                  WorkerStatusHelper.isActive(status) && !record.is_healthy ? 'text-orange-500' :
                  status === WorkerStatus.ERROR ? 'text-red-600' :
                  status === WorkerStatus.MAINTENANCE ? 'text-blue-600' :
                  'text-gray-500'
                }`}>
                  {WorkerStatusHelper.isActive(status) && !record.is_healthy ? 'Stale' : WorkerStatusHelper.getDisplayLabel(status)}
                </span>
              </Space>
            }
          />
        </div>
      ),
    },
    {
      title: 'Worker',
      key: 'worker',
      render: (_, record: Worker) => (
        <div>
          <div className="font-medium">{record.worker_name}</div>
          <div className="text-sm text-gray-500">
            {record.hostname}
            {record.ip_address && ` • ${record.ip_address}`}
          </div>
          {record.worker_version && (
            <div className="text-xs text-gray-400">v{record.worker_version}</div>
          )}
        </div>
      ),
    },
    {
      title: 'Assignment',
      key: 'assignment',
      width: 140,
      render: (_, record: Worker) => (
        <div>
          {record.site_id && <div className="text-sm">Site: {record.site_id}</div>}
          {record.camera_id && <div className="text-sm">Camera: {record.camera_id}</div>}
          {!record.site_id && !record.camera_id && (
            <span className="text-gray-400 text-sm">Unassigned</span>
          )}
        </div>
      ),
    },
    {
      title: 'Stats',
      key: 'stats',
      width: 120,
      render: (_, record: Worker) => (
        <div>
          <div className="text-sm">
            Faces: <span className="font-medium">{record.total_faces_processed.toLocaleString()}</span>
          </div>
          <div className="text-sm">
            Uptime: <span className="font-medium">{formatUptime(record.uptime_minutes)}</span>
          </div>
          {record.error_count > 0 && (
            <div className="text-sm text-red-500">
              Errors: <span className="font-medium">{record.error_count}</span>
            </div>
          )}
        </div>
      ),
    },
    {
      title: 'Last Seen',
      dataIndex: 'last_heartbeat',
      key: 'last_heartbeat',
      width: 140,
      render: (dateString: string) => (
        <div>
          <div className="text-sm">{formatDateTime(dateString)}</div>
        </div>
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 120,
      render: (_, record: Worker) => (
        <Space size="small">
          <Tooltip title="View Details">
            <Button
              type="text"
              icon={<InfoCircleOutlined />}
              onClick={() => {
                setSelectedWorker(record);
                setDetailsModalVisible(true);
              }}
            />
          </Tooltip>
          <Tooltip title="Delete Worker">
            <Button
              type="text"
              danger
              icon={<DeleteOutlined />}
              onClick={() => handleDeleteWorker(record.worker_id, record.worker_name)}
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
          <CloudServerOutlined className="mr-2" />
          Workers Management
        </Title>
        
        {/* Summary Statistics */}
        <Row gutter={16} className="mb-6">
          <Col span={6}>
            <Card>
              <Statistic
                title="Total Workers"
                value={summaryStats.total_count}
                valueStyle={{ color: '#1890ff' }}
                prefix={<CloudServerOutlined />}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="Online & Healthy"
                value={summaryStats.online_count}
                valueStyle={{ color: '#52c41a' }}
                prefix={<CheckCircleOutlined />}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="Offline / Stale"
                value={summaryStats.offline_count}
                valueStyle={{ color: '#faad14' }}
                prefix={<ExclamationCircleOutlined />}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="Errors"
                value={summaryStats.error_count}
                valueStyle={{ color: '#ff4d4f' }}
                prefix={<CloseCircleOutlined />}
              />
            </Card>
          </Col>
        </Row>

        {/* Controls */}
        <div className="flex justify-between items-center mb-4">
          <Space>
            <Search
              placeholder="Search workers..."
              allowClear
              style={{ width: 250 }}
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
            />
            <Select
              placeholder="Filter by status"
              allowClear
              style={{ width: 150 }}
              value={statusFilter}
              onChange={setStatusFilter}
              options={WorkerStatusHelper.getStatusOptions()}
            />
          </Space>
          <Space>
            <div className="flex items-center space-x-2">
              <div className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-green-500' : 'bg-red-500'}`}></div>
              <span className="text-sm text-gray-500">
                {wsConnected ? 'Live' : 'Disconnected'}
              </span>
            </div>
            <Button
              icon={<DeleteOutlined />}
              onClick={handleCleanupStaleWorkers}
              title="Mark stale workers as offline"
            >
              Cleanup Stale
            </Button>
            <Button
              type="primary"
              icon={<ReloadOutlined />}
              loading={loading}
              onClick={loadWorkers}
            >
              Refresh
            </Button>
          </Space>
        </div>

        {/* Alert for offline workers */}
        {summaryStats.offline_count > 0 && (
          <Alert
            message={`${summaryStats.offline_count} worker(s) are offline or stale`}
            description="These workers haven't sent heartbeat recently and may need attention."
            type="warning"
            showIcon
            closable
            className="mb-4"
          />
        )}

        {/* Workers Table */}
        <Card>
          <Table
            columns={columns}
            dataSource={filteredWorkers}
            rowKey="worker_id"
            loading={loading}
            pagination={{
              total: filteredWorkers.length,
              pageSize: 50,
              showSizeChanger: true,
              showQuickJumper: true,
              showTotal: (total, range) => `${range[0]}-${range[1]} of ${total} workers`,
            }}
            size="middle"
          />
        </Card>

        {/* Worker Details Modal */}
        <Modal
          title={
            <Space>
              <CloudServerOutlined />
              Worker Details
            </Space>
          }
          open={detailsModalVisible}
          onCancel={() => setDetailsModalVisible(false)}
          footer={null}
          width={700}
        >
          {selectedWorker && (
            <div>
              <Descriptions column={2} bordered size="small">
                <Descriptions.Item label="Worker ID" span={2}>
                  <code className="bg-gray-100 px-2 py-1 rounded text-sm">
                    {selectedWorker.worker_id}
                  </code>
                </Descriptions.Item>
                <Descriptions.Item label="Name">
                  {selectedWorker.worker_name}
                </Descriptions.Item>
                <Descriptions.Item label="Version">
                  {selectedWorker.worker_version || 'N/A'}
                </Descriptions.Item>
                <Descriptions.Item label="Hostname">
                  {selectedWorker.hostname}
                </Descriptions.Item>
                <Descriptions.Item label="IP Address">
                  {selectedWorker.ip_address || 'N/A'}
                </Descriptions.Item>
                <Descriptions.Item label="Status">
                  <Badge 
                    status={getStatusColor(selectedWorker.status, selectedWorker.is_healthy) as any}
                    text={
                      <Space size={4}>
                        {getStatusIcon(selectedWorker.status, selectedWorker.is_healthy)}
                        <span>{WorkerStatusHelper.isActive(selectedWorker.status) && !selectedWorker.is_healthy ? 'Stale' : WorkerStatusHelper.getDisplayLabel(selectedWorker.status)}</span>
                      </Space>
                    }
                  />
                </Descriptions.Item>
                <Descriptions.Item label="Healthy">
                  {selectedWorker.is_healthy ? (
                    <Tag color="success">Yes</Tag>
                  ) : (
                    <Tag color="error">No</Tag>
                  )}
                </Descriptions.Item>
                <Descriptions.Item label="Site Assignment">
                  {selectedWorker.site_id || 'Unassigned'}
                </Descriptions.Item>
                <Descriptions.Item label="Camera Assignment">
                  {selectedWorker.camera_id || 'Unassigned'}
                </Descriptions.Item>
                <Descriptions.Item label="Faces Processed">
                  {selectedWorker.total_faces_processed.toLocaleString()}
                </Descriptions.Item>
                <Descriptions.Item label="Error Count">
                  <span className={selectedWorker.error_count > 0 ? 'text-red-500' : ''}>
                    {selectedWorker.error_count}
                  </span>
                </Descriptions.Item>
                <Descriptions.Item label="Uptime">
                  {formatUptime(selectedWorker.uptime_minutes)}
                </Descriptions.Item>
                <Descriptions.Item label="Last Heartbeat">
                  {formatDateTime(selectedWorker.last_heartbeat)}
                </Descriptions.Item>
                <Descriptions.Item label="Registered">
                  {formatDateTime(selectedWorker.registration_time)}
                </Descriptions.Item>
                {selectedWorker.last_error && (
                  <Descriptions.Item label="Last Error" span={2}>
                    <div className="bg-red-50 border border-red-200 rounded p-2 text-red-700 text-sm">
                      {selectedWorker.last_error}
                    </div>
                  </Descriptions.Item>
                )}
              </Descriptions>
              
              {selectedWorker.capabilities && (
                <div className="mt-4">
                  <Title level={5}>Capabilities</Title>
                  <div className="bg-gray-50 border rounded p-3">
                    <pre className="text-sm overflow-auto">
                      {JSON.stringify(selectedWorker.capabilities, null, 2)}
                    </pre>
                  </div>
                </div>
              )}
            </div>
          )}
        </Modal>
      </div>
    </div>
  );
};

export default Workers;