"""Tests for the event bus pub/sub system."""

import asyncio
import pytest
from event_bus import EventBus


@pytest.fixture
def bus():
    return EventBus()


class TestEventBus:
    """Test event publishing and subscribing."""

    @pytest.mark.asyncio
    async def test_subscribe_and_emit(self, bus):
        received = []

        async def handler(event_type, data):
            received.append((event_type, data))

        bus.subscribe("wifi.connected", handler)
        await bus.emit("wifi.connected", {"ssid": "test"})

        assert len(received) == 1
        assert received[0] == ("wifi.connected", {"ssid": "test"})

    @pytest.mark.asyncio
    async def test_wildcard_subscriber(self, bus):
        received = []

        async def handler(event_type, data):
            received.append(event_type)

        bus.subscribe("*", handler)
        await bus.emit("wifi.connected", {})
        await bus.emit("battery.low", {})

        assert received == ["wifi.connected", "battery.low"]

    @pytest.mark.asyncio
    async def test_no_subscribers(self, bus):
        # Should not raise
        await bus.emit("some.event", {"data": 123})

    @pytest.mark.asyncio
    async def test_unsubscribe(self, bus):
        received = []

        async def handler(event_type, data):
            received.append(event_type)

        bus.subscribe("test.event", handler)
        await bus.emit("test.event", {})
        assert len(received) == 1

        bus.unsubscribe("test.event", handler)
        await bus.emit("test.event", {})
        assert len(received) == 1  # No new events

    @pytest.mark.asyncio
    async def test_unsubscribe_wildcard(self, bus):
        received = []

        async def handler(event_type, data):
            received.append(event_type)

        bus.subscribe("*", handler)
        await bus.emit("a", {})
        bus.unsubscribe("*", handler)
        await bus.emit("b", {})

        assert received == ["a"]

    @pytest.mark.asyncio
    async def test_emit_default_empty_data(self, bus):
        received = []

        async def handler(event_type, data):
            received.append(data)

        bus.subscribe("test", handler)
        await bus.emit("test")

        assert received == [{}]

    @pytest.mark.asyncio
    async def test_handler_error_doesnt_break_others(self, bus):
        results = []

        async def bad_handler(event_type, data):
            raise RuntimeError("oops")

        async def good_handler(event_type, data):
            results.append("ok")

        bus.subscribe("test", bad_handler)
        bus.subscribe("test", good_handler)
        await bus.emit("test", {})

        assert results == ["ok"]

    @pytest.mark.asyncio
    async def test_shutdown_clears_subscribers(self, bus):
        async def handler(event_type, data):
            pass

        bus.subscribe("test", handler)
        bus.subscribe("*", handler)
        await bus.shutdown()

        assert len(bus._subscribers) == 0
        assert len(bus._wildcard_subscribers) == 0

    @pytest.mark.asyncio
    async def test_multiple_subscribers_same_event(self, bus):
        results = []

        async def handler_a(event_type, data):
            results.append("a")

        async def handler_b(event_type, data):
            results.append("b")

        bus.subscribe("test", handler_a)
        bus.subscribe("test", handler_b)
        await bus.emit("test", {})

        assert "a" in results
        assert "b" in results
