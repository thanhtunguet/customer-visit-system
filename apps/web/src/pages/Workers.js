import {
  jsx as _jsx,
  jsxs as _jsxs,
  Fragment as _Fragment,
} from 'react/jsx-runtime';
import { useState, useEffect, useRef, useCallback } from 'react';
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
  message,
} from 'antd';
import {
  CloudServerOutlined,
  ReloadOutlined,
  DeleteOutlined,
  InfoCircleOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
  BugOutlined,
} from '@ant-design/icons';
import { apiClient } from '../services/api';
import { WorkerStatus, WorkerStatusHelper } from '@shared/common';
import WorkerLogViewer from '../components/WorkerLogViewer';
const { Title } = Typography;
const { Search } = Input;
const normalizeWorker = (worker) => ({
  ...worker,
  status: WorkerStatusHelper.fromString(worker.status),
});
// WorkersResponse shape no longer used directly
const Workers = () => {
  const [workers, setWorkers] = useState([]);
  const [sites, setSites] = useState([]);
  const [cameras, setCameras] = useState([]);
  const wsRef = useRef(null);
  const [wsConnected, setWsConnected] = useState(false);
  const reconnectTimeoutRef = useRef(null);
  const [loading, setLoading] = useState(true);
  const [summaryStats, setSummaryStats] = useState({
    total_count: 0,
    online_count: 0,
    offline_count: 0,
    error_count: 0,
  });
  const [selectedWorker, setSelectedWorker] = useState(null);
  const [detailsModalVisible, setDetailsModalVisible] = useState(false);
  // Log viewer modal state
  const [logViewerVisible, setLogViewerVisible] = useState(false);
  const [selectedWorkerForLogs, setSelectedWorkerForLogs] = useState(null);
  const [statusFilter, setStatusFilter] = useState(undefined);
  const [siteFilter, setSiteFilter] = useState(undefined);
  const [searchText, setSearchText] = useState('');
  // Setup WebSocket connection once on mount
  useEffect(() => {
    setupWebSocket();
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      // Clear any pending reconnection timeout
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  // Load workers when filters change
  useEffect(() => {
    loadWorkers();
    // Auto-refresh every 30 seconds (fallback)
    const interval = setInterval(loadWorkers, 30000);
    return () => {
      clearInterval(interval);
    };
  }, [statusFilter, siteFilter]); // eslint-disable-line react-hooks/exhaustive-deps
  const setupWebSocket = useCallback(() => {
    // Clean up existing connection first
    if (wsRef.current && wsRef.current.readyState !== WebSocket.CLOSED) {
      wsRef.current.close();
    }
    // Clear any existing reconnection timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    const token = localStorage.getItem('access_token');
    const currentTenant = apiClient.getCurrentTenant();
    if (!token || !currentTenant) {
      console.warn('No token or tenant for WebSocket connection');
      return;
    }
    try {
      const wsUrl = apiClient.getWorkerWebSocketUrl(currentTenant);
      const ws = new WebSocket(wsUrl);
      ws.onopen = () => {
        console.log('WebSocket connected');
        setWsConnected(true);
      };
      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          console.log('WebSocket message received:', message);
          if (message.type === 'initial_data') {
            const normalizedWorkers = Array.isArray(message.data)
              ? message.data.map((worker) => normalizeWorker(worker))
              : [];
            setWorkers(normalizedWorkers);
            // Update summary stats
            const total = normalizedWorkers.length;
            const online = normalizedWorkers.filter(
              (w) => WorkerStatusHelper.isActive(w.status) && w.is_healthy
            ).length;
            const offline = normalizedWorkers.filter(
              (w) => w.status === WorkerStatus.OFFLINE || !w.is_healthy
            ).length;
            const error = normalizedWorkers.filter(
              (w) => w.status === WorkerStatus.ERROR
            ).length;
            setSummaryStats({
              total_count: total,
              online_count: online,
              offline_count: offline,
              error_count: error,
            });
          } else if (
            message.type === 'worker_registered' ||
            message.type === 'worker_updated' ||
            message.type === 'worker_status_changed'
          ) {
            const updatedWorker = normalizeWorker(message.data);
            setWorkers((prev) => {
              const newWorkers = prev.map((w) =>
                w.worker_id === updatedWorker.worker_id ? updatedWorker : w
              );
              // If worker doesn't exist, add it
              if (!prev.find((w) => w.worker_id === updatedWorker.worker_id)) {
                newWorkers.push(updatedWorker);
              }
              // Update summary stats
              const total = newWorkers.length;
              const online = newWorkers.filter(
                (w) => WorkerStatusHelper.isActive(w.status) && w.is_healthy
              ).length;
              const offline = newWorkers.filter(
                (w) => w.status === WorkerStatus.OFFLINE || !w.is_healthy
              ).length;
              const error = newWorkers.filter(
                (w) => w.status === WorkerStatus.ERROR
              ).length;
              setSummaryStats({
                total_count: total,
                online_count: online,
                offline_count: offline,
                error_count: error,
              });
              return newWorkers;
            });
          } else if (message.type === 'worker_removed') {
            const removedWorkerId = message.data.worker_id;
            setWorkers((prev) => {
              const newWorkers = prev.filter(
                (w) => w.worker_id !== removedWorkerId
              );
              // Update summary stats
              const total = newWorkers.length;
              const online = newWorkers.filter(
                (w) => WorkerStatusHelper.isActive(w.status) && w.is_healthy
              ).length;
              const offline = newWorkers.filter(
                (w) => w.status === WorkerStatus.OFFLINE || !w.is_healthy
              ).length;
              const error = newWorkers.filter(
                (w) => w.status === WorkerStatus.ERROR
              ).length;
              setSummaryStats({
                total_count: total,
                online_count: online,
                offline_count: offline,
                error_count: error,
              });
              return newWorkers;
            });
          } else if (message.type === 'ping') {
            // Respond to ping
            console.log('WebSocket ping received, sending pong');
            try {
              ws.send('pong');
            } catch (error) {
              console.error('Failed to send pong:', error);
            }
          } else {
            console.log(
              'Unknown WebSocket message type:',
              message.type,
              message
            );
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };
      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setWsConnected(false);
        // Clear any existing timeout and set up reconnection
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current);
        }
        // Reconnect after 5 seconds only if component is still mounted
        reconnectTimeoutRef.current = setTimeout(() => {
          if (
            wsRef.current === null ||
            wsRef.current.readyState === WebSocket.CLOSED
          ) {
            setupWebSocket();
          }
        }, 5000);
      };
      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setWsConnected(false);
      };
      wsRef.current = ws;
    } catch (error) {
      console.error('Error setting up WebSocket:', error);
    }
  }, []); // No dependencies needed as it uses refs and doesn't depend on state
  const loadWorkers = useCallback(async () => {
    try {
      setLoading(true);
      // Load workers and sites first
      const [workersResponse, sitesResponse] = await Promise.all([
        apiClient.getWorkers({
          status: statusFilter,
          include_offline: true,
        }),
        apiClient.get('/sites'),
      ]);
      // Load cameras for all sites
      const camerasPromises = sitesResponse.map((site) =>
        apiClient.get(`/sites/${site.site_id}/cameras`)
      );
      const camerasResponses = await Promise.all(camerasPromises);
      // Flatten all cameras from all sites
      const allCameras = camerasResponses.flat();
      setWorkers(
        workersResponse.workers.map((worker) => normalizeWorker(worker))
      );
      setSites(sitesResponse);
      setCameras(allCameras);
      setSummaryStats({
        total_count: workersResponse.total_count,
        online_count: workersResponse.online_count,
        offline_count: workersResponse.offline_count,
        error_count: workersResponse.error_count,
      });
    } catch (error) {
      console.error('Failed to load workers:', error);
      message.error('Failed to load workers');
    } finally {
      setLoading(false);
    }
  }, [statusFilter]); // Only depend on statusFilter as it's used in the API call
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
  const handleDeleteWorker = async (workerId, workerName) => {
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
  const getStatusColor = (status, isHealthy) => {
    if (WorkerStatusHelper.isActive(status) && isHealthy) return 'success';
    if (WorkerStatusHelper.isActive(status) && !isHealthy) return 'warning';
    if (status === WorkerStatus.ERROR) return 'error';
    if (status === WorkerStatus.MAINTENANCE) return 'processing';
    return 'default';
  };
  const getStatusIcon = (status, isHealthy) => {
    if (WorkerStatusHelper.isActive(status) && isHealthy)
      return _jsx(CheckCircleOutlined, {});
    if (WorkerStatusHelper.isActive(status) && !isHealthy)
      return _jsx(ExclamationCircleOutlined, {});
    if (status === WorkerStatus.ERROR) return _jsx(CloseCircleOutlined, {});
    if (status === WorkerStatus.MAINTENANCE)
      return _jsx(SyncOutlined, { spin: true });
    return _jsx(CloseCircleOutlined, {});
  };
  const formatUptime = (minutes) => {
    if (!minutes) return 'N/A';
    if (minutes < 60) return `${minutes}m`;
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return `${hours}h ${mins}m`;
  };
  const formatDateTime = (dateString) => {
    if (!dateString) return 'Never';
    return new Date(dateString).toLocaleString();
  };
  const getSiteName = (siteId) => {
    if (!siteId) return null;
    const site = sites.find((s) => s.site_id === siteId);
    return site ? site.name : `Site ${siteId}`;
  };
  const getCameraName = (cameraId) => {
    if (!cameraId) return null;
    const camera = cameras.find((c) => c.camera_id === cameraId);
    return camera ? camera.name : `Camera ${cameraId}`;
  };
  const filteredWorkers = workers.filter((worker) => {
    // Apply search text filter
    if (
      searchText &&
      !(
        worker.worker_name.toLowerCase().includes(searchText.toLowerCase()) ||
        worker.hostname.toLowerCase().includes(searchText.toLowerCase()) ||
        worker.ip_address?.toLowerCase().includes(searchText.toLowerCase())
      )
    ) {
      return false;
    }
    // Apply site filter
    if (siteFilter && worker.site_id !== siteFilter) {
      return false;
    }
    return true;
  });
  const columns = [
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status, record) =>
        _jsx('div', {
          className: 'text-center',
          children: _jsx(Badge, {
            status: getStatusColor(status, record.is_healthy),
            text: _jsxs(Space, {
              size: 4,
              children: [
                getStatusIcon(status, record.is_healthy),
                _jsx('span', {
                  className: `font-medium ${
                    WorkerStatusHelper.isActive(status) && record.is_healthy
                      ? 'text-green-600'
                      : WorkerStatusHelper.isActive(status) &&
                          !record.is_healthy
                        ? 'text-orange-500'
                        : status === WorkerStatus.ERROR
                          ? 'text-red-600'
                          : status === WorkerStatus.MAINTENANCE
                            ? 'text-blue-600'
                            : 'text-gray-500'
                  }`,
                  children:
                    WorkerStatusHelper.isActive(status) && !record.is_healthy
                      ? 'Stale'
                      : WorkerStatusHelper.getDisplayLabel(status),
                }),
              ],
            }),
          }),
        }),
    },
    {
      title: 'Worker ID',
      dataIndex: 'worker_id',
      key: 'worker_id',
      width: 140,
      render: (workerId) =>
        _jsx('div', {
          className: 'font-mono text-xs',
          children: _jsx('code', {
            className: 'bg-gray-100 px-2 py-1 rounded text-gray-700',
            children: workerId,
          }),
        }),
    },
    {
      title: 'Worker',
      key: 'worker',
      render: (_, record) =>
        _jsxs('div', {
          children: [
            _jsx('div', {
              className: 'font-medium',
              children: record.worker_name,
            }),
            _jsxs('div', {
              className: 'text-sm text-gray-500',
              children: [
                record.hostname,
                record.ip_address && ` • ${record.ip_address}`,
              ],
            }),
            record.worker_version &&
              _jsxs('div', {
                className: 'text-xs text-gray-400',
                children: ['v', record.worker_version],
              }),
          ],
        }),
    },
    {
      title: 'Site',
      key: 'site',
      width: 120,
      render: (_, record) =>
        _jsx('div', {
          children: record.site_id
            ? _jsx('span', {
                className: 'font-medium',
                children: getSiteName(record.site_id),
              })
            : _jsx('span', {
                className: 'text-gray-400 text-sm',
                children: 'Unassigned',
              }),
        }),
    },
    {
      title: 'Camera & Streaming',
      key: 'camera',
      width: 160,
      render: (_, record) =>
        _jsx('div', {
          children: record.camera_id
            ? _jsxs('div', {
                children: [
                  _jsx('span', {
                    className: 'font-medium',
                    children: getCameraName(record.camera_id),
                  }),
                  record.capabilities &&
                    _jsx('div', {
                      className: 'text-xs mt-1',
                      children:
                        (record.capabilities.total_active_streams || 0) > 0
                          ? _jsxs(Tag, {
                              color: 'green',
                              className: 'text-xs',
                              children: [
                                'Streaming (',
                                record.capabilities.total_active_streams,
                                ')',
                              ],
                            })
                          : _jsx(Tag, {
                              color: 'gray',
                              className: 'text-xs',
                              children: 'Not streaming',
                            }),
                    }),
                ],
              })
            : _jsx('span', {
                className: 'text-gray-400 text-sm',
                children: 'Unassigned',
              }),
        }),
    },
    {
      title: 'Stats',
      key: 'stats',
      width: 120,
      render: (_, record) =>
        _jsxs('div', {
          children: [
            _jsxs('div', {
              className: 'text-sm',
              children: [
                'Faces:',
                ' ',
                _jsx('span', {
                  className: 'font-medium',
                  children: (
                    record.total_faces_processed || 0
                  ).toLocaleString(),
                }),
              ],
            }),
            _jsxs('div', {
              className: 'text-sm',
              children: [
                'Uptime:',
                ' ',
                _jsx('span', {
                  className: 'font-medium',
                  children: formatUptime(record.uptime_minutes),
                }),
              ],
            }),
            record.error_count > 0 &&
              _jsxs('div', {
                className: 'text-sm text-red-500',
                children: [
                  'Errors:',
                  ' ',
                  _jsx('span', {
                    className: 'font-medium',
                    children: record.error_count || 0,
                  }),
                ],
              }),
          ],
        }),
    },
    {
      title: 'Last Seen',
      dataIndex: 'last_heartbeat',
      key: 'last_heartbeat',
      width: 140,
      render: (dateString) =>
        _jsx('div', {
          children: _jsx('div', {
            className: 'text-sm',
            children: formatDateTime(dateString),
          }),
        }),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 150,
      render: (_, record) =>
        _jsxs(Space, {
          size: 'small',
          children: [
            _jsx(Tooltip, {
              title: 'View Logs',
              children: _jsx(Button, {
                type: 'text',
                icon: _jsx(BugOutlined, {}),
                onClick: () => {
                  setSelectedWorkerForLogs(record);
                  setLogViewerVisible(true);
                },
              }),
            }),
            _jsx(Tooltip, {
              title: 'View Details',
              children: _jsx(Button, {
                type: 'text',
                icon: _jsx(InfoCircleOutlined, {}),
                onClick: () => {
                  setSelectedWorker(record);
                  setDetailsModalVisible(true);
                },
              }),
            }),
            _jsx(Tooltip, {
              title: 'Delete Worker',
              children: _jsx(Button, {
                type: 'text',
                danger: true,
                icon: _jsx(DeleteOutlined, {}),
                onClick: () =>
                  handleDeleteWorker(record.worker_id, record.worker_name),
              }),
            }),
          ],
        }),
    },
  ];
  return _jsx('div', {
    className: 'p-6',
    children: _jsxs('div', {
      className: 'mb-6',
      children: [
        _jsxs(Title, {
          level: 2,
          className: 'mb-4',
          children: [
            _jsx(CloudServerOutlined, { className: 'mr-2' }),
            'Workers Management',
          ],
        }),
        _jsxs(Row, {
          gutter: 16,
          className: 'mb-6',
          children: [
            _jsx(Col, {
              span: 6,
              children: _jsx(Card, {
                children: _jsx(Statistic, {
                  title: 'Total Workers',
                  value: summaryStats.total_count,
                  valueStyle: { color: '#1890ff' },
                  prefix: _jsx(CloudServerOutlined, {}),
                }),
              }),
            }),
            _jsx(Col, {
              span: 6,
              children: _jsx(Card, {
                children: _jsx(Statistic, {
                  title: 'Online & Healthy',
                  value: summaryStats.online_count,
                  valueStyle: { color: '#52c41a' },
                  prefix: _jsx(CheckCircleOutlined, {}),
                }),
              }),
            }),
            _jsx(Col, {
              span: 6,
              children: _jsx(Card, {
                children: _jsx(Statistic, {
                  title: 'Offline / Stale',
                  value: summaryStats.offline_count,
                  valueStyle: { color: '#faad14' },
                  prefix: _jsx(ExclamationCircleOutlined, {}),
                }),
              }),
            }),
            _jsx(Col, {
              span: 6,
              children: _jsx(Card, {
                children: _jsx(Statistic, {
                  title: 'Errors',
                  value: summaryStats.error_count,
                  valueStyle: { color: '#ff4d4f' },
                  prefix: _jsx(CloseCircleOutlined, {}),
                }),
              }),
            }),
          ],
        }),
        _jsxs('div', {
          className:
            'flex flex-col lg:flex-row lg:justify-between lg:items-center gap-4 mb-4',
          children: [
            _jsxs('div', {
              className: 'flex flex-col sm:flex-row gap-2',
              children: [
                _jsx(Search, {
                  placeholder: 'Search workers...',
                  allowClear: true,
                  className: 'w-full sm:w-64',
                  value: searchText,
                  onChange: (e) => setSearchText(e.target.value),
                }),
                _jsx(Select, {
                  placeholder: 'Filter by status',
                  allowClear: true,
                  className: 'w-full sm:w-36',
                  value: statusFilter,
                  onChange: setStatusFilter,
                  options: WorkerStatusHelper.getStatusOptions(),
                }),
                _jsx(Select, {
                  placeholder: 'Filter by site',
                  allowClear: true,
                  className: 'w-full sm:w-36',
                  value: siteFilter,
                  onChange: setSiteFilter,
                  options: sites.map((site) => ({
                    value: site.site_id,
                    label: site.name,
                  })),
                }),
              ],
            }),
            _jsxs('div', {
              className:
                'flex flex-col sm:flex-row gap-2 items-start sm:items-center',
              children: [
                _jsxs('div', {
                  className: 'flex items-center space-x-2',
                  children: [
                    _jsx('div', {
                      className: `w-2 h-2 rounded-full ${wsConnected ? 'bg-green-500' : 'bg-red-500'}`,
                    }),
                    _jsx('span', {
                      className: 'text-sm text-gray-500',
                      children: wsConnected ? 'Live' : 'Disconnected',
                    }),
                  ],
                }),
                _jsxs('div', {
                  className: 'flex gap-2',
                  children: [
                    _jsx(Button, {
                      icon: _jsx(DeleteOutlined, {}),
                      onClick: handleCleanupStaleWorkers,
                      title: 'Mark stale workers as offline',
                      children: 'Cleanup Stale',
                    }),
                    _jsx(Button, {
                      type: 'primary',
                      icon: _jsx(ReloadOutlined, {}),
                      loading: loading,
                      onClick: loadWorkers,
                      children: 'Refresh',
                    }),
                  ],
                }),
              ],
            }),
          ],
        }),
        summaryStats.offline_count > 0 &&
          _jsx(Alert, {
            message: `${summaryStats.offline_count} worker(s) are offline or stale`,
            description:
              "These workers haven't sent heartbeat recently and may need attention.",
            type: 'warning',
            showIcon: true,
            closable: true,
            className: 'mb-4',
          }),
        _jsx(Card, {
          children: _jsx(Table, {
            columns: columns,
            dataSource: filteredWorkers,
            rowKey: 'worker_id',
            loading: loading,
            pagination: {
              total: filteredWorkers.length,
              pageSize: 50,
              showSizeChanger: true,
              showQuickJumper: true,
              showTotal: (total, range) =>
                `${range[0]}-${range[1]} of ${total} workers`,
            },
            size: 'middle',
          }),
        }),
        _jsx(Modal, {
          title: _jsxs(Space, {
            children: [_jsx(CloudServerOutlined, {}), 'Worker Details'],
          }),
          open: detailsModalVisible,
          onCancel: () => setDetailsModalVisible(false),
          footer: null,
          width: 700,
          children:
            selectedWorker &&
            _jsxs('div', {
              children: [
                _jsxs(Descriptions, {
                  column: 2,
                  bordered: true,
                  size: 'small',
                  children: [
                    _jsx(Descriptions.Item, {
                      label: 'Worker ID',
                      span: 2,
                      children: _jsx('code', {
                        className: 'bg-gray-100 px-2 py-1 rounded text-sm',
                        children: selectedWorker.worker_id,
                      }),
                    }),
                    _jsx(Descriptions.Item, {
                      label: 'Name',
                      children: selectedWorker.worker_name,
                    }),
                    _jsx(Descriptions.Item, {
                      label: 'Version',
                      children: selectedWorker.worker_version || 'N/A',
                    }),
                    _jsx(Descriptions.Item, {
                      label: 'Hostname',
                      children: selectedWorker.hostname,
                    }),
                    _jsx(Descriptions.Item, {
                      label: 'IP Address',
                      children: selectedWorker.ip_address || 'N/A',
                    }),
                    _jsx(Descriptions.Item, {
                      label: 'Status',
                      children: _jsx(Badge, {
                        status: getStatusColor(
                          selectedWorker.status,
                          selectedWorker.is_healthy
                        ),
                        text: _jsxs(Space, {
                          size: 4,
                          children: [
                            getStatusIcon(
                              selectedWorker.status,
                              selectedWorker.is_healthy
                            ),
                            _jsx('span', {
                              children:
                                WorkerStatusHelper.isActive(
                                  selectedWorker.status
                                ) && !selectedWorker.is_healthy
                                  ? 'Stale'
                                  : WorkerStatusHelper.getDisplayLabel(
                                      selectedWorker.status
                                    ),
                            }),
                          ],
                        }),
                      }),
                    }),
                    _jsx(Descriptions.Item, {
                      label: 'Healthy',
                      children: selectedWorker.is_healthy
                        ? _jsx(Tag, { color: 'success', children: 'Yes' })
                        : _jsx(Tag, { color: 'error', children: 'No' }),
                    }),
                    _jsx(Descriptions.Item, {
                      label: 'Site Assignment',
                      children: selectedWorker.site_id
                        ? getSiteName(selectedWorker.site_id)
                        : 'Unassigned',
                    }),
                    _jsx(Descriptions.Item, {
                      label: 'Camera Assignment',
                      children: selectedWorker.camera_id
                        ? getCameraName(selectedWorker.camera_id)
                        : 'Unassigned',
                    }),
                    selectedWorker.capabilities &&
                      _jsxs(_Fragment, {
                        children: [
                          _jsx(Descriptions.Item, {
                            label: 'Active Streams',
                            children: _jsxs(Space, {
                              children: [
                                _jsxs(Tag, {
                                  color:
                                    selectedWorker.capabilities
                                      .total_active_streams > 0
                                      ? 'success'
                                      : 'default',
                                  children: [
                                    selectedWorker.capabilities
                                      .total_active_streams || 0,
                                    ' ',
                                    'cameras streaming',
                                  ],
                                }),
                                selectedWorker.capabilities
                                  .streaming_status_updated &&
                                  _jsxs('span', {
                                    className: 'text-xs text-gray-500',
                                    children: [
                                      'Updated:',
                                      ' ',
                                      new Date(
                                        selectedWorker.capabilities.streaming_status_updated
                                      ).toLocaleString(),
                                    ],
                                  }),
                              ],
                            }),
                          }),
                          _jsx(Descriptions.Item, {
                            label: 'Streaming Cameras',
                            span: 2,
                            children:
                              (
                                selectedWorker.capabilities
                                  .active_camera_streams || []
                              ).length > 0
                                ? _jsx(Space, {
                                    wrap: true,
                                    children: (
                                      selectedWorker.capabilities
                                        .active_camera_streams || []
                                    ).map((cameraId) =>
                                      _jsxs(
                                        Tag,
                                        {
                                          color: 'blue',
                                          children: ['Camera ', cameraId],
                                        },
                                        cameraId
                                      )
                                    ),
                                  })
                                : _jsx('span', {
                                    className: 'text-gray-500',
                                    children: 'No cameras currently streaming',
                                  }),
                          }),
                        ],
                      }),
                    _jsx(Descriptions.Item, {
                      label: 'Faces Processed',
                      children:
                        selectedWorker.total_faces_processed.toLocaleString(),
                    }),
                    _jsx(Descriptions.Item, {
                      label: 'Error Count',
                      children: _jsx('span', {
                        className:
                          selectedWorker.error_count > 0 ? 'text-red-500' : '',
                        children: selectedWorker.error_count,
                      }),
                    }),
                    _jsx(Descriptions.Item, {
                      label: 'Uptime',
                      children: formatUptime(selectedWorker.uptime_minutes),
                    }),
                    _jsx(Descriptions.Item, {
                      label: 'Last Heartbeat',
                      children: formatDateTime(selectedWorker.last_heartbeat),
                    }),
                    _jsx(Descriptions.Item, {
                      label: 'Registered',
                      children: formatDateTime(
                        selectedWorker.registration_time
                      ),
                    }),
                    selectedWorker.last_error &&
                      _jsx(Descriptions.Item, {
                        label: 'Last Error',
                        span: 2,
                        children: _jsx('div', {
                          className:
                            'bg-red-50 border border-red-200 rounded p-2 text-red-700 text-sm',
                          children: selectedWorker.last_error,
                        }),
                      }),
                  ],
                }),
                selectedWorker.capabilities &&
                  _jsxs('div', {
                    className: 'mt-4',
                    children: [
                      _jsx(Title, { level: 5, children: 'Capabilities' }),
                      _jsx('div', {
                        className: 'bg-gray-50 border rounded p-3',
                        children: _jsx('pre', {
                          className: 'text-sm overflow-auto',
                          children: JSON.stringify(
                            selectedWorker.capabilities,
                            null,
                            2
                          ),
                        }),
                      }),
                    ],
                  }),
              ],
            }),
        }),
        _jsx(WorkerLogViewer, {
          visible: logViewerVisible,
          workerId: selectedWorkerForLogs?.worker_id,
          workerName: selectedWorkerForLogs?.worker_name,
          onClose: () => {
            setLogViewerVisible(false);
            setSelectedWorkerForLogs(null);
          },
        }),
      ],
    }),
  });
};
export default Workers;
