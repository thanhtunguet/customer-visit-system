import React, { useState, useEffect, useCallback } from 'react';
import { Button, Space, Tag, Tooltip, Dropdown, MenuProps } from 'antd';
import { 
  FullscreenOutlined,
  FullscreenExitOutlined,
  StopOutlined,
  VideoCameraOutlined,
  AppstoreOutlined,
  BorderOutlined,
  BlockOutlined,
  BorderlessTableOutlined,
  EyeOutlined
} from '@ant-design/icons';
import { WebRTCCameraStream } from './WebRTCCameraStream';
import { Camera } from '../types/api';

interface MultiCameraStreamViewProps {
  siteId: number | string | null;
  cameras: Camera[];
  streamStatuses: Record<string, boolean>;
  onStreamStateChange: (cameraId: string, isActive: boolean) => void;
  onStopStream: (camera: Camera) => void;
}

type GridLayout = '2x2' | '3x3' | '4x4' | 'auto';

const GRID_LAYOUTS = {
  '2x2': { cols: 2, rows: 2, maxCameras: 4, gridCols: 'grid-cols-2' },
  '3x3': { cols: 3, rows: 3, maxCameras: 9, gridCols: 'grid-cols-3' },
  '4x4': { cols: 4, rows: 4, maxCameras: 16, gridCols: 'grid-cols-4' },
  'auto': { cols: 0, rows: 0, maxCameras: Infinity, gridCols: 'auto' }
};

