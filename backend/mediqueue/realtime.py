"""Realtime delivery: WebSocket broadcast with durable polling fallback."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("mediqueue.realtime")


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


class RealtimeHub:
    """In-process fan-out of committed events to connected WebSocket clients."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        try:
            await ws.send_text(json.dumps({"type": "hello", "ts": str(_now_iso())}))
        except Exception:  # noqa: BLE001 - client vanished during handshake
            return
        async with self._lock:
            self._clients.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, events: list[dict[str, Any]]) -> None:
        if not events:
            return
        async with self._lock:
            targets = list(self._clients)
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_text(json.dumps({"events": events}, default=str))
            except Exception:  # noqa: BLE001 - client vanished; drop it
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._clients.discard(ws)

    @property
    def client_count(self) -> int:
        return len(self._clients)


hub = RealtimeHub()
