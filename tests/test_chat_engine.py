"""Tests for the Claude chat engine."""

import asyncio
import json
import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from chat_engine import ChatEngine, ChatResponse, Message, MessageRole


@pytest.fixture
def engine():
    """Create a ChatEngine instance."""
    return ChatEngine()


class TestChatEngineTools:
    """Test tool registration and management."""

    def test_register_tool(self, engine):
        async def dummy_tool(**kwargs):
            return {"result": "ok"}

        engine.register_tool("test_tool", dummy_tool, "A test tool")
        assert "test_tool" in engine.tools
        assert engine.tools["test_tool"].description == "A test tool"

    def test_build_tools_spec(self, engine):
        async def dummy(**kwargs):
            return {}

        engine.register_tool("wifi_scan", dummy, "Scan WiFi")
        engine.register_tool("get_battery", dummy, "Get battery")

        specs = engine._build_tools_spec()
        assert len(specs) == 2
        names = [s["name"] for s in specs]
        assert "wifi_scan" in names
        assert "get_battery" in names

    def test_build_tools_spec_empty(self, engine):
        assert engine._build_tools_spec() == []

    @pytest.mark.asyncio
    async def test_execute_tool_success(self, engine):
        async def my_tool(**kwargs):
            return {"networks": ["WiFi1", "WiFi2"]}

        engine.register_tool("wifi_scan", my_tool, "Scan")

        result = await engine._execute_tool({
            "id": "call_123",
            "name": "wifi_scan",
            "input": {},
        })

        assert result["tool_use_id"] == "call_123"
        data = json.loads(result["content"])
        assert data["networks"] == ["WiFi1", "WiFi2"]

    @pytest.mark.asyncio
    async def test_execute_tool_unknown(self, engine):
        result = await engine._execute_tool({
            "id": "call_456",
            "name": "nonexistent",
            "input": {},
        })

        data = json.loads(result["content"])
        assert "error" in data
        assert "Unknown tool" in data["error"]

    @pytest.mark.asyncio
    async def test_execute_tool_error(self, engine):
        async def bad_tool(**kwargs):
            raise RuntimeError("Something broke")

        engine.register_tool("bad", bad_tool, "Broken tool")

        result = await engine._execute_tool({
            "id": "call_789",
            "name": "bad",
            "input": {},
        })

        assert result.get("is_error") is True
        data = json.loads(result["content"])
        assert "Something broke" in data["error"]


class TestChatEngineMessages:
    """Test message handling."""

    def test_message_to_api_format(self):
        msg = Message(role=MessageRole.USER, text="Hello Claude")
        result = msg.to_api_format()
        assert result == {"role": "user", "content": "Hello Claude"}

    def test_assistant_message_format(self):
        msg = Message(role=MessageRole.ASSISTANT, text="Hi there!")
        result = msg.to_api_format()
        assert result == {"role": "assistant", "content": "Hi there!"}

    def test_message_with_tool_calls(self):
        msg = Message(
            role=MessageRole.ASSISTANT,
            text="Let me check that.",
            tool_calls=[{"id": "tc1", "name": "wifi_scan", "input": {}}],
        )
        result = msg.to_api_format()
        assert isinstance(result["content"], list)
        assert result["content"][0]["type"] == "text"
        assert result["content"][1]["type"] == "tool_use"

    def test_build_api_messages(self, engine):
        engine.messages = [
            Message(role=MessageRole.USER, text="Hi"),
            Message(role=MessageRole.ASSISTANT, text="Hello!"),
        ]
        msgs = engine._build_api_messages()
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"

    def test_trim_history(self, engine):
        engine.MAX_HISTORY = 5
        for i in range(10):
            engine.messages.append(
                Message(role=MessageRole.USER, text=f"msg {i}")
            )
        engine._trim_history()
        assert len(engine.messages) == 5

    def test_clear_history(self, engine):
        engine.messages.append(Message(role=MessageRole.USER, text="Hi"))
        engine.clear_history()
        assert len(engine.messages) == 0


class TestChatEngineAPI:
    """Test API key handling."""

    def test_no_api_key_returns_error(self, engine):
        assert engine._get_api_key() is None

    def test_api_key_from_env(self, engine, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
        key = engine._get_api_key()
        assert key == "sk-test-123"

    @pytest.mark.asyncio
    async def test_send_message_no_key(self, engine):
        # Should return an error response, not crash
        response = await engine.send_message("Hello")
        assert "API key" in response.text

    def test_get_render_state(self, engine):
        engine.messages.append(Message(role=MessageRole.USER, text="Test"))
        state = engine.get_render_state()
        assert "messages" in state
        assert "tools_available" in state
        assert len(state["messages"]) == 1
