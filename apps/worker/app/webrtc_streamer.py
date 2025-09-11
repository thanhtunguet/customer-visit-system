"""
WebRTC Streamer for Worker

This module implements WebRTC peer connection functionality in workers
to stream camera frames directly to frontend clients via P2P connection,
eliminating the need for HTTP streaming through the API server.

Features:
- WebRTC peer connection with SDP offer generation
- ICE candidate handling for NAT traversal
- Direct camera frame streaming to client
- Signaling through API server WebSocket
- No dynamic port allocation (uses ICE for connectivity)

Dependencies:
- aiortc: Python WebRTC implementation
- opencv-python: Camera frame capture
- websockets: Signaling server communication
"""

import asyncio
import json
import logging
from typing import Any, Callable, Dict, Optional

import cv2
import httpx
import numpy as np
import websockets
from aiortc import (
    RTCIceCandidate,
    RTCPeerConnection,
    RTCSessionDescription,
    VideoStreamTrack,
)
from websockets.exceptions import ConnectionClosed

from .camera_manager import CameraManager

logger = logging.getLogger(__name__)


class CameraVideoTrack(VideoStreamTrack):
    """Custom video track that streams camera frames via WebRTC"""

    def __init__(self, camera_id: int, camera_manager: CameraManager):
        super().__init__()
        self.camera_id = camera_id
        self.camera_manager = camera_manager

    async def recv(self):
        """Get next video frame from camera; wait briefly for real frames."""
        pts, time_base = await self.next_timestamp()

        # Try to obtain a real frame with a brief wait budget
        frame = self.camera_manager.get_latest_frame(self.camera_id)
        attempts = 0
        while frame is None and attempts < 10:
            await asyncio.sleep(0.05)  # 50ms, total up to ~500ms
            frame = self.camera_manager.get_latest_frame(self.camera_id)
            attempts += 1

        if frame is None:
            # Return black frame if camera not available
            logger.debug(
                f"CameraVideoTrack: no frame available for camera {self.camera_id}, sending black frame"
            )
            frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # Convert BGR to RGB (OpenCV uses BGR, WebRTC expects RGB)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Create av.VideoFrame
        from av import VideoFrame

        av_frame = VideoFrame.from_ndarray(frame_rgb, format="rgb24")
        av_frame.pts = pts
        av_frame.time_base = time_base

        return av_frame


