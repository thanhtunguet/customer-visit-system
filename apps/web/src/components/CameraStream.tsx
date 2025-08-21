import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { Button, Space, Alert, Tag, Spin, Tooltip, message, Popconfirm } from 'antd';
import { 
  PlayCircleOutlined, 
  StopOutlined,
  ReloadOutlined,
  VideoCameraOutlined,
  InfoCircleOutlined
} from '@ant-design/icons';
import { apiClient } from '../services/api';

interface CameraStreamProps {
  siteId: string;
  cameraId: number;
  cameraName: string;
  onClose?: () => void;
  autoStart?: boolean;
  autoReconnect?: boolean;
  currentStreamStatus?: boolean;
  onStreamStateChange?: (cameraId: string, isActive: boolean) => void;
  onConnectionStateChange?: (state: 'disconnected' | 'connecting' | 'connected' | 'error') => void;
}

interface StreamStatus {
  camera_id: number;
  stream_active: boolean;
  stream_info: {
    camera_id: number;
    is_active: boolean;
    camera_type: string;
    last_frame_time: number;
    error_count: number;
    queue_size: number;
  } | null;
}

export const CameraStream: React.FC<CameraStreamProps> = ({
  siteId,
  cameraId,
  cameraName,
  onClose,
  autoStart = false,
  autoReconnect = false,
  currentStreamStatus = false,
  onStreamStateChange,
  onConnectionStateChange
}) => {
  const [isStreaming, setIsStreaming] = useState(currentStreamStatus);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [streamStatus, setStreamStatus] = useState<StreamStatus | null>(null);
  const [connectionState, setConnectionState] = useState<'disconnected' | 'connecting' | 'connected' | 'error'>('disconnected');
  const [manuallyStopped, setManuallyStopped] = useState(false);
  
  const imgRef = useRef<HTMLImageElement>(null);
  const statusIntervalRef = useRef<NodeJS.Timeout | null>(null);
  
  // Get stream URL (updates when siteId or cameraId changes)
  const streamUrl = useMemo(() => 
    apiClient.getCameraStreamUrl(siteId, cameraId), 
    [siteId, cameraId]
  );

  // Notify parent component of stream state changes
  const notifyStreamStateChange = useCallback((isActive: boolean) => {
    if (onStreamStateChange) {
      onStreamStateChange(cameraId.toString(), isActive);
    }
  }, [onStreamStateChange, cameraId]);

  // Notify parent component of connection state changes
  const notifyConnectionStateChange = useCallback((state: 'disconnected' | 'connecting' | 'connected' | 'error') => {
    if (onConnectionStateChange) {
      onConnectionStateChange(state);
    }
  }, [onConnectionStateChange]);

  // Check stream status
  const checkStreamStatus = useCallback(async () => {
    try {
      const status = await apiClient.getCameraStreamStatus(siteId, cameraId);
      setStreamStatus(status);
      return status;
    } catch (err: any) {
      console.error('Failed to check stream status:', err);
      return null;
    }
  }, [siteId, cameraId]);

  // Start streaming
  const handleStartStream = async () => {
    try {
      setLoading(true);
      setError(null);
      setConnectionState('connecting');
      notifyConnectionStateChange('connecting');
      
      await apiClient.startCameraStream(siteId, cameraId);
      setIsStreaming(true);
      notifyStreamStateChange(true);
      setManuallyStopped(false); // Reset manually stopped flag when starting
      
      // Wait a moment for the stream to start
      setTimeout(() => {
        if (imgRef.current) {
          imgRef.current.src = `${streamUrl}&t=${Date.now()}`;
        }
      }, 1000);
      
      message.success('Camera stream started');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to start stream');
      setConnectionState('error');
      notifyConnectionStateChange('error');
      message.error('Failed to start camera stream');
    } finally {
      setLoading(false);
    }
  };

  // Stop streaming
  const handleStopStream = async () => {
    try {
      setLoading(true);
      await apiClient.stopCameraStream(siteId, cameraId);
      setIsStreaming(false);
      notifyStreamStateChange(false);
      setConnectionState('disconnected');
      notifyConnectionStateChange('disconnected');
      setManuallyStopped(true); // Mark as manually stopped
      
      // Clear image source
      if (imgRef.current) {
        imgRef.current.src = '';
      }
      
      message.success('Camera stream stopped');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to stop stream');
      message.error('Failed to stop camera stream');
    } finally {
      setLoading(false);
    }
  };

  // Reconnect to stream
  const handleReconnect = async () => {
    try {
      setLoading(true);
      setError(null);
      setConnectionState('connecting');
      
      // Check if stream is still active on backend
      const status = await checkStreamStatus();
      
      if (status?.stream_active) {
        // Stream is active, just reconnect the display
        if (imgRef.current) {
          imgRef.current.src = `${streamUrl}&t=${Date.now()}`;
        }
        setIsStreaming(true);
        notifyStreamStateChange(true);
        message.success('Reconnected to stream');
      } else {
        // Stream is not active, need to start it
        await handleStartStream();
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to reconnect');
      setConnectionState('error');
      message.error('Failed to reconnect to stream');
    } finally {
      setLoading(false);
    }
  };

  // Close stream (frontend only)
  const handleClose = () => {
    setConnectionState('disconnected');
    if (imgRef.current) {
      imgRef.current.src = '';
    }
    if (onClose) {
      onClose();
    }
  };

  // Handle image load events
  const handleImageLoad = () => {
    setConnectionState('connected');
    notifyConnectionStateChange('connected');
    setError(null);
  };

  const handleImageError = () => {
    if (isStreaming) {
      setConnectionState('error');
      notifyConnectionStateChange('error');
      setError('Stream connection lost');
    }
  };



  // Sync internal state with external currentStreamStatus
  useEffect(() => {
    setIsStreaming(currentStreamStatus);
  }, [currentStreamStatus]);

  // Auto-start/reconnect stream on component mount
  useEffect(() => {
    const initializeStream = async () => {
      if ((autoStart || autoReconnect) && !manuallyStopped) {
        const status = await checkStreamStatus();
        if (status?.stream_active) {
          // Stream already active, just connect to existing stream
          setIsStreaming(true);
          notifyStreamStateChange(true);
          if (imgRef.current) {
            imgRef.current.src = `${streamUrl}&t=${Date.now()}`;
          }
        } else if (autoStart) {
          // Start new stream only if autoStart is enabled (not for reconnect)
          handleStartStream();
        }
      }
    };

    initializeStream();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Only run on mount - component remounts when camera changes due to key prop

  // Periodic status check
  useEffect(() => {
    if (isStreaming) {
      statusIntervalRef.current = setInterval(() => {
        checkStreamStatus();
      }, 5000); // Check every 5 seconds
    } else if (statusIntervalRef.current) {
      clearInterval(statusIntervalRef.current);
      statusIntervalRef.current = null;
    }

    return () => {
      if (statusIntervalRef.current) {
        clearInterval(statusIntervalRef.current);
      }
    };
  }, [isStreaming, checkStreamStatus]);

  const getConnectionStatus = () => {
    switch (connectionState) {
      case 'connected':
        return 'Connected';
      case 'connecting':
        return 'Connecting...';
      case 'error':
        return 'Error';
      default:
        return 'Disconnected';
    }
  };

  const getConnectionStatusColor = () => {
    switch (connectionState) {
      case 'connected':
        return 'green';
      case 'connecting':
        return 'blue';
      case 'error':
        return 'red';
      default:
        return 'default';
    }
  };

  return (
    <div className="space-y-3">
        {error && (
          <Alert
            message="Stream Error"
            description={error}
            type="error"
            closable
            onClose={() => setError(null)}
          />
        )}

        <div className="relative bg-gray-900 rounded-lg overflow-hidden w-full" style={{ aspectRatio: '16/9' }}>
          {isStreaming ? (
            <>
              <img
                ref={imgRef}
                alt="Camera Stream"
                className="w-full h-full object-contain"
                onLoad={handleImageLoad}
                onError={handleImageError}
                style={{ display: connectionState === 'connected' ? 'block' : 'none' }}
              />
              {connectionState !== 'connected' && (
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="text-center text-white">
                    {connectionState === 'connecting' && (
                      <>
                        <Spin size="large" />
                        <div className="mt-4">Connecting to stream...</div>
                      </>
                    )}
                    {connectionState === 'error' && (
                      <>
                        <div className="text-red-400 text-lg mb-2">Connection Lost</div>
                        <Button onClick={handleReconnect} loading={loading}>
                          Reconnect
                        </Button>
                      </>
                    )}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="absolute inset-0 flex items-center justify-center bg-gray-800">
              <div className="text-center text-white">
                <VideoCameraOutlined className="text-4xl mb-4 text-gray-400" />
                <div className="text-lg">Camera Stream Not Active</div>
                <div className="text-sm text-gray-400 mt-2">Click Start to begin streaming</div>
              </div>
            </div>
          )}
        </div>

        <div className="flex justify-center">
          <Space size="small">
            {!isStreaming ? (
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                onClick={handleStartStream}
                loading={loading}
                size="default"
              >
                Start Stream
              </Button>
            ) : (
              <>
                <Popconfirm
                  title="Stop Camera Stream"
                  description="Are you sure you want to stop this camera stream?"
                  onConfirm={handleStopStream}
                  okText="Yes, Stop"
                  cancelText="Cancel"
                  okButtonProps={{ danger: true }}
                >
                  <Button
                    icon={<StopOutlined />}
                    loading={loading}
                    size="default"
                    danger
                  >
                    Stop Stream
                  </Button>
                </Popconfirm>
                <Button
                  icon={<ReloadOutlined />}
                  onClick={handleReconnect}
                  loading={loading}
                  size="default"
                >
                  Reconnect
                </Button>
              </>
            )}

          </Space>
        </div>

        {streamStatus?.stream_info && (
          <div className="text-xs text-gray-500 text-center space-x-3">
            <span>Type: {streamStatus.stream_info.camera_type.toUpperCase()}</span>
            <span>Queue: {streamStatus.stream_info.queue_size}</span>
            <span>Errors: {streamStatus.stream_info.error_count}</span>
            <span>Last Frame: {new Date(streamStatus.stream_info.last_frame_time * 1000).toLocaleTimeString()}</span>
          </div>
        )}
    </div>
  );
};