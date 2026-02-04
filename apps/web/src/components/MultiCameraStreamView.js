import { jsx as _jsx, jsxs as _jsxs } from 'react/jsx-runtime';
import { useState, useEffect, useCallback } from 'react';
import { Button, Space, Tag, Tooltip, Dropdown } from 'antd';
import {
  FullscreenOutlined,
  FullscreenExitOutlined,
  StopOutlined,
  VideoCameraOutlined,
  AppstoreOutlined,
  BorderOutlined,
  BlockOutlined,
  BorderlessTableOutlined,
  EyeOutlined,
} from '@ant-design/icons';
import { WebRTCCameraStream } from './WebRTCCameraStream';
const GRID_LAYOUTS = {
  '2x2': { cols: 2, rows: 2, maxCameras: 4, gridCols: 'grid-cols-2' },
  '3x3': { cols: 3, rows: 3, maxCameras: 9, gridCols: 'grid-cols-3' },
  '4x4': { cols: 4, rows: 4, maxCameras: 16, gridCols: 'grid-cols-4' },
  auto: { cols: 0, rows: 0, maxCameras: Infinity, gridCols: 'auto' },
};
export const MultiCameraStreamView = ({
  siteId,
  cameras,
  streamStatuses,
  onStreamStateChange,
  onStopStream,
}) => {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [gridLayout, setGridLayout] = useState('auto');
  // Get active cameras
  const activeCameras = cameras.filter(
    (camera) => streamStatuses[camera.camera_id]
  );
  // Calculate optimal grid layout for auto mode
  const getAutoGridLayout = useCallback((count) => {
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
      document.removeEventListener(
        'webkitfullscreenchange',
        handleFullscreenChange
      );
      document.removeEventListener(
        'mozfullscreenchange',
        handleFullscreenChange
      );
      document.removeEventListener(
        'MSFullscreenChange',
        handleFullscreenChange
      );
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
  const layoutMenuItems = [
    {
      key: 'auto',
      icon: _jsx(AppstoreOutlined, {}),
      label: 'Auto Layout',
      onClick: () => setGridLayout('auto'),
    },
    {
      key: '2x2',
      icon: _jsx(BorderOutlined, {}),
      label: '2×2 Grid (4 cameras)',
      disabled: activeCameras.length === 0,
      onClick: () => setGridLayout('2x2'),
    },
    {
      key: '3x3',
      icon: _jsx(BlockOutlined, {}),
      label: '3×3 Grid (9 cameras)',
      disabled: activeCameras.length === 0,
      onClick: () => setGridLayout('3x3'),
    },
    {
      key: '4x4',
      icon: _jsx(BorderlessTableOutlined, {}),
      label: '4×4 Grid (16 cameras)',
      disabled: activeCameras.length === 0,
      onClick: () => setGridLayout('4x4'),
    },
  ];
  const camerasToDisplay = getCamerasToDisplay();
  return _jsxs('div', {
    id: 'multi-camera-container',
    className: `space-y-4 ${isFullscreen ? 'bg-black p-4' : ''}`,
    style: { height: isFullscreen ? '100vh' : 'auto' },
    children: [
      _jsxs('div', {
        className: `flex items-center justify-between ${isFullscreen ? 'text-white' : ''}`,
        children: [
          _jsxs('div', {
            className: 'flex items-center space-x-3',
            children: [
              _jsxs(Space, {
                children: [
                  _jsx(EyeOutlined, {
                    style: { color: isFullscreen ? '#fff' : '#1890ff' },
                  }),
                  _jsxs('span', {
                    className: 'font-medium',
                    children: [
                      'All Active Camera Streams (',
                      activeCameras.length,
                      ')',
                    ],
                  }),
                ],
              }),
              gridLayout !== 'auto' &&
                camerasToDisplay.length < activeCameras.length &&
                _jsxs(Tag, {
                  color: 'orange',
                  children: [
                    'Showing ',
                    camerasToDisplay.length,
                    ' of ',
                    activeCameras.length,
                    ' cameras',
                  ],
                }),
            ],
          }),
          _jsxs(Space, {
            children: [
              _jsx(Dropdown, {
                menu: { items: layoutMenuItems },
                trigger: ['click'],
                children: _jsx(Button, {
                  icon: _jsx(AppstoreOutlined, {}),
                  type: isFullscreen ? 'default' : 'text',
                  children:
                    gridLayout === 'auto'
                      ? 'Auto Layout'
                      : `${gridLayout.toUpperCase()} Grid`,
                }),
              }),
              _jsx(Tooltip, {
                title: isFullscreen ? 'Exit Fullscreen' : 'Enter Fullscreen',
                children: _jsx(Button, {
                  icon: isFullscreen
                    ? _jsx(FullscreenExitOutlined, {})
                    : _jsx(FullscreenOutlined, {}),
                  onClick: handleFullscreenToggle,
                  type: isFullscreen ? 'default' : 'text',
                }),
              }),
            ],
          }),
        ],
      }),
      _jsxs('div', {
        className: `grid gap-4 ${getGridClass()}`,
        style: {
          height: isFullscreen ? 'calc(100vh - 80px)' : '80vh',
          maxHeight: isFullscreen ? 'calc(100vh - 80px)' : '80vh',
          overflowY: 'auto',
        },
        children: [
          camerasToDisplay.map((camera) =>
            _jsxs(
              'div',
              {
                className: `${isFullscreen ? 'bg-gray-900' : 'border border-gray-200 bg-white'} rounded-lg p-4`,
                style: {
                  minHeight: isFullscreen ? '200px' : '300px',
                  height: 'fit-content',
                },
                children: [
                  _jsxs('div', {
                    className: 'flex items-center justify-between mb-3',
                    children: [
                      _jsxs('div', {
                        className: 'flex items-center space-x-2',
                        children: [
                          _jsx(VideoCameraOutlined, {
                            className: isFullscreen
                              ? 'text-blue-400'
                              : 'text-blue-600',
                          }),
                          _jsx('span', {
                            className: `font-medium ${isFullscreen ? 'text-white' : ''}`,
                            children: camera.name,
                          }),
                          _jsxs('span', {
                            className: `text-sm ${isFullscreen ? 'text-gray-400' : 'text-gray-500'}`,
                            children: ['#', camera.camera_id],
                          }),
                          _jsx(Tag, {
                            color:
                              camera.camera_type === 'rtsp' ? 'blue' : 'green',
                            children:
                              camera.camera_type === 'rtsp' ? 'RTSP' : 'Webcam',
                          }),
                        ],
                      }),
                      _jsx(Button, {
                        size: 'small',
                        icon: _jsx(StopOutlined, {}),
                        onClick: () => onStopStream(camera),
                        danger: true,
                        type: isFullscreen ? 'default' : 'text',
                        children: 'Stop',
                      }),
                    ],
                  }),
                  _jsx('div', {
                    style: {
                      height: isFullscreen
                        ? 'calc((100vh - 180px) / 2)'
                        : '250px',
                    },
                    children: _jsx(WebRTCCameraStream, {
                      siteId: siteId,
                      cameraId: camera.camera_id,
                      cameraName: camera.name,
                      onStreamStateChange: onStreamStateChange,
                      onConnectionStateChange: () => {},
                      autoReconnect: true,
                      currentStreamStatus:
                        streamStatuses[camera.camera_id] || false,
                    }),
                  }),
                ],
              },
              camera.camera_id
            )
          ),
          camerasToDisplay.length === 0 &&
            _jsxs('div', {
              className: `col-span-full text-center py-8 ${isFullscreen ? 'text-gray-400' : 'text-gray-500'}`,
              children: [
                _jsx(VideoCameraOutlined, { className: 'text-4xl mb-4' }),
                _jsx('div', {
                  className: 'text-lg',
                  children: 'No Active Streams',
                }),
                _jsx('div', {
                  className: 'text-sm',
                  children:
                    'Start camera streams from the main table to view them here',
                }),
              ],
            }),
        ],
      }),
      isFullscreen &&
        gridLayout !== 'auto' &&
        _jsxs('div', {
          className: 'text-center text-gray-400 text-sm',
          children: [
            _jsxs('div', {
              children: [
                'Press ESC to exit fullscreen \u2022 Layout: ',
                gridLayout.toUpperCase(),
              ],
            }),
            camerasToDisplay.length < activeCameras.length &&
              _jsxs('div', {
                className: 'mt-1',
                children: [
                  'Displaying ',
                  camerasToDisplay.length,
                  ' of ',
                  activeCameras.length,
                  ' active cameras',
                ],
              }),
          ],
        }),
    ],
  });
};
