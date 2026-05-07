"""Tiny OBS WebSocket helper for save replay buffer."""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger(__name__)


class OBSClient:
    """Wraps obsws-python so the rest of the analyzer doesn't care about it."""

    def __init__(self, host: str, port: int, password: str = "") -> None:
        self.host = host
        self.port = port
        self.password = password
        self._client = None

    def _connect(self):
        if self._client is not None:
            return self._client
        try:
            import obsws_python as obsws
        except ImportError:
            log.warning("obsws-python not installed; OBS integration disabled")
            return None
        try:
            self._client = obsws.ReqClient(
                host=self.host,
                port=self.port,
                password=self.password or "",
                timeout=3,
            )
            log.info("Connected to OBS at %s:%s", self.host, self.port)
        except Exception as e:
            log.warning("OBS connection failed: %s", e)
            self._client = None
        return self._client

    def save_replay(self) -> bool:
        client = self._connect()
        if client is None:
            return False
        try:
            client.save_replay_buffer()
            log.info("Sent SaveReplayBuffer to OBS")
            return True
        except Exception as e:
            log.warning("OBS save_replay failed: %s", e)
            self._client = None
            return False

    def close(self) -> None:
        try:
            if self._client is not None:
                self._client.disconnect()
        except Exception:
            pass
        self._client = None