class WebRTCStreamer:
    """WebRTC streaming client for worker"""

    def __init__(self, worker_id: str, camera_manager: CameraManager):
        self.worker_id = worker_id
        self.camera_manager = camera_manager

        # WebRTC connections: {session_id: RTCPeerConnection}
        self.peer_connections: Dict[str, RTCPeerConnection] = {}

        # Active streaming sessions: {session_id: camera_id}
        self.streaming_sessions: Dict[str, int] = {}

        # Signaling WebSocket connection
        self.signaling_websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.signaling_url: Optional[str] = None

        # Connection state
        self.is_connected = False
        self.reconnect_delay = 5  # seconds
        self.max_reconnect_attempts = 10

        # Optional provider to fetch camera configuration by id
        self._camera_config_provider: Optional[
            Callable[[int], Optional[Dict[str, Any]]]
        ] = None

    def set_camera_config_provider(
        self, provider: Callable[[int], Optional[Dict[str, Any]]]
    ):
        """Set a provider function to retrieve camera configuration for a camera_id."""
        self._camera_config_provider = provider

    async def initialize(
        self, access_token: str, api_base_url: str = "http://localhost:8080"
    ):
        """Initialize WebRTC streamer and connect to signaling server"""

        # Build signaling WebSocket URL
        api_ws_url = api_base_url.replace("http://", "ws://").replace(
            "https://", "wss://"
        )
        self.signaling_url = (
            f"{api_ws_url}/v1/webrtc/worker/{self.worker_id}?token={access_token}"
        )
        # Save API context for later
        self._api_base_url = api_base_url
        self._access_token = access_token

        logger.info(f"WebRTC Streamer initialized for worker {self.worker_id}")

        # Connect to signaling server
        await self._connect_signaling()

    async def shutdown(self):
        """Shutdown WebRTC streamer and cleanup connections"""

        logger.info(f"Shutting down WebRTC streamer for worker {self.worker_id}")

        # Close all peer connections
        for session_id in list(self.peer_connections.keys()):
            await self._cleanup_session(session_id)

        # Close signaling WebSocket
        if self.signaling_websocket and not self.signaling_websocket.closed:
            await self.signaling_websocket.close()

        self.is_connected = False
        logger.info("WebRTC streamer shutdown complete")

    async def _connect_signaling(self):
        """Connect to WebRTC signaling server"""

        attempt = 0

        while attempt < self.max_reconnect_attempts and not self.is_connected:
            try:
                logger.info(
                    f"Connecting to WebRTC signaling server: {self.signaling_url}"
                )

                self.signaling_websocket = await websockets.connect(
                    self.signaling_url,
                    ping_interval=30,
                    ping_timeout=10,
                    close_timeout=5,
                )

                self.is_connected = True
                logger.info("Connected to WebRTC signaling server")

                # Start message handling task
                asyncio.create_task(self._handle_signaling_messages())
                return

            except Exception as e:
                attempt += 1
                logger.error(
                    f"Failed to connect to signaling server (attempt {attempt}): {e}"
                )

                if attempt < self.max_reconnect_attempts:
                    logger.info(f"Retrying in {self.reconnect_delay} seconds...")
                    await asyncio.sleep(self.reconnect_delay)

        logger.error(
            "Failed to connect to WebRTC signaling server after maximum attempts"
        )

    async def _handle_signaling_messages(self):
        """Handle incoming signaling messages from server"""

        try:
            while self.is_connected and self.signaling_websocket:
                try:
                    message = await self.signaling_websocket.recv()
                    data = json.loads(message)

                    await self._process_signaling_message(data)

                except ConnectionClosed:
                    logger.warning("WebRTC signaling connection closed")
                    break
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in signaling message: {e}")
                except Exception as e:
                    logger.error(f"Error processing signaling message: {e}")

        except Exception as e:
            logger.error(f"Error in signaling message handler: {e}")
        finally:
            self.is_connected = False
            # Attempt reconnection
            if not self.signaling_websocket or self.signaling_websocket.closed:
                logger.info("Attempting to reconnect to signaling server...")
                await asyncio.sleep(self.reconnect_delay)
                await self._connect_signaling()

    async def _process_signaling_message(self, data: Dict[str, Any]):
        """Process incoming signaling message"""

        message_type = data.get("type")

        if message_type == "connected":
            logger.info(f"Worker {self.worker_id} connected to WebRTC signaling")

        elif message_type == "stream-request":
            # Client requested stream - create offer
            await self._handle_stream_request(data)

        elif message_type == "answer":
            # Client sent WebRTC answer
            await self._handle_webrtc_answer(data)

        elif message_type == "ice-candidate":
            # ICE candidate from client
            await self._handle_ice_candidate(data)

        elif message_type == "stream-stop":
            # Stop streaming session
            await self._handle_stream_stop(data)

        elif message_type == "ping":
            # Respond to ping
            await self._send_signaling_message({"type": "pong"})

        else:
            logger.warning(f"Unknown signaling message type: {message_type}")

    async def _handle_stream_request(self, data: Dict[str, Any]):
        """Handle stream request from client"""

        session_id = data.get("session_id")
        client_id = data.get("client_id")
        camera_id = data.get("camera_id")
        site_id = data.get("site_id")

        logger.info(f"WebRTC stream request: session {session_id}, camera {camera_id}")

        try:
            # Ensure camera is active before creating track
            if not self.camera_manager.is_camera_active(camera_id):
                cam_cfg: Optional[Dict[str, Any]] = None
                if self._camera_config_provider:
                    try:
                        cam_cfg = self._camera_config_provider(camera_id)
                    except Exception as e:
                        logger.warning(f"Camera config provider error: {e}")
                if cam_cfg:
                    logger.info(
                        f"Starting camera {camera_id} for WebRTC session {session_id}"
                    )
                    started = await self.camera_manager.start_camera(camera_id, cam_cfg)
                    if not started:
                        logger.warning(
                            f"Camera {camera_id} failed to start; streaming black frames"
                        )
                else:
                    # Try fetch from API when not assigned
                    fetched_cfg = await self._fetch_camera_config(site_id, camera_id)
                    if fetched_cfg:
                        logger.info(
                            f"Fetched camera config for {camera_id} from API; starting camera"
                        )
                        started = await self.camera_manager.start_camera(
                            camera_id, fetched_cfg
                        )
                        if not started:
                            logger.warning(
                                f"Camera {camera_id} failed to start with fetched config; streaming black frames"
                            )
                    else:
                        logger.warning(
                            f"No camera config available for {camera_id}; proceeding but frames may be black"
                        )

            # Wait briefly for the first frame to arrive before creating offer
            # to avoid negotiating while only black frames are present.
            warmup_attempts = 0
            while (
                self.camera_manager.get_latest_frame(camera_id) is None
                and warmup_attempts < 20
            ):
                await asyncio.sleep(0.05)  # up to ~1s
                warmup_attempts += 1
            if warmup_attempts >= 20:
                logger.info(
                    f"WebRTC: no real frame yet for camera {camera_id}, proceeding anyway"
                )
            # Create RTCPeerConnection
            pc = RTCPeerConnection()
            self.peer_connections[session_id] = pc
            self.streaming_sessions[session_id] = camera_id

            # Create video track for camera
            video_track = CameraVideoTrack(camera_id, self.camera_manager)
            pc.addTrack(video_track)

            # Set up ICE candidate handling
            @pc.on("icecandidate")
            async def on_ice_candidate(candidate):
                if candidate:
                    await self._send_signaling_message(
                        {
                            "type": "signaling",
                            "data": {
                                "type": "ice-candidate",
                                "session_id": session_id,
                                "from_id": self.worker_id,
                                "to_id": client_id,
                                "ice_candidate": {
                                    "candidate": candidate.candidate,
                                    "sdpMid": candidate.sdpMid,
                                    "sdpMLineIndex": candidate.sdpMLineIndex,
                                },
                            },
                        }
                    )

            # Set up connection state monitoring
            @pc.on("connectionstatechange")
            async def on_connection_state_change():
                logger.info(f"WebRTC connection state changed to: {pc.connectionState}")
                if pc.connectionState in ["failed", "closed"]:
                    await self._cleanup_session(session_id)

            # Create offer
            offer = await pc.createOffer()

            # Prefer H264 for wider browser compatibility (e.g., Safari)
            def _prefer_video_codec(sdp: str, codec_substr: str = "H264") -> str:
                try:
                    lines = sdp.split("\n")
                    # Map payload type to codec name
                    pt_to_codec = {}
                    for line in lines:
                        if line.startswith("a=rtpmap:"):
                            try:
                                rest = line[len("a=rtpmap:") :].strip()
                                pt, desc = rest.split(" ", 1)
                                codec = desc.split("/")[0].upper()
                                pt_to_codec[pt] = codec
                            except Exception:
                                continue

                    new_lines = []
                    for line in lines:
                        if line.startswith("m=video "):
                            parts = line.strip().split(" ")
                            # parts: m=video <port> <proto> <pt1> <pt2> ...
                            header = parts[:3]
                            pts = parts[3:]
                            preferred = [
                                pt
                                for pt in pts
                                if pt_to_codec.get(pt, "").find(codec_substr) != -1
                            ]
                            others = [pt for pt in pts if pt not in preferred]
                            reordered = header + preferred + others
                            new_lines.append(" ".join(reordered))
                        else:
                            new_lines.append(line)
                    return "\n".join(new_lines)
                except Exception:
                    return sdp

            munged_sdp = _prefer_video_codec(offer.sdp, "H264")
            # Set local description with munged SDP
            offer = RTCSessionDescription(sdp=munged_sdp, type="offer")
            await pc.setLocalDescription(offer)

            # Send offer to client via signaling server
            await self._send_signaling_message(
                {
                    "type": "signaling",
                    "data": {
                        "type": "offer",
                        "session_id": session_id,
                        "from_id": self.worker_id,
                        "to_id": client_id,
                        "sdp": pc.localDescription.sdp,
                    },
                }
            )

            logger.info(f"WebRTC offer sent for session {session_id}")

        except Exception as e:
            logger.error(f"Failed to handle stream request: {e}")
            await self._cleanup_session(session_id)

    async def _handle_webrtc_answer(self, data: Dict[str, Any]):
        """Handle WebRTC answer from client"""

        session_id = data.get("session_id")
        sdp = data.get("sdp")

        logger.info(f"Received WebRTC answer for session {session_id}")

        try:
            pc = self.peer_connections.get(session_id)
            if not pc:
                logger.warning(f"No peer connection found for session {session_id}")
                return

            # Set remote description (client's answer)
            answer = RTCSessionDescription(sdp=sdp, type="answer")
            await pc.setRemoteDescription(answer)

            logger.info(f"WebRTC answer processed for session {session_id}")

        except Exception as e:
            logger.error(f"Failed to handle WebRTC answer: {e}")
            await self._cleanup_session(session_id)

    async def _handle_ice_candidate(self, data: Dict[str, Any]):
        """Handle ICE candidate from client"""

        session_id = data.get("session_id")
        ice_data = data.get("ice_candidate", {})

        try:
            pc = self.peer_connections.get(session_id)
            if not pc:
                logger.warning(f"No peer connection found for session {session_id}")
                return

            # Add ICE candidate
            candidate = RTCIceCandidate(
                candidate=ice_data.get("candidate"),
                sdpMid=ice_data.get("sdpMid"),
                sdpMLineIndex=ice_data.get("sdpMLineIndex"),
            )
            await pc.addIceCandidate(candidate)

            logger.debug(f"ICE candidate added for session {session_id}")

        except Exception as e:
            logger.error(f"Failed to handle ICE candidate: {e}")

    async def _handle_stream_stop(self, data: Dict[str, Any]):
        """Handle stream stop request"""

        session_id = data.get("session_id")
        logger.info(f"Stopping WebRTC session {session_id}")

        await self._cleanup_session(session_id)

    async def _cleanup_session(self, session_id: str):
        """Clean up WebRTC session and peer connection"""

        logger.info(f"Cleaning up WebRTC session {session_id}")

        try:
            # Close peer connection
            if session_id in self.peer_connections:
                pc = self.peer_connections[session_id]
                await pc.close()
                del self.peer_connections[session_id]

            # Remove session tracking
            if session_id in self.streaming_sessions:
                del self.streaming_sessions[session_id]

        except Exception as e:
            logger.error(f"Error cleaning up session {session_id}: {e}")

    async def _send_signaling_message(self, message: Dict[str, Any]):
        """Send message to signaling server"""

        try:
            if self.signaling_websocket and not self.signaling_websocket.closed:
                await self.signaling_websocket.send(json.dumps(message))
            else:
                logger.warning(
                    "Cannot send signaling message - WebSocket not connected"
                )

        except Exception as e:
            logger.error(f"Failed to send signaling message: {e}")

    def get_active_sessions(self) -> Dict[str, Any]:
        """Get information about active WebRTC sessions"""

        return {
            "active_sessions": len(self.streaming_sessions),
            "sessions": {
                session_id: {
                    "camera_id": camera_id,
                    "connection_state": (
                        self.peer_connections.get(session_id, {}).connectionState
                        if session_id in self.peer_connections
                        else "unknown"
                    ),
                }
                for session_id, camera_id in self.streaming_sessions.items()
            },
            "signaling_connected": self.is_connected,
        }

    async def _fetch_camera_config(
        self, site_id: int, camera_id: int
    ) -> Optional[Dict[str, Any]]:
        """Fetch camera details from API to build camera config."""
        if not getattr(self, "_api_base_url", None) or not getattr(
            self, "_access_token", None
        ):
            return None
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self._api_base_url}/v1/sites/{site_id}/cameras/{camera_id}",
                    headers={"Authorization": f"Bearer {self._access_token}"},
                )
                if resp.status_code != 200:
                    logger.warning(f"Fetch camera config failed: {resp.status_code}")
                    return None
                cam = resp.json()
                return {
                    "camera_type": cam.get("camera_type", "webcam"),
                    "rtsp_url": cam.get("rtsp_url"),
                    "device_index": cam.get("device_index", 0),
                    "fps": 15,
                    "width": 640,
                    "height": 480,
                }
        except Exception as e:
            logger.warning(f"Error fetching camera config: {e}")
            return None
