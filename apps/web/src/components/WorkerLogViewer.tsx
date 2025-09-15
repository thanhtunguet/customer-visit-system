import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Modal,
  Typography,
  Space,
  Button,
  Tag,
  Alert,
  Switch,
  Select,
  Input,
  Spin,
  App
} from 'antd';
import {
  PlayCircleOutlined,
  PauseCircleOutlined,
  ClearOutlined,
  DownloadOutlined,
  ReloadOutlined,
  BugOutlined
} from '@ant-design/icons';
import { apiClient } from '../services/api';

const { Text } = Typography;
const { Search } = Input;

interface LogEntry {
  timestamp: string;
  level: string;
  logger: string;
  message: string;
  module?: string;
  funcName?: string;
  lineno?: number;
  exception?: string;
}

interface WorkerLogViewerProps {
  visible: boolean;
  onClose: () => void;
  workerId: string;
  workerName: string;
}

const WorkerLogViewer: React.FC<WorkerLogViewerProps> = ({
  visible,
  onClose,
  workerId,
  workerName
}) => {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const [levelFilter, setLevelFilter] = useState<string>('all');
  const [searchFilter, setSearchFilter] = useState('');
  const [error, setError] = useState<string | null>(null);
  
  const logsContainerRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const { notification } = App.useApp();

  // Filter logs based on level and search
  const filteredLogs = logs.filter(log => {
    const matchesLevel = levelFilter === 'all' || log.level.toLowerCase() === levelFilter.toLowerCase();
    const matchesSearch = !searchFilter || 
      log.message.toLowerCase().includes(searchFilter.toLowerCase()) ||
      log.logger.toLowerCase().includes(searchFilter.toLowerCase());
    return matchesLevel && matchesSearch;
  });

  // Auto-scroll to bottom when new logs arrive
  const scrollToBottom = useCallback(() => {
    if (autoScroll && logsContainerRef.current) {
      logsContainerRef.current.scrollTop = logsContainerRef.current.scrollHeight;
    }
  }, [autoScroll]);

  // Load recent logs
  const loadRecentLogs = async () => {
    if (!workerId) return;
    
    setLoading(true);
    setError(null);
    
    try {
      console.log('Loading logs for worker:', workerId);
      console.log('API call URL:', `/worker-management/workers/${workerId}/logs/recent?limit=100`);
      const response = await apiClient.get(`/worker-management/workers/${workerId}/logs/recent?limit=100`);
      console.log('API response:', response);
      console.log('Response type:', typeof response);
      console.log('Response.logs:', response.logs);
      
      if (response && response.logs) {
        setLogs(response.logs);
      } else {
        console.error('Unexpected response structure:', response);
        setLogs([]);
      }
      setTimeout(scrollToBottom, 100); // Allow DOM to update
    } catch (err: any) {
      console.error('Error loading logs:', err);
      console.error('Error response:', err.response);
      const errorMsg = err.response?.data?.detail || 'Failed to load logs';
      setError(errorMsg);
      notification.error({
        message: 'Log Loading Failed',
        description: errorMsg
      });
    } finally {
      setLoading(false);
    }
  };

  // Start streaming logs
  const startStreaming = () => {
    if (!workerId || eventSourceRef.current) return;
    
    try {
      const token = localStorage.getItem('access_token');
      const streamUrl = `${apiClient.baseURL}/worker-management/workers/${workerId}/logs/stream?access_token=${encodeURIComponent(token || '')}`;
      
      const eventSource = new EventSource(streamUrl);
      
      eventSource.onopen = () => {
        setStreaming(true);
        setError(null);
        notification.success({
          message: 'Log Stream Connected',
          description: 'Real-time logs are now streaming'
        });
      };
      
      eventSource.addEventListener('initial_logs', (event) => {
        try {
          const data = JSON.parse(event.data);
          setLogs(data.logs || []);
          setTimeout(scrollToBottom, 100);
        } catch (e) {
          console.error('Error parsing initial logs:', e);
        }
      });
      
      eventSource.addEventListener('new_logs', (event) => {
        try {
          const data = JSON.parse(event.data);
          setLogs(prev => [...prev, ...data.logs]);
          setTimeout(scrollToBottom, 100);
        } catch (e) {
          console.error('Error parsing new logs:', e);
        }
      });
      
      eventSource.addEventListener('error', (event: any) => {
        try {
          const data = JSON.parse(event.data);
          setError(data.message || 'Stream error occurred');
        } catch (e) {
          setError('Connection error occurred');
        }
      });
      
      eventSource.onerror = (event) => {
        console.error('EventSource error:', event);
        setStreaming(false);
        setError('Stream connection failed');
        eventSource.close();
        eventSourceRef.current = null;
      };
      
      eventSourceRef.current = eventSource;
      
    } catch (err: any) {
      setError('Failed to start log stream');
      notification.error({
        message: 'Stream Failed',
        description: 'Failed to start log streaming'
      });
    }
  };

  // Stop streaming logs
  const stopStreaming = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setStreaming(false);
  };

  // Generate test logs
  const generateTestLogs = async () => {
    try {
      await apiClient.post(`/worker-management/workers/${workerId}/logs/test`);
      notification.success({
        message: 'Test Logs Generated',
        description: 'Test log entries have been generated'
      });
    } catch (err: any) {
      notification.error({
        message: 'Test Failed',
        description: err.response?.data?.detail || 'Failed to generate test logs'
      });
    }
  };

  // Clear logs
  const clearLogs = () => {
    setLogs([]);
  };

  // Download logs
  const downloadLogs = () => {
    const logText = filteredLogs.map(log => 
      `${log.timestamp} [${log.level}] ${log.logger}: ${log.message}${log.exception ? '\n' + log.exception : ''}`
    ).join('\n');
    
    const blob = new Blob([logText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `worker-${workerId}-logs-${new Date().toISOString().slice(0, 19).replace(/[:.]/g, '-')}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // Get level color
  const getLevelColor = (level: string): string => {
    switch (level.toUpperCase()) {
      case 'ERROR': return '#ff4d4f';
      case 'WARNING': return '#faad14';
      case 'INFO': return '#1890ff';
      case 'DEBUG': return '#52c41a';
      default: return '#8c8c8c';
    }
  };

  // Format timestamp
  const formatTimestamp = (timestamp: string): string => {
    try {
      return new Date(timestamp).toLocaleTimeString();
    } catch {
      return timestamp;
    }
  };

  // Load logs when modal opens
  useEffect(() => {
    if (visible && workerId) {
      loadRecentLogs();
    }
  }, [visible, workerId]);

  // Cleanup on unmount or close
  useEffect(() => {
    return () => {
      stopStreaming();
    };
  }, []);

  return (
    <Modal
      title={
        <Space>
          <BugOutlined />
          <span>Worker Logs - {workerName}</span>
          <Tag color={streaming ? 'green' : 'default'}>
            {streaming ? 'Streaming' : 'Offline'}
          </Tag>
        </Space>
      }
      open={visible}
      onCancel={() => {
        stopStreaming();
        onClose();
      }}
      width={1200}
      footer={null}
      styles={{
        body: { padding: 0 }
      }}
    >
      <div className="flex flex-col h-[600px]">
        {/* Controls */}
        <div className="border-b p-4 bg-gray-50">
          <div className="flex justify-between items-center mb-3">
            <Space>
              <Button
                type={streaming ? 'default' : 'primary'}
                icon={streaming ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
                onClick={streaming ? stopStreaming : startStreaming}
                loading={loading}
              >
                {streaming ? 'Stop Stream' : 'Start Stream'}
              </Button>
              <Button icon={<ReloadOutlined />} onClick={loadRecentLogs} loading={loading}>
                Refresh
              </Button>
              <Button icon={<BugOutlined />} onClick={generateTestLogs}>
                Test Logs
              </Button>
            </Space>
            
            <Space>
              <Button icon={<ClearOutlined />} onClick={clearLogs}>
                Clear
              </Button>
              <Button icon={<DownloadOutlined />} onClick={downloadLogs}>
                Download
              </Button>
            </Space>
          </div>
          
          <div className="flex justify-between items-center">
            <Space>
              <span>Level:</span>
              <Select
                value={levelFilter}
                onChange={setLevelFilter}
                style={{ width: 100 }}
                size="small"
              >
                <Select.Option value="all">All</Select.Option>
                <Select.Option value="debug">Debug</Select.Option>
                <Select.Option value="info">Info</Select.Option>
                <Select.Option value="warning">Warning</Select.Option>
                <Select.Option value="error">Error</Select.Option>
              </Select>
              
              <Search
                placeholder="Search logs..."
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                style={{ width: 200 }}
                size="small"
                allowClear
              />
            </Space>
            
            <Space>
              <span>Auto-scroll:</span>
              <Switch checked={autoScroll} onChange={setAutoScroll} size="small" />
              <Text type="secondary">
                {filteredLogs.length} / {logs.length} entries
              </Text>
            </Space>
          </div>
        </div>

        {/* Error Alert */}
        {error && (
          <Alert
            message={error}
            type="error"
            closable
            onClose={() => setError(null)}
            className="my-4"
          />
        )}

        {/* Logs Content */}
        <div className="flex-1 overflow-hidden">
          {loading ? (
            <div className="flex justify-center items-center h-full">
              <Spin size="large" />
            </div>
          ) : (
            <div
              ref={logsContainerRef}
              className="h-full overflow-y-auto bg-black text-white font-mono text-sm"
              style={{ padding: '12px' }}
            >
              {filteredLogs.length === 0 ? (
                <div className="text-gray-400 text-center mt-8">
                  No log entries {logs.length > 0 ? 'match your filters' : 'available'}
                </div>
              ) : (
                filteredLogs.map((log, index) => (
                  <div key={`${log.timestamp}-${index}-${log.message.slice(0, 50)}`} className="mb-1 leading-relaxed hover:bg-gray-800 px-2 py-1 rounded">
                    <span className="text-gray-400 mr-2">
                      {formatTimestamp(log.timestamp)}
                    </span>
                    <span
                      className="mr-2 font-semibold"
                      style={{ color: getLevelColor(log.level) }}
                    >
                      [{log.level}]
                    </span>
                    <span className="text-blue-300 mr-2">
                      {log.logger}
                      {log.funcName && `:${log.funcName}`}
                      {log.lineno && `:${log.lineno}`}:
                    </span>
                    <span>{log.message}</span>
                    {log.exception && (
                      <pre className="text-red-400 mt-1 ml-4 text-xs whitespace-pre-wrap">
                        {log.exception}
                      </pre>
                    )}
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>
    </Modal>
  );
};

export default WorkerLogViewer;
