import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Card, Button, Space, Alert, Tag, Spin, Tooltip, message } from 'antd';
import { 
  PlayCircleOutlined, 
  PauseCircleOutlined, 
  ReloadOutlined, 
  CloseOutlined,
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
  autoStart = false
}) => {
  const [isStreaming, setIsStreaming] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [streamStatus, setStreamStatus] = useState<StreamStatus | null>(null);
  const [connectionState, setConnectionState] = useState<'disconnected' | 'connecting' | 'connected' | 'error'>('disconnected');
  
  const imgRef = useRef<HTMLImageElement>(null);
  const statusIntervalRef = useRef<NodeJS.Timeout | null>(null);
  
  // Get stream URL
  const streamUrl = apiClient.getCameraStreamUrl(siteId, cameraId);

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
      
      await apiClient.startCameraStream(siteId, cameraId);
      setIsStreaming(true);
      
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
      setConnectionState('disconnected');
      
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
    setError(null);
  };

  const handleImageError = () => {
    if (isStreaming) {
      setConnectionState('error');
      setError('Stream connection lost');
    }
  };

  // Auto-start stream if requested
  useEffect(() => {
    if (autoStart) {
      checkStreamStatus().then((status) => {
        if (status?.stream_active) {
          // Stream already active, just connect
          setIsStreaming(true);
          if (imgRef.current) {
            imgRef.current.src = `${streamUrl}&t=${Date.now()}`;
          }
        } else {
          // Start new stream
          handleStartStream();
        }
      });
    }
  }, [autoStart, streamUrl, checkStreamStatus]);

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

  const getConnectionStatusTag = () => {
    switch (connectionState) {
      case 'connected':
        return <Tag color="green">Connected</Tag>;
      case 'connecting':
        return <Tag color="blue">Connecting...</Tag>;
      case 'error':
        return <Tag color="red">Error</Tag>;
      default:
        return <Tag color="default">Disconnected</Tag>;
    }
  };

  return (
    <Card
      title={
        <Space>
          <VideoCameraOutlined />
          <span>{cameraName}</span>
          <span className="text-gray-500 text-sm">#{cameraId}</span>
          {getConnectionStatusTag()}
        </Space>
      }
      extra={
        <Space>
          {streamStatus?.stream_info && (
            <Tooltip title={`Queue: ${streamStatus.stream_info.queue_size}, Errors: ${streamStatus.stream_info.error_count}`}>
              <Button icon={<InfoCircleOutlined />} size="small" />
            </Tooltip>
          )}
          <Button
            type="text"
            icon={<CloseOutlined />}
            onClick={handleClose}
            size="small"
          />
        </Space>
      }
      className="w-full max-w-2xl"
    >
      <div className="space-y-4">
        {error && (
          <Alert
            message="Stream Error"
            description={error}
            type="error"
            closable
            onClose={() => setError(null)}
          />
        )}

        <div className="relative bg-gray-900 rounded-lg overflow-hidden" style={{ aspectRatio: '16/9' }}>
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
          <Space size="middle">
            {!isStreaming ? (
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                onClick={handleStartStream}
                loading={loading}
                size="large"
              >
                Start Stream
              </Button>
            ) : (
              <>
                <Button
                  icon={<PauseCircleOutlined />}
                  onClick={handleStopStream}
                  loading={loading}
                  size="large"
                >
                  Stop Stream
                </Button>
                <Button
                  icon={<ReloadOutlined />}
                  onClick={handleReconnect}
                  loading={loading}
                  size="large"
                >
                  Reconnect
                </Button>
              </>
            )}
            <Button
              icon={<CloseOutlined />}
              onClick={handleClose}
              size="large"
            >
              Close
            </Button>
          </Space>
        </div>

        {streamStatus?.stream_info && (
          <div className="text-xs text-gray-500 text-center space-x-4">
            <span>Type: {streamStatus.stream_info.camera_type.toUpperCase()}</span>
            <span>Queue: {streamStatus.stream_info.queue_size}</span>
            <span>Errors: {streamStatus.stream_info.error_count}</span>
            <span>Last Frame: {new Date(streamStatus.stream_info.last_frame_time * 1000).toLocaleTimeString()}</span>
          </div>
        )}
      </div>
    </Card>
  );
};