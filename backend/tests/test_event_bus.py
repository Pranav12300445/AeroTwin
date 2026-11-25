"""EventBus against an in-process Redis (fakeredis): publish, streams, subscribe/listen, history."""

import json
from unittest.mock import AsyncMock

import pytest

from app import event_bus
from tests.conftest import wait_for


async def _collect(bus, channel):
    """Subscribe a raw pubsub client to `channel` and return it (messages read via get_message)."""
    ps = bus._redis.pubsub()
    await ps.subscribe(channel)
    await ps.get_message(timeout=0.1)  # drain the subscribe confirmation
    return ps


async def test_publish_sends_envelope_to_channel(bus):
    ps = await _collect(bus, "telemetry.raw")
    await bus.publish("telemetry.raw", {"egt": 630}, agent_name="telemetry_monitor")

    msg = await ps.get_message(ignore_subscribe_messages=True, timeout=1)
    event = json.loads(msg["data"])
    assert event["channel"] == "telemetry.raw"
    assert event["agent"] == "telemetry_monitor"
    assert event["data"] == {"egt": 630}
    assert "T" in event["timestamp"]  # ISO-8601


async def test_publish_appends_to_durable_stream(bus):
    await bus.publish("fault.predicted", {"fault_type": "bearing_wear"}, agent_name="fault_predictor")
    entries = await bus._redis.xrange("stream:fault.predicted")
    assert len(entries) == 1
    assert json.loads(entries[0][1]["payload"])["data"]["fault_type"] == "bearing_wear"


async def test_publish_mirrors_to_agent_activity_with_message_summary(bus):
    ps = await _collect(bus, "agent.activity")
    await bus.publish("anomaly.detected", {"message": "Anomaly detected!"}, agent_name="telemetry_monitor")

    activity = json.loads((await ps.get_message(ignore_subscribe_messages=True, timeout=1))["data"])
    assert activity["agent"] == "telemetry_monitor"
    assert activity["event"] == "anomaly.detected"
    assert activity["summary"] == "Anomaly detected!"


@pytest.mark.parametrize("data,expected", [
    ({"summary": "from summary"}, "from summary"),
    ({"x": 1}, "{'x': 1}"),
    ({"blob": "y" * 500}, None),  # falls back to str(data) truncated to 120 chars
])
async def test_activity_summary_fallbacks(bus, data, expected):
    ps = await _collect(bus, "agent.activity")
    await bus.publish("some.channel", data)
    activity = json.loads((await ps.get_message(ignore_subscribe_messages=True, timeout=1))["data"])
    if expected is None:
        assert len(activity["summary"]) == 120
    else:
        assert activity["summary"] == expected


async def test_publishing_on_agent_activity_does_not_recurse(bus):
    await bus.publish("agent.activity", {"summary": "x"})
    # only the stream copy exists; no second agent.activity publish was triggered
    assert await bus._redis.xlen("stream:agent.activity") == 1


async def test_stream_is_capped(bus, monkeypatch):
    # maxlen=5000 is passed to XADD; verify the argument rather than writing 5000 entries
    real_xadd, seen = bus._redis.xadd, {}

    async def spy(*args, **kwargs):
        seen.update(kwargs)
        return await real_xadd(*args, **kwargs)

    monkeypatch.setattr(bus._redis, "xadd", spy)
    await bus.publish("telemetry.raw", {"a": 1})
    assert seen["maxlen"] == 5000


async def test_subscribe_dispatches_to_all_callbacks(listening_bus):
    seen_a, seen_b = [], []

    async def cb_a(event): seen_a.append(event)
    async def cb_b(event): seen_b.append(event)

    await listening_bus.subscribe("fault.predicted", cb_a)
    await listening_bus.subscribe("fault.predicted", cb_b)
    await listening_bus.publish("fault.predicted", {"fault_type": "compressor_stall"}, agent_name="fault_predictor")

    await wait_for(lambda: seen_a and seen_b)
    assert seen_a[0]["data"]["fault_type"] == "compressor_stall"
    assert seen_b[0]["agent"] == "fault_predictor"


async def test_subscribers_only_receive_their_channel(listening_bus):
    got = []

    async def cb(event): got.append(event["channel"])

    await listening_bus.subscribe("anomaly.detected", cb)
    await listening_bus.publish("twin.residual", {"a": 1})
    await listening_bus.publish("anomaly.detected", {"a": 2})
    await wait_for(lambda: got)
    assert got == ["anomaly.detected"]


async def test_failing_callback_does_not_stop_the_listener(listening_bus, capsys):
    ok = []

    async def bad(event): raise RuntimeError("boom")
    async def good(event): ok.append(event["data"]["n"])

    await listening_bus.subscribe("telemetry.raw", bad)
    await listening_bus.subscribe("telemetry.raw", good)
    await listening_bus.publish("telemetry.raw", {"n": 1})
    await listening_bus.publish("telemetry.raw", {"n": 2})

    await wait_for(lambda: ok == [1, 2])
    assert "Error in callback" in capsys.readouterr().out


async def test_get_recent_events_returns_chronological_and_respects_count(bus):
    for n in range(5):
        await bus.publish("maintenance.recommended", {"n": n})
    events = await bus.get_recent_events("maintenance.recommended", count=3)
    assert [e["data"]["n"] for e in events] == [2, 3, 4]


async def test_get_recent_events_unknown_channel_is_empty(bus):
    assert await bus.get_recent_events("nope") == []


async def test_get_recent_events_returns_empty_on_redis_error(bus, monkeypatch):
    monkeypatch.setattr(bus._redis, "xrevrange", AsyncMock(side_effect=ConnectionError("down")))
    assert await bus.get_recent_events("telemetry.raw") == []


async def test_stop_ends_listen_loop(bus):
    import asyncio
    task = asyncio.create_task(bus.listen())
    await wait_for(lambda: bus._running)
    bus.stop()
    await asyncio.wait_for(task, timeout=2)
    assert bus._running is False


def test_get_event_bus_is_a_singleton(monkeypatch):
    monkeypatch.setattr(event_bus, "_event_bus", None)
    assert event_bus.get_event_bus() is event_bus.get_event_bus()
