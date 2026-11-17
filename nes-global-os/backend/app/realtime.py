"""Real-time hub for the employee app: WebSocket connections, presence and cross-worker delivery.

The API runs several worker processes. A message for a user may arrive on a worker that doesn't hold that
user's WebSocket, so every message is published on Redis and each worker delivers it to its own sockets.
Without Redis (tests / single process) delivery is local only.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections import defaultdict

from fastapi import WebSocket

from .config import settings

log = logging.getLogger("nes.realtime")
CHANNEL = "nes:rt"
PRESENCE = "nes:presence"
ONLINE_WINDOW_S = 75


class Hub:
    def __init__(self) -> None:
        self.local: dict[str, set[WebSocket]] = defaultdict(set)
        self.redis = None
        self._task: asyncio.Task | None = None
        self._presence_local: dict[str, float] = {}

    # ---------------------------------------------------------------- lifecycle
    async def start(self) -> None:
        try:
            import redis.asyncio as aioredis
            r = aioredis.from_url(settings.redis_url, socket_connect_timeout=1)
            await r.ping()
            self.redis = r
            self._task = asyncio.create_task(self._listen())
        except Exception as e:  # pragma: no cover - depends on environment
            log.warning("realtime: Redis unavailable (%s) — single-process delivery only", e.__class__.__name__)
            self.redis = None

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
        if self.redis:
            try:
                await self.redis.aclose()
            except Exception:
                pass

    async def _listen(self) -> None:
        while True:
            try:
                ps = self.redis.pubsub()
                await ps.subscribe(CHANNEL)
                async for item in ps.listen():
                    if item.get("type") != "message":
                        continue
                    data = json.loads(item["data"])
                    await self._deliver_local(data["to"], data["msg"])
            except asyncio.CancelledError:
                return
            except Exception:
                log.exception("realtime listener error; reconnecting")
                await asyncio.sleep(1)

    # ---------------------------------------------------------------- connections
    def add(self, user_id: uuid.UUID, ws: WebSocket) -> None:
        self.local[str(user_id)].add(ws)

    def remove(self, user_id: uuid.UUID, ws: WebSocket) -> None:
        s = self.local.get(str(user_id))
        if s:
            s.discard(ws)
            if not s:
                self.local.pop(str(user_id), None)

    async def send(self, user_ids, msg: dict) -> None:
        ids = [str(u) for u in user_ids]
        if not ids:
            return
        if self.redis:
            try:
                await self.redis.publish(CHANNEL, json.dumps({"to": ids, "msg": msg}, default=str))
                return
            except Exception:
                log.warning("realtime: publish failed, delivering locally")
        await self._deliver_local(ids, msg)

    async def _deliver_local(self, ids: list[str], msg: dict) -> None:
        for uid in ids:
            for ws in list(self.local.get(uid, ())):
                try:
                    await ws.send_json(msg)
                except Exception:
                    self.local.get(uid, set()).discard(ws)

    # ---------------------------------------------------------------- presence
    async def touch(self, user_id: uuid.UUID) -> None:
        now = time.time()
        self._presence_local[str(user_id)] = now
        if self.redis:
            try:
                await self.redis.hset(PRESENCE, str(user_id), now)
            except Exception:
                pass

    async def offline(self, user_id: uuid.UUID) -> None:
        if str(user_id) in self.local:
            return  # another socket of this user is still open on this worker
        self._presence_local.pop(str(user_id), None)
        if self.redis:
            try:
                await self.redis.hdel(PRESENCE, str(user_id))
            except Exception:
                pass

    async def online_ids(self) -> set[str]:
        now = time.time()
        if self.redis:
            try:
                raw = await self.redis.hgetall(PRESENCE)
                return {k.decode() for k, v in raw.items() if now - float(v) < ONLINE_WINDOW_S}
            except Exception:
                pass
        return {k for k, v in self._presence_local.items() if now - v < ONLINE_WINDOW_S}


hub = Hub()


def online_ids_sync() -> set[str]:
    """For synchronous endpoints: read presence straight from Redis."""
    import redis as syncredis
    now = time.time()
    try:
        r = syncredis.Redis.from_url(settings.redis_url, socket_timeout=0.5, socket_connect_timeout=0.5)
        return {k.decode() for k, v in r.hgetall(PRESENCE).items() if now - float(v) < ONLINE_WINDOW_S}
    except Exception:
        return {k for k, v in hub._presence_local.items() if now - v < ONLINE_WINDOW_S}