export const MultiCameraStreamView: React.FC<MultiCameraStreamViewProps> = ({
  siteId,
  cameras,
  streamStatuses,
  onStreamStateChange,
  onStopStream
}) => {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [gridLayout, setGridLayout] = useState<GridLayout>('auto');

  // Get active cameras
  const activeCameras = cameras.filter(camera => streamStatuses[camera.camera_id]);

  // Calculate optimal grid layout for auto mode
  const getAutoGridLayout = useCallback((count: number) => {
    if (count <= 1) return 'grid-cols-1';
    if (count <= 4) return 'grid-cols-2';
    if (count <= 9) return 'grid-cols-3';
    return 'grid-cols-4';
  }, []);

  // Get grid CSS class
  const getGridClass = useCallback(() => {
    if (gridLayout === 'auto') {
      return getAutoGridLayout(activeCameras.length);
    }
    return GRID_LAYOUTS[gridLayout].gridCols;
  }, [gridLayout, activeCameras.length, getAutoGridLayout]);

  // Get cameras to display based on layout
  const getCamerasToDisplay = useCallback(() => {
    if (gridLayout === 'auto') {
      return activeCameras;
    }
    const maxCameras = GRID_LAYOUTS[gridLayout].maxCameras;
    return activeCameras.slice(0, maxCameras);
  }, [activeCameras, gridLayout]);

  // Handle fullscreen toggle
  const handleFullscreenToggle = useCallback(async () => {
    const element = document.getElementById('multi-camera-container');
    if (!element) return;

    try {
      if (!isFullscreen && document.fullscreenElement === null) {
        await element.requestFullscreen();
        setIsFullscreen(true);
      } else if (document.fullscreenElement) {
        await document.exitFullscreen();
        setIsFullscreen(false);
      }
    } catch (err) {
      console.error('Fullscreen toggle failed:', err);
    }
  }, [isFullscreen]);

  // Listen for fullscreen changes (handles ESC key and other exits)
  useEffect(() => {
    const handleFullscreenChange = () => {
      const isCurrentlyFullscreen = document.fullscreenElement !== null;
      setIsFullscreen(isCurrentlyFullscreen);
      // no-op
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    document.addEventListener('webkitfullscreenchange', handleFullscreenChange);
    document.addEventListener('mozfullscreenchange', handleFullscreenChange);
    document.addEventListener('MSFullscreenChange', handleFullscreenChange);
    
    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
      document.removeEventListener('webkitfullscreenchange', handleFullscreenChange);
      document.removeEventListener('mozfullscreenchange', handleFullscreenChange);
      document.removeEventListener('MSFullscreenChange', handleFullscreenChange);
    };
  }, []);

  // Cleanup when component unmounts
  useEffect(() => {
    return () => {
      // Exit fullscreen if active when component unmounts
      if (document.fullscreenElement) {
        document.exitFullscreen().catch(console.error);
      }
    };
  }, []);

  // Layout menu items
  const layoutMenuItems: MenuProps['items'] = [
    {
      key: 'auto',
      icon: <AppstoreOutlined />,
      label: 'Auto Layout',
      onClick: () => setGridLayout('auto')
    },
    {
      key: '2x2',
      icon: <BorderOutlined />,
      label: '2×2 Grid (4 cameras)',
      disabled: activeCameras.length === 0,
      onClick: () => setGridLayout('2x2')
    },
    {
      key: '3x3',
      icon: <BlockOutlined />,
      label: '3×3 Grid (9 cameras)',
      disabled: activeCameras.length === 0,
      onClick: () => setGridLayout('3x3')
    },
    {
      key: '4x4',
      icon: <BorderlessTableOutlined />,
      label: '4×4 Grid (16 cameras)',
      disabled: activeCameras.length === 0,
      onClick: () => setGridLayout('4x4')
    }
  ];

  const camerasToDisplay = getCamerasToDisplay();

  return (
    <div 
      id="multi-camera-container" 
      className={`space-y-4 ${isFullscreen ? 'bg-black p-4' : ''}`}
      style={{ height: isFullscreen ? '100vh' : 'auto' }}
    >
      {/* Toolbar */}
      <div className={`flex items-center justify-between ${isFullscreen ? 'text-white' : ''}`}>
        <div className="flex items-center space-x-3">
          <Space>
            <EyeOutlined style={{ color: isFullscreen ? '#fff' : '#1890ff' }} />
            <span className="font-medium">
              All Active Camera Streams ({activeCameras.length})
            </span>
          </Space>
          
          {gridLayout !== 'auto' && camerasToDisplay.length < activeCameras.length && (
            <Tag color="orange">
              Showing {camerasToDisplay.length} of {activeCameras.length} cameras
            </Tag>
          )}
        </div>

        <Space>
          <Dropdown menu={{ items: layoutMenuItems }} trigger={['click']}>
            <Button 
              icon={<AppstoreOutlined />}
              type={isFullscreen ? 'default' : 'text'}
            >
              {gridLayout === 'auto' ? 'Auto Layout' : `${gridLayout.toUpperCase()} Grid`}
            </Button>
          </Dropdown>

          <Tooltip title={isFullscreen ? 'Exit Fullscreen' : 'Enter Fullscreen'}>
            <Button
              icon={isFullscreen ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
              onClick={handleFullscreenToggle}
              type={isFullscreen ? 'default' : 'text'}
            />
          </Tooltip>
        </Space>
      </div>

      {/* Camera Grid */}
      <div 
        className={`grid gap-4 ${getGridClass()}`}
        style={{ 
          height: isFullscreen ? 'calc(100vh - 80px)' : '80vh',
          maxHeight: isFullscreen ? 'calc(100vh - 80px)' : '80vh',
          overflowY: 'auto'
        }}
      >
        {camerasToDisplay.map((camera) => (
          <div 
            key={camera.camera_id} 
            className={`${isFullscreen ? 'bg-gray-900' : 'border border-gray-200 bg-white'} rounded-lg p-4`}
            style={{ 
              minHeight: isFullscreen ? '200px' : '300px',
              height: 'fit-content'
            }}
          >
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center space-x-2">
                <VideoCameraOutlined className={isFullscreen ? 'text-blue-400' : 'text-blue-600'} />
                <span className={`font-medium ${isFullscreen ? 'text-white' : ''}`}>
                  {camera.name}
                </span>
                <span className={`text-sm ${isFullscreen ? 'text-gray-400' : 'text-gray-500'}`}>
                  #{camera.camera_id}
                </span>
                <Tag color={camera.camera_type === 'rtsp' ? 'blue' : 'green'}>
                  {camera.camera_type === 'rtsp' ? 'RTSP' : 'Webcam'}
                </Tag>
              </div>
              <Button
                size="small"
                icon={<StopOutlined />}
                onClick={() => onStopStream(camera)}
                danger
                type={isFullscreen ? 'default' : 'text'}
              >
                Stop
              </Button>
            </div>
            
            <div style={{ height: isFullscreen ? 'calc((100vh - 180px) / 2)' : '250px' }}>
              <WebRTCCameraStream
                siteId={siteId}
                cameraId={camera.camera_id}
                cameraName={camera.name}
                onStreamStateChange={onStreamStateChange}
                onConnectionStateChange={() => {}} // Individual connection states not needed here
                autoReconnect={true}
                currentStreamStatus={streamStatuses[camera.camera_id] || false}
              />
            </div>
          </div>
        ))}

        {camerasToDisplay.length === 0 && (
          <div className={`col-span-full text-center py-8 ${isFullscreen ? 'text-gray-400' : 'text-gray-500'}`}>
            <VideoCameraOutlined className="text-4xl mb-4" />
            <div className="text-lg">No Active Streams</div>
            <div className="text-sm">Start camera streams from the main table to view them here</div>
          </div>
        )}
      </div>

      {/* Layout Info */}
      {isFullscreen && gridLayout !== 'auto' && (
        <div className="text-center text-gray-400 text-sm">
          <div>Press ESC to exit fullscreen • Layout: {gridLayout.toUpperCase()}</div>
          {camerasToDisplay.length < activeCameras.length && (
            <div className="mt-1">
              Displaying {camerasToDisplay.length} of {activeCameras.length} active cameras
            </div>
          )}
        </div>
      )}
    </div>
  );
};
