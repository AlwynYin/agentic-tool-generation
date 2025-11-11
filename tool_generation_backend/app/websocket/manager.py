"""
WebSocket connection manager for real-time communication.
"""

from typing import Dict, List, Set, Any, Optional
import json
import logging
from datetime import datetime, timezone

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections for real-time session updates."""

    def __init__(self):
        """Initialize WebSocket manager."""
        # Active connections by session ID
        self.session_connections: Dict[str, Set[WebSocket]] = {}

        # Connection metadata
        self.connection_metadata: Dict[WebSocket, Dict[str, Any]] = {}

        # Global connections (for system-wide notifications)
        self.global_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket, session_id: str):
        """
        Accept WebSocket connection and add to session room.

        Args:
            websocket: WebSocket connection
            session_id: Session ID for the connection
        """
        try:
            await websocket.accept()

            # Add to session connections
            if session_id not in self.session_connections:
                self.session_connections[session_id] = set()

            self.session_connections[session_id].add(websocket)

            # Store connection metadata
            self.connection_metadata[websocket] = {
                "session_id": session_id,
                "connected_at": datetime.now(timezone.utc).isoformat(),
                "last_activity": datetime.now(timezone.utc).isoformat()
            }

            # Add to global connections
            self.global_connections.add(websocket)

            logger.info(f"WebSocket connected for session {session_id}")

            # Send connection confirmation
            await self._send_to_websocket(websocket, {
                "type": "connection-established",
                "session_id": session_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

            # Keep connection alive and handle messages
            await self._handle_connection(websocket, session_id)

        except WebSocketDisconnect:
            await self.disconnect(websocket, session_id)
        except Exception as e:
            logger.error(f"WebSocket connection error for session {session_id}: {e}")
            await self.disconnect(websocket, session_id)

    async def disconnect(self, websocket: WebSocket, session_id: str):
        """
        Remove WebSocket connection from session room.

        Args:
            websocket: WebSocket connection
            session_id: Session ID
        """
        try:
            # Remove from session connections
            if session_id in self.session_connections:
                self.session_connections[session_id].discard(websocket)

                # Clean up empty session rooms
                if not self.session_connections[session_id]:
                    del self.session_connections[session_id]

            # Remove from global connections
            self.global_connections.discard(websocket)

            # Clean up metadata
            if websocket in self.connection_metadata:
                del self.connection_metadata[websocket]

            logger.info(f"WebSocket disconnected for session {session_id}")

        except Exception as e:
            logger.error(f"Error disconnecting WebSocket for session {session_id}: {e}")

    async def send_to_session(self, session_id: str, message: Dict[str, Any]):
        """
        Send message to all connections in a session.

        Args:
            session_id: Session ID
            message: Message to send
        """
        if session_id not in self.session_connections:
            logger.debug(f"No connections for session {session_id}")
            return

        # Add timestamp if not present
        if "timestamp" not in message:
            message["timestamp"] = datetime.now(timezone.utc).isoformat()

        message_str = json.dumps(message)
        connections = self.session_connections[session_id].copy()

        disconnected_connections = []

        for websocket in connections:
            try:
                await self._send_to_websocket(websocket, message)

                # Update last activity
                if websocket in self.connection_metadata:
                    self.connection_metadata[websocket]["last_activity"] = datetime.now(timezone.utc).isoformat()

            except Exception as e:
                logger.error(f"Failed to send message to WebSocket in session {session_id}: {e}")
                disconnected_connections.append(websocket)

        # Clean up disconnected connections
        for websocket in disconnected_connections:
            await self.disconnect(websocket, session_id)

        if connections:
            logger.debug(f"Sent message to {len(connections)} connections in session {session_id}")

    async def send_to_all(self, message: Dict[str, Any]):
        """
        Send message to all connected clients.

        Args:
            message: Message to send
        """
        if "timestamp" not in message:
            message["timestamp"] = datetime.now(timezone.utc).isoformat()

        connections = self.global_connections.copy()
        disconnected_connections = []

        for websocket in connections:
            try:
                await self._send_to_websocket(websocket, message)

                # Update last activity
                if websocket in self.connection_metadata:
                    self.connection_metadata[websocket]["last_activity"] = datetime.now(timezone.utc).isoformat()

            except Exception as e:
                logger.error(f"Failed to send global message to WebSocket: {e}")
                disconnected_connections.append(websocket)

        # Clean up disconnected connections
        for websocket in disconnected_connections:
            session_id = self.connection_metadata.get(websocket, {}).get("session_id", "unknown")
            await self.disconnect(websocket, session_id)

        if connections:
            logger.debug(f"Sent global message to {len(connections)} connections")

    async def send_to_job(self, job_id: str, message: Dict[str, Any]):
        """
        Send job-related message to all connected clients.

        For now, broadcasts to all connections. Future enhancement could
        support job-specific subscriptions.

        Args:
            job_id: Job ID
            message: Message to send (will have jobId added if not present)
        """
        # Ensure jobId is in message for proper frontend routing
        if "jobId" not in message:
            message["jobId"] = job_id

        # Broadcast to all for now (frontend will filter by jobId)
        await self.send_to_all(message)
        logger.debug(f"Broadcasted job message for {job_id}")

    async def send_to_task(self, task_id: str, job_id: str, message: Dict[str, Any]):
        """
        Send task-related message to all connected clients.

        For now, broadcasts to all connections. Future enhancement could
        support task-specific subscriptions.

        Args:
            task_id: Task ID
            job_id: Job ID (for frontend routing)
            message: Message to send (will have taskId/jobId added if not present)
        """
        # Ensure taskId and jobId are in message for proper frontend routing
        if "taskId" not in message:
            message["taskId"] = task_id
        if "jobId" not in message:
            message["jobId"] = job_id

        # Broadcast to all for now (frontend will filter by taskId/jobId)
        await self.send_to_all(message)
        logger.debug(f"Broadcasted task message for task {task_id} in job {job_id}")

    async def _send_to_websocket(self, websocket: WebSocket, message: Dict[str, Any]):
        """
        Send message to a specific WebSocket connection.

        Args:
            websocket: WebSocket connection
            message: Message to send
        """
        try:
            message_str = json.dumps(message, default=str)
            await websocket.send_text(message_str)
        except Exception as e:
            logger.error(f"Failed to send WebSocket message: {e}")
            raise

    async def _handle_connection(self, websocket: WebSocket, session_id: str):
        """
        Handle WebSocket connection lifecycle and incoming messages.

        Args:
            websocket: WebSocket connection
            session_id: Session ID
        """
        try:
            while True:
                # Receive message from client
                data = await websocket.receive_text()

                try:
                    message = json.loads(data)
                    await self._handle_client_message(websocket, session_id, message)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON received from session {session_id}: {data}")
                    await self._send_to_websocket(websocket, {
                        "type": "error",
                        "message": "Invalid JSON format"
                    })

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for session {session_id}")
        except Exception as e:
            logger.error(f"WebSocket handler error for session {session_id}: {e}")

    async def _handle_client_message(self, websocket: WebSocket, session_id: str, message: Dict[str, Any]):
        """
        Handle incoming message from client.

        Args:
            websocket: WebSocket connection
            session_id: Session ID
            message: Received message
        """
        message_type = message.get("type", "unknown")

        try:
            if message_type == "ping":
                # Respond to ping with pong
                await self._send_to_websocket(websocket, {
                    "type": "pong",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

            elif message_type == "subscribe":
                # Handle subscription to specific events
                event_types = message.get("events", [])
                logger.info(f"Session {session_id} subscribed to events: {event_types}")

                # Store subscription preferences
                if websocket in self.connection_metadata:
                    self.connection_metadata[websocket]["subscriptions"] = event_types

                await self._send_to_websocket(websocket, {
                    "type": "subscription-confirmed",
                    "events": event_types
                })

            elif message_type == "heartbeat":
                # Update last activity
                if websocket in self.connection_metadata:
                    self.connection_metadata[websocket]["last_activity"] = datetime.now(timezone.utc).isoformat()

            else:
                logger.warning(f"Unknown message type '{message_type}' from session {session_id}")
                await self._send_to_websocket(websocket, {
                    "type": "error",
                    "message": f"Unknown message type: {message_type}"
                })

        except Exception as e:
            logger.error(f"Error handling client message from session {session_id}: {e}")
            await self._send_to_websocket(websocket, {
                "type": "error",
                "message": "Internal server error"
            })

    def get_connection_count(self) -> int:
        """
        Get total number of active connections.

        Returns:
            int: Number of active connections
        """
        return len(self.global_connections)

    def get_session_connection_count(self, session_id: str) -> int:
        """
        Get number of connections for a specific session.

        Args:
            session_id: Session ID

        Returns:
            int: Number of connections for the session
        """
        return len(self.session_connections.get(session_id, set()))

    def get_active_sessions(self) -> List[str]:
        """
        Get list of sessions with active connections.

        Returns:
            List[str]: List of session IDs with active connections
        """
        return list(self.session_connections.keys())

    def get_connection_stats(self) -> Dict[str, Any]:
        """
        Get detailed connection statistics.

        Returns:
            Dict[str, Any]: Connection statistics
        """
        now = datetime.now(timezone.utc)

        session_stats = {}
        for session_id, connections in self.session_connections.items():
            session_stats[session_id] = {
                "connection_count": len(connections),
                "connections": [
                    {
                        "connected_at": self.connection_metadata.get(ws, {}).get("connected_at"),
                        "last_activity": self.connection_metadata.get(ws, {}).get("last_activity"),
                        "subscriptions": self.connection_metadata.get(ws, {}).get("subscriptions", [])
                    }
                    for ws in connections
                ]
            }

        return {
            "total_connections": len(self.global_connections),
            "active_sessions": len(self.session_connections),
            "session_stats": session_stats,
            "timestamp": now.isoformat()
        }

    async def broadcast_system_message(self, message_type: str, data: Dict[str, Any]):
        """
        Broadcast system-wide message to all connections.

        Args:
            message_type: Type of system message
            data: Message data
        """
        message = {
            "type": "system-message",
            "message_type": message_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        await self.send_to_all(message)

    async def cleanup_stale_connections(self, max_idle_minutes: int = 30):
        """
        Clean up connections that have been idle for too long.

        Args:
            max_idle_minutes: Maximum idle time before cleanup
        """
        now = datetime.now(timezone.utc)
        stale_connections = []

        for websocket, metadata in self.connection_metadata.items():
            last_activity_str = metadata.get("last_activity")
            if last_activity_str:
                try:
                    last_activity = datetime.fromisoformat(last_activity_str.replace('Z', '+00:00'))
                    idle_minutes = (now - last_activity).total_seconds() / 60

                    if idle_minutes > max_idle_minutes:
                        stale_connections.append((websocket, metadata.get("session_id", "unknown")))

                except ValueError:
                    # Invalid timestamp format, consider stale
                    stale_connections.append((websocket, metadata.get("session_id", "unknown")))

        # Clean up stale connections
        for websocket, session_id in stale_connections:
            logger.info(f"Cleaning up stale connection for session {session_id}")
            await self.disconnect(websocket, session_id)

        if stale_connections:
            logger.info(f"Cleaned up {len(stale_connections)} stale connections")