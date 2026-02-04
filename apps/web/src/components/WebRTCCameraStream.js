import {
  jsx as _jsx,
  Fragment as _Fragment,
  jsxs as _jsxs,
} from 'react/jsx-runtime';
import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import {
  Button,
  Space,
  Alert,
  Tag,
  Spin,
  Tooltip,
  Popconfirm,
  App,
} from 'antd';
import {
  PlayCircleOutlined,
  StopOutlined,
  ReloadOutlined,
  WifiOutlined,
} from '@ant-design/icons';
import { apiClient } from '../services/api';
export const WebRTCCameraStream = ({
  siteId,
  cameraId,
  cameraName: _cameraName,
  onClose: _onClose,
  autoStart = false,
  autoReconnect: _autoReconnect = false,
  currentStreamStatus = false,
  onStreamStateChange,
  onConnectionStateChange,
}) => {
  const [isStreaming, setIsStreaming] = useState(currentStreamStatus);
  const { message } = App.useApp();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [connectionState, setConnectionState] = useState('disconnected');
  const [signalingState, setSignalingState] = useState('closed');
  const [manuallyStopped, setManuallyStopped] = useState(false);
  // WebRTC state
  const [session, setSession] = useState(null);
  // Use a ref for worker id to avoid stale closures in ICE handlers
  const workerIdRef = useRef(null);
  const clientId = useRef(`client-${Math.random().toString(36).substr(2, 9)}`);
  // WebRTC refs
  const videoRef = useRef(null);
  const peerConnectionRef = useRef(null);
  const signalingWsRef = useRef(null);
  const streamRef = useRef(null);
  const sessionRef = useRef(null);
  // Connection retry logic
  const retryCountRef = useRef(0);
  const maxRetries = 3;
  const retryTimeoutRef = useRef(null);
  // Refs for callback functions to avoid circular dependencies
  const handleReconnectRef = useRef();
  const handleSignalingMessageRef = useRef();
  // Generate unique client ID
  const currentClientId = useMemo(() => clientId.current, []);
  // Notify parent component of stream state changes
  const notifyStreamStateChange = useCallback(
    (isActive) => {
      if (onStreamStateChange) {
        onStreamStateChange(cameraId.toString(), isActive);
      }
    },
    [onStreamStateChange, cameraId]
  );
  // Notify parent component of connection state changes
  const notifyConnectionStateChange = useCallback(
    (state) => {
      if (onConnectionStateChange) {
        onConnectionStateChange(state);
      }
    },
    [onConnectionStateChange]
  );
  // Update connection state with notifications
  const updateConnectionState = useCallback(
    (state) => {
      setConnectionState(state);
      notifyConnectionStateChange(state);
    },
    [notifyConnectionStateChange]
  );
  // Setup WebRTC peer connection
  const setupPeerConnection = useCallback(() => {
    const pc = new RTCPeerConnection({
      iceServers: [
        { urls: 'stun:stun.l.google.com:19302' },
        { urls: 'stun:stun1.l.google.com:19302' },
      ],
    });
    // Ensure we are ready to receive a remote video track on all browsers
    try {
      pc.addTransceiver('video', { direction: 'recvonly' });
    } catch (_) {
      // Some implementations may not require/allow this; ignore
    }
    // Handle incoming media stream
    pc.ontrack = (event) => {
      console.log('Received remote track:', event);
      if (event.streams && event.streams[0]) {
        const stream = event.streams[0];
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          console.log('Video element source set to remote stream');
          try {
            videoRef.current.play();
          } catch (_) {
            // Ignore autoplay errors - browser may prevent it
          }
        }
      }
    };
    // Handle ICE candidates
    pc.onicecandidate = (event) => {
      if (
        event.candidate &&
        signalingWsRef.current?.readyState === WebSocket.OPEN
      ) {
        console.log('Sending ICE candidate to signaling server');
        const message = {
          type: 'signaling',
          data: {
            type: 'ice-candidate',
            session_id: sessionRef.current?.session_id,
            from_id: currentClientId,
            to_id: workerIdRef.current || `worker-${session?.camera_id}`,
            ice_candidate: {
              candidate: event.candidate.candidate,
              sdpMid: event.candidate.sdpMid,
              sdpMLineIndex: event.candidate.sdpMLineIndex,
            },
          },
        };
        console.log('🔄 Sending ICE candidate message:', message);
        signalingWsRef.current.send(JSON.stringify(message));
      }
    };
    // Handle connection state changes
    pc.onconnectionstatechange = () => {
      console.log('WebRTC connection state:', pc.connectionState);
      switch (pc.connectionState) {
        case 'connected':
          updateConnectionState('connected');
          setError(null);
          retryCountRef.current = 0;
          break;
        case 'connecting':
          updateConnectionState('connecting');
          break;
        case 'disconnected':
          updateConnectionState('disconnected');
          break;
        case 'failed':
          updateConnectionState('error');
          setError('WebRTC connection failed');
          handleReconnectRef.current?.();
          break;
        case 'closed':
          updateConnectionState('disconnected');
          break;
      }
    };
    // Handle ICE connection state
    pc.oniceconnectionstatechange = () => {
      console.log('ICE connection state:', pc.iceConnectionState);
    };
    return pc;
  }, [currentClientId, updateConnectionState, workerIdRef, session]);
  // Setup signaling WebSocket connection
  const setupSignalingConnection = useCallback(async () => {
    try {
      const token = localStorage.getItem('access_token');
      // Get base URL without /v1 for WebSocket connection
      const baseUrl = apiClient.baseURL.replace('/v1', '');
      const wsUrl = new URL(`${baseUrl}/v1/webrtc/client/${currentClientId}`);
      wsUrl.protocol = wsUrl.protocol === 'https:' ? 'wss:' : 'ws:';
      if (token) {
        wsUrl.searchParams.set('token', token);
      }
      console.log('🌐 WebSocket URL components:', {
        apiClientBaseURL: apiClient.baseURL,
        wsBaseURL: baseUrl,
        protocol: wsUrl.protocol,
        host: wsUrl.host,
        pathname: wsUrl.pathname,
        fullURL: wsUrl.toString(),
      });
      setSignalingState('connecting');
      const ws = new WebSocket(wsUrl.toString());
      const openPromise = new Promise((resolve, reject) => {
        ws.onopen = () => {
          console.log('Connected to WebRTC signaling server');
          setSignalingState('open');
          signalingWsRef.current = ws;
          resolve(ws);
        };
        ws.onerror = (error) => {
          console.error('❌ WebSocket error:', error);
          setSignalingState('error');
          setError('Failed to connect to signaling server');
          reject(new Error('WebSocket connection error'));
        };
      });
      ws.onmessage = async (event) => {
        try {
          const message = JSON.parse(event.data);
          console.log('Received signaling message:', message);
          await handleSignalingMessageRef.current?.(message);
        } catch (err) {
          console.error('Error processing signaling message:', err);
        }
      };
      ws.onclose = (event) => {
        console.log('🔌 WebSocket closed:', {
          code: event.code,
          reason: event.reason,
          wasClean: event.wasClean,
          url: ws.url,
        });
        setSignalingState('closed');
        signalingWsRef.current = null;
        // Auto-reconnect if not manually stopped
        if (!manuallyStopped && isStreaming) {
          setTimeout(setupSignalingConnection, 2000);
        }
      };
      // Wait for open or error
      await openPromise;
      return ws;
    } catch (err) {
      console.error('Failed to setup signaling connection:', err);
      setSignalingState('error');
      setError('Failed to setup signaling connection');
      return null;
    }
  }, [currentClientId, isStreaming, manuallyStopped]);
  // Stop WebRTC streaming session
  const handleStopStream = useCallback(async () => {
    try {
      setLoading(true);
      setManuallyStopped(true);
      // Close peer connection
      if (peerConnectionRef.current) {
        peerConnectionRef.current.close();
        peerConnectionRef.current = null;
      }
      // Close signaling WebSocket
      if (signalingWsRef.current) {
        signalingWsRef.current.close();
        signalingWsRef.current = null;
      }
      // Clear video source
      if (videoRef.current) {
        videoRef.current.srcObject = null;
      }
      // Clear stream
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
      }
      // Stop session on server
      if (sessionRef.current) {
        try {
          await apiClient.stopWebRTCSession(sessionRef.current.session_id);
        } catch (err) {
          console.warn('Failed to stop session on server:', err);
        }
      }
      setSession(null);
      sessionRef.current = null;
      setIsStreaming(false);
      updateConnectionState('disconnected');
      setSignalingState('closed');
      notifyStreamStateChange(false);
      // Attempt to stop camera stream on backend to release camera
      try {
        await apiClient.stopCameraStream(siteId, cameraId);
      } catch (e) {
        console.warn('Failed to stop camera stream via API');
      }
      message.success('WebRTC stream stopped');
    } catch (err) {
      const error = err;
      setError(error.message || 'Failed to stop stream');
      message.error('Failed to stop stream');
    } finally {
      setLoading(false);
    }
  }, [
    updateConnectionState,
    notifyStreamStateChange,
    siteId,
    cameraId,
    message,
  ]);
  // Handle signaling messages
  const handleSignalingMessage = useCallback(
    async (message) => {
      if (!peerConnectionRef.current) {
        console.warn('Received signaling message but no peer connection');
        return;
      }
      const pc = peerConnectionRef.current;
      switch (message.type) {
        case 'connected':
          console.log('Signaling server confirmed connection');
          break;
        case 'offer':
          console.log('Received direct WebRTC offer from worker');
          // Capture worker ID from the message
          if (message.from_id) {
            workerIdRef.current = message.from_id;
          }
          try {
            await pc.setRemoteDescription(
              new RTCSessionDescription({
                type: 'offer',
                sdp: message.sdp,
              })
            );
            // Create answer
            const answer = await pc.createAnswer();
            await pc.setLocalDescription(answer);
            // Send answer back via signaling
            if (signalingWsRef.current?.readyState === WebSocket.OPEN) {
              console.log('🔍 Session state when sending answer:', {
                session: session,
                sessionId: session?.session_id,
                cameraId: session?.camera_id,
              });
              const answerMessage = {
                type: 'signaling',
                data: {
                  type: 'answer',
                  session_id: sessionRef.current?.session_id,
                  from_id: currentClientId,
                  to_id:
                    message.from_id ||
                    workerIdRef.current ||
                    `worker-${session?.camera_id}`,
                  sdp: answer.sdp,
                },
              };
              console.log('🔄 Sending answer message:', answerMessage);
              signalingWsRef.current.send(JSON.stringify(answerMessage));
              console.log('Sent WebRTC answer to worker');
            }
          } catch (err) {
            console.error('Error handling direct WebRTC offer:', err);
            setError('Failed to process WebRTC offer');
          }
          break;
        case 'ice-candidate':
          console.log('Received direct ICE candidate from worker');
          try {
            const candidate = new RTCIceCandidate({
              candidate: message.candidate,
              sdpMid: message.sdpMid,
              sdpMLineIndex: message.sdpMLineIndex,
            });
            await pc.addIceCandidate(candidate);
          } catch (err) {
            console.error('Error adding direct ICE candidate:', err);
          }
          break;
        case 'stream-stop':
          console.log('Worker stopped the stream');
          await handleStopStream();
          break;
        case 'signaling': {
          const signalingData = message.data;
          switch (signalingData.type) {
            case 'offer':
              console.log('Received WebRTC offer from worker');
              try {
                await pc.setRemoteDescription(
                  new RTCSessionDescription({
                    type: 'offer',
                    sdp: signalingData.sdp,
                  })
                );
                // Create answer
                const answer = await pc.createAnswer();
                await pc.setLocalDescription(answer);
                // Send answer back via signaling
                if (signalingWsRef.current?.readyState === WebSocket.OPEN) {
                  const answerMessage = {
                    type: 'signaling',
                    data: {
                      type: 'answer',
                      session_id: sessionRef.current?.session_id,
                      from_id: currentClientId,
                      to_id:
                        signalingData.from_id ||
                        workerIdRef.current ||
                        `worker-${session?.camera_id}`,
                      sdp: answer.sdp,
                    },
                  };
                  signalingWsRef.current.send(JSON.stringify(answerMessage));
                  console.log('Sent WebRTC answer to worker');
                }
              } catch (err) {
                console.error('Error handling WebRTC offer:', err);
                setError('Failed to process WebRTC offer');
              }
              break;
            case 'ice-candidate':
              console.log('Received ICE candidate from worker');
              try {
                const candidate = new RTCIceCandidate({
                  candidate: signalingData.ice_candidate.candidate,
                  sdpMid: signalingData.ice_candidate.sdpMid,
                  sdpMLineIndex: signalingData.ice_candidate.sdpMLineIndex,
                });
                await pc.addIceCandidate(candidate);
              } catch (err) {
                console.error('Error adding ICE candidate:', err);
              }
              break;
            case 'stream-stop':
              console.log('Worker stopped the stream');
              await handleStopStream();
              break;
          }
          break;
        }
        default:
          console.log('Unknown signaling message type:', message.type);
      }
    },
    [currentClientId, workerIdRef, handleStopStream, session]
  );
  // Assign handleSignalingMessage to ref
  useEffect(() => {
    handleSignalingMessageRef.current = handleSignalingMessage;
  }, [handleSignalingMessage]);
  // Start WebRTC streaming session
  const handleStartStream = useCallback(async () => {
    try {
      // Ensure worker has camera stream started (assign and start capture)
      try {
        await apiClient.startCameraStream(Number(siteId), cameraId);
      } catch (e) {
        console.warn(
          'Failed to ensure camera stream started via API, proceeding with WebRTC'
        );
      }
      // Prepare peer connection and signaling before asking server to start
      peerConnectionRef.current = setupPeerConnection();
      const ws = await setupSignalingConnection();
      if (!ws) {
        throw new Error('Signaling not available');
      }
      // First, request WebRTC session from API (after WS is ready)
      console.log('🚀 Starting WebRTC session:', {
        client_id: currentClientId,
        camera_id: cameraId,
        site_id: siteId,
        site_id_parsed: Number(siteId),
      });
      const response = await apiClient.startWebRTCSession({
        session_id: `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        client_id: currentClientId,
        camera_id: cameraId,
        site_id: Number(siteId),
      });
      console.log('✅ WebRTC session response:', response);
      if (response.session_id) {
        const newSession = {
          session_id: response.session_id,
          client_id: currentClientId,
          camera_id: cameraId,
          site_id: Number(siteId),
        };
        setSession(newSession);
        sessionRef.current = newSession; // Store in ref for immediate access
        setIsStreaming(true);
        setManuallyStopped(false);
        notifyStreamStateChange(true);
        console.log('WebRTC session created:', newSession);
        // Signaling already ready; worker should send offer shortly
        message.success('WebRTC stream session started');
      } else {
        throw new Error('Failed to create WebRTC session');
      }
    } catch (err) {
      const error = err;
      console.error('❌ WebRTC session failed:', err);
      console.error('❌ Error details:', {
        message: error.message,
        response: error.response?.data,
        status: error.response?.status,
      });
      setError(
        error.response?.data?.detail ||
          error.message ||
          'Failed to start WebRTC stream'
      );
      updateConnectionState('error');
      message.error('Failed to start WebRTC stream');
    } finally {
      setLoading(false);
    }
  }, [
    cameraId,
    siteId,
    currentClientId,
    notifyStreamStateChange,
    updateConnectionState,
    setupPeerConnection,
    setupSignalingConnection,
    message,
  ]);
  // Handle reconnection logic
  const handleReconnect = useCallback(async () => {
    if (manuallyStopped || retryCountRef.current >= maxRetries) {
      return;
    }
    retryCountRef.current++;
    const delay = Math.min(
      1000 * Math.pow(2, retryCountRef.current - 1),
      10000
    );
    console.log(
      `Attempting reconnection ${retryCountRef.current}/${maxRetries} in ${delay}ms`
    );
    retryTimeoutRef.current = setTimeout(async () => {
      try {
        if (!sessionRef.current) {
          // Full restart if no active session
          await handleStartStream();
          return;
        }
        // Re-setup peer connection and signaling
        peerConnectionRef.current = setupPeerConnection();
        await setupSignalingConnection();
      } catch (err) {
        console.error('Reconnection failed:', err);
        if (retryCountRef.current >= maxRetries) {
          setError('Failed to reconnect after maximum attempts');
          updateConnectionState('error');
        } else {
          handleReconnectRef.current?.();
        }
      }
    }, delay);
  }, [
    manuallyStopped,
    setupPeerConnection,
    setupSignalingConnection,
    updateConnectionState,
    handleStartStream,
  ]);
  // Assign callbacks to refs to avoid circular dependencies
  useEffect(() => {
    handleReconnectRef.current = handleReconnect;
  }, [handleReconnect]);
  // Manual reconnect button
  const handleManualReconnect = useCallback(async () => {
    retryCountRef.current = 0;
    setError(null);
    // If we have an active session try reconnect, else do full start
    if (sessionRef.current) {
      await handleReconnectRef.current?.();
    } else {
      await handleStartStream();
    }
  }, [handleStartStream]);
  // Auto-start effect
  useEffect(() => {
    if (autoStart && !isStreaming && !manuallyStopped) {
      handleStartStream();
    }
  }, [autoStart, isStreaming, manuallyStopped, handleStartStream]);
  // Cleanup on unmount
  useEffect(() => {
    return () => {
      // Clear retry timeout
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current);
        retryTimeoutRef.current = null;
      }
      // Force cleanup
      if (peerConnectionRef.current) {
        peerConnectionRef.current.close();
      }
      if (signalingWsRef.current) {
        signalingWsRef.current.close();
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);
  const getConnectionStatus = () => {
    if (signalingState === 'connecting') return 'Connecting to signaling...';
    if (signalingState === 'closed') return 'Signaling disconnected';
    if (signalingState === 'error') return 'Signaling error';
    switch (connectionState) {
      case 'connected':
        return 'Connected (P2P)';
      case 'connecting':
        return 'Establishing P2P connection...';
      case 'error':
        return 'Connection error';
      default:
        return 'Disconnected';
    }
  };
  const getConnectionStatusColor = () => {
    if (connectionState === 'connected') return 'green';
    if (connectionState === 'connecting' || signalingState === 'connecting')
      return 'blue';
    if (connectionState === 'error' || signalingState === 'error') return 'red';
    return 'default';
  };
  return _jsxs('div', {
    className: 'space-y-3',
    children: [
      error &&
        _jsx(Alert, {
          message: 'WebRTC Stream Error',
          description: error,
          type: 'error',
          closable: true,
          onClose: () => setError(null),
        }),
      _jsx('div', {
        className: 'relative bg-gray-900 rounded-lg overflow-hidden w-full',
        style: { aspectRatio: '16/9' },
        children: isStreaming
          ? _jsxs(_Fragment, {
              children: [
                _jsx('video', {
                  ref: videoRef,
                  autoPlay: true,
                  playsInline: true,
                  muted: true,
                  className: 'w-full h-full object-contain',
                  // Always render video; overlay shows connection progress
                  onLoadedMetadata: () => {
                    try {
                      videoRef.current?.play();
                    } catch (e) {
                      /* ignore */
                    }
                  },
                }),
                connectionState !== 'connected' &&
                  _jsx('div', {
                    className:
                      'absolute inset-0 flex items-center justify-center',
                    children: _jsxs('div', {
                      className: 'text-center text-white',
                      children: [
                        connectionState === 'connecting' &&
                          _jsxs(_Fragment, {
                            children: [
                              _jsx(Spin, { size: 'large' }),
                              _jsx('div', {
                                className: 'mt-4',
                                children: 'Establishing P2P connection...',
                              }),
                              signalingState !== 'open' &&
                                _jsx('div', {
                                  className: 'text-sm text-gray-400 mt-2',
                                  children: 'Connecting to signaling server...',
                                }),
                            ],
                          }),
                        connectionState === 'error' &&
                          _jsxs(_Fragment, {
                            children: [
                              _jsx('div', {
                                className: 'text-red-400 text-lg mb-2',
                                children: 'P2P Connection Failed',
                              }),
                              _jsxs(Button, {
                                onClick: handleManualReconnect,
                                loading: loading,
                                children: [
                                  _jsx(ReloadOutlined, {}),
                                  ' Reconnect',
                                ],
                              }),
                              _jsxs('div', {
                                className: 'text-sm text-gray-400 mt-2',
                                children: [
                                  'Retry ',
                                  retryCountRef.current,
                                  '/',
                                  maxRetries,
                                ],
                              }),
                            ],
                          }),
                      ],
                    }),
                  }),
              ],
            })
          : _jsx('div', {
              className:
                'absolute inset-0 flex items-center justify-center bg-gray-800',
              children: _jsxs('div', {
                className: 'text-center text-white',
                children: [
                  _jsx(WifiOutlined, {
                    className: 'text-4xl mb-4 text-gray-400',
                  }),
                  _jsx('div', {
                    className: 'text-lg',
                    children: 'WebRTC P2P Stream',
                  }),
                  _jsx('div', {
                    className: 'text-sm text-gray-400 mt-2',
                    children: 'Direct connection to worker camera',
                  }),
                ],
              }),
            }),
      }),
      _jsxs('div', {
        className: 'flex justify-between items-center',
        children: [
          _jsxs('div', {
            className: 'flex items-center space-x-2',
            children: [
              _jsx(Tag, {
                color: getConnectionStatusColor(),
                children: getConnectionStatus(),
              }),
              session &&
                _jsx(Tooltip, {
                  title: `Session: ${session.session_id.substring(0, 8)}...`,
                  children: _jsx(Tag, { color: 'purple', children: 'WebRTC' }),
                }),
            ],
          }),
          _jsx(Space, {
            size: 'small',
            children: !isStreaming
              ? _jsx(Button, {
                  type: 'primary',
                  icon: _jsx(PlayCircleOutlined, {}),
                  onClick: handleStartStream,
                  loading: loading,
                  size: 'middle',
                  children: 'Start WebRTC Stream',
                })
              : _jsxs(_Fragment, {
                  children: [
                    _jsx(Popconfirm, {
                      title: 'Stop WebRTC Stream',
                      description:
                        'Are you sure you want to stop the peer-to-peer stream?',
                      onConfirm: handleStopStream,
                      okText: 'Yes, Stop',
                      cancelText: 'Cancel',
                      okButtonProps: { danger: true },
                      children: _jsx(Button, {
                        icon: _jsx(StopOutlined, {}),
                        loading: loading,
                        size: 'middle',
                        danger: true,
                        children: 'Stop Stream',
                      }),
                    }),
                    connectionState !== 'connected' &&
                      _jsx(Button, {
                        icon: _jsx(ReloadOutlined, {}),
                        onClick: handleManualReconnect,
                        loading: loading,
                        size: 'middle',
                        children: 'Reconnect',
                      }),
                  ],
                }),
          }),
        ],
      }),
      isStreaming &&
        _jsxs('div', {
          className: 'text-xs text-gray-500 text-center space-x-3',
          children: [
            _jsxs('span', { children: ['Client: ', currentClientId] }),
            _jsxs('span', { children: ['Signaling: ', signalingState] }),
            _jsxs('span', { children: ['P2P: ', connectionState] }),
            retryCountRef.current > 0 &&
              _jsxs('span', {
                children: ['Retries: ', retryCountRef.current, '/', maxRetries],
              }),
          ],
        }),
    ],
  });
};
