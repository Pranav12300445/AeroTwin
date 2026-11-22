"""
Redis Event Bus — pub/sub + streams for agent coordination.

Channels:
    telemetry.raw           — raw sensor readings
    anomaly.detected        — Telemetry Monitor → Fault Predictor
    twin.residual           — Digital Twin Sync → Fault Predictor
    fault.predicted         — Fault Predictor → Maintenance Planner
    maintenance.recommended — Maintenance Planner → Dashboard
    agent.activity          — all agents → Dashboard (observability log)
"""

import json
import asyncio
from datetime import datetime, timezone
from typing import Callable, Optional

import redis.asyncio as aioredis

from .config import get_settings


class EventBus:
    """Async Redis-backed event bus for agent coordination."""

    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None
        self._pubsub: Optional[aioredis.client.PubSub] = None
        self._subscribers: dict[str, list[Callable]] = {}
        self._running = False

    async def connect(self):
        settings = get_settings()
        self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        self._pubsub = self._redis.pubsub()
        await self._redis.ping()

    async def disconnect(self):
        if self._pubsub:
            await self._pubsub.unsubscribe()
            await self._pubsub.close()
        if self._redis:
            await self._redis.close()

    async def publish(self, channel: str, data: dict, agent_name: str = "system") -> None:
        """Publish an event to a channel."""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": agent_name,
            "channel": channel,
            "data": data,
        }
        payload = json.dumps(event, default=str)

        # Pub/Sub for real-time
        await self._redis.publish(channel, payload)

        # Also append to Redis Stream for durability / audit log
        await self._redis.xadd(f"stream:{channel}", {"payload": payload}, maxlen=5000)

        # Publish to agent activity channel for dashboard observability
        if channel != "agent.activity":
            activity = {
                "timestamp": event["timestamp"],
                "agent": agent_name,
                "event": channel,
                "summary": data.get("message", data.get("summary", str(data)[:120])),
            }
            await self._redis.publish("agent.activity", json.dumps(activity, default=str))

    async def subscribe(self, channel: str, callback: Callable) -> None:
        """Subscribe to a channel with a callback."""
        if channel not in self._subscribers:
            self._subscribers[channel] = []
            await self._pubsub.subscribe(channel)
        self._subscribers[channel].append(callback)

    async def listen(self) -> None:
        """Listen for messages and dispatch to callbacks."""
        self._running = True
        while self._running:
            try:
                message = await self._pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
                if message and message["type"] == "message":
                    channel = message["channel"]
                    data = json.loads(message["data"])
                    for cb in self._subscribers.get(channel, []):
                        try:
                            await cb(data)
                        except Exception as e:
                            print(f"[EventBus] Error in callback for {channel}: {e}")
                await asyncio.sleep(0.01)
            except Exception as e:
                print(f"[EventBus] Listen error: {e}")
                await asyncio.sleep(1)

    def stop(self):
        self._running = False

    async def get_recent_events(self, channel: str, count: int = 50) -> list[dict]:
        """Get recent events from a stream (for dashboard on load)."""
        try:
            entries = await self._redis.xrevrange(f"stream:{channel}", count=count)
            events = []
            for entry_id, fields in entries:
                events.append(json.loads(fields["payload"]))
            return list(reversed(events))
        except Exception:
            return []


# Singleton
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus

