"""
Claude Chat Engine

Manages the conversation with the Claude API, including:
- Message history and context management
- Tool use (system tools Claude can invoke mid-conversation)
- Streaming responses
- Conversation persistence across sessions

The chat engine is the core intelligence layer — every user interaction
(typed, voice, or gesture) ultimately flows through here.
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Callable

logger = logging.getLogger("chat")

CONVERSATIONS_DIR = Path(
    os.environ.get("CLAUDE_OS_DATA", "/var/lib/claude-os")
) / "conversations"

API_KEY_PATH = Path(
    os.environ.get("CLAUDE_OS_CONFIG", "/etc/claude-os")
) / "api_key"


class MessageRole(Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL_RESULT = "tool_result"


@dataclass
class Message:
    """A single message in the conversation."""
    role: MessageRole
    text: str
    timestamp: float = field(default_factory=time.time)
    source: str = "keyboard"  # "keyboard", "voice", "system"
    tool_calls: list[dict] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)

    def to_api_format(self) -> dict:
        """Convert to Claude API message format."""
        content = self.text
        if self.tool_calls:
            content = [{"type": "text", "text": self.text}]
            for tc in self.tool_calls:
                content.append({
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["name"],
                    "input": tc["input"],
                })
        return {"role": self.role.value, "content": content}


@dataclass
class ChatResponse:
    """Response from the chat engine."""
    text: str
    tool_calls: list[dict] = field(default_factory=list)
    finish_reason: str = "end_turn"


@dataclass
class RegisteredTool:
    """A system tool that Claude can invoke."""
    name: str
    handler: Callable
    description: str
    parameters: dict = field(default_factory=dict)


class ChatEngine:
    """
    Core chat engine connecting the user to Claude.

    Manages conversation state, tool use, and API communication.
    """

    # System prompt that gives Claude context about being an OS
    SYSTEM_PROMPT = """You are Claude, running as the primary interface of Claude-OS — \
a mobile operating system built around you. You ARE the OS.

You have direct access to system tools that let you control the device:
- WiFi: scan, connect, disconnect, check status
- Battery: check level and charging state
- Display: adjust brightness
- Audio: adjust volume
- System: get device info

When users ask you to do something on their phone, USE the available tools \
to actually do it. Don't just describe what they should do — do it for them.

Keep responses concise and mobile-friendly. You're on a phone screen, \
not a desktop monitor. Short paragraphs, clear actions.

If a tool call fails due to permissions, let the user know they need to \
grant the permission in settings."""

    MAX_HISTORY = 50  # Max messages to keep in context

    def __init__(self):
        self.messages: list[Message] = []
        self.tools: dict[str, RegisteredTool] = {}
        self._tool_manager = None
        self._api_key: str | None = None
        self._conversation_id: str | None = None

    def set_tool_manager(self, manager):
        """Set the system tool manager."""
        self._tool_manager = manager

    def register_tool(self, name: str, handler: Callable,
                      description: str, parameters: dict = None):
        """Register a system tool that Claude can use."""
        self.tools[name] = RegisteredTool(
            name=name,
            handler=handler,
            description=description,
            parameters=parameters or {},
        )
        logger.info("Registered tool: %s", name)

    async def send_message(self, text: str,
                           source: str = "keyboard") -> ChatResponse:
        """
        Send a user message and get Claude's response.

        This is the main entry point for all user interactions.
        Handles the full tool-use loop: send message → Claude responds
        with tool calls → execute tools → send results → get final response.
        """
        # Add user message to history
        user_msg = Message(
            role=MessageRole.USER,
            text=text,
            source=source,
        )
        self.messages.append(user_msg)

        # Build API request
        api_messages = self._build_api_messages()
        tools_spec = self._build_tools_spec()

        # Call Claude API
        response = await self._call_api(api_messages, tools_spec)

        # Handle tool use loop
        while response.tool_calls:
            # Execute each tool call
            tool_results = []
            for tool_call in response.tool_calls:
                result = await self._execute_tool(tool_call)
                tool_results.append(result)

            # Add assistant message with tool calls
            assistant_msg = Message(
                role=MessageRole.ASSISTANT,
                text=response.text,
                tool_calls=response.tool_calls,
            )
            self.messages.append(assistant_msg)

            # Add tool results
            result_msg = Message(
                role=MessageRole.TOOL_RESULT,
                text="",
                tool_results=tool_results,
            )
            self.messages.append(result_msg)

            # Call API again with tool results
            api_messages = self._build_api_messages()
            response = await self._call_api(api_messages, tools_spec)

        # Add final assistant response
        assistant_msg = Message(
            role=MessageRole.ASSISTANT,
            text=response.text,
        )
        self.messages.append(assistant_msg)

        # Trim history if needed
        self._trim_history()

        # Persist conversation
        self._save_conversation()

        return response

    async def _call_api(self, messages: list[dict],
                        tools: list[dict] = None) -> ChatResponse:
        """
        Call the Claude API.

        Uses the Anthropic Python SDK if available, falls back to
        raw HTTP requests via urllib.
        """
        api_key = self._get_api_key()
        if not api_key:
            return ChatResponse(
                text="I need an API key to respond. Please add your "
                     "Anthropic API key to /etc/claude-os/api_key",
                finish_reason="error",
            )

        try:
            return await self._call_api_sdk(api_key, messages, tools)
        except ImportError:
            return await self._call_api_http(api_key, messages, tools)
        except Exception as e:
            logger.error("API call failed: %s", e)
            return ChatResponse(
                text=f"Sorry, I couldn't reach the Claude API: {e}",
                finish_reason="error",
            )

    async def _call_api_sdk(self, api_key: str, messages: list[dict],
                            tools: list[dict] = None) -> ChatResponse:
        """Call API using the Anthropic Python SDK."""
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=api_key)

        kwargs = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1024,
            "system": self.SYSTEM_PROMPT,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools

        response = await client.messages.create(**kwargs)

        # Parse response
        text_parts = []
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })

        return ChatResponse(
            text="\n".join(text_parts),
            tool_calls=tool_calls,
            finish_reason=response.stop_reason,
        )

    async def _call_api_http(self, api_key: str, messages: list[dict],
                             tools: list[dict] = None) -> ChatResponse:
        """Call API using raw HTTP (fallback when SDK not installed)."""
        import urllib.request
        import urllib.error

        body = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1024,
            "system": self.SYSTEM_PROMPT,
            "messages": messages,
        }
        if tools:
            body["tools"] = tools

        payload = json.dumps(body).encode()

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
        )

        def do_request():
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode())

        data = await asyncio.to_thread(do_request)

        text_parts = []
        tool_calls = []
        for block in data.get("content", []):
            if block.get("type") == "text":
                text_parts.append(block["text"])
            elif block.get("type") == "tool_use":
                tool_calls.append({
                    "id": block["id"],
                    "name": block["name"],
                    "input": block.get("input", {}),
                })

        return ChatResponse(
            text="\n".join(text_parts),
            tool_calls=tool_calls,
            finish_reason=data.get("stop_reason", "end_turn"),
        )

    async def _execute_tool(self, tool_call: dict) -> dict:
        """Execute a tool call and return the result."""
        name = tool_call["name"]
        inputs = tool_call.get("input", {})
        tool_id = tool_call["id"]

        tool = self.tools.get(name)
        if not tool:
            return {
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": json.dumps({"error": f"Unknown tool: {name}"}),
            }

        try:
            logger.info("Executing tool: %s(%s)", name, inputs)
            result = await tool.handler(**inputs)
            return {
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": json.dumps(result) if isinstance(result, dict) else str(result),
            }
        except Exception as e:
            logger.error("Tool %s failed: %s", name, e)
            return {
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": json.dumps({"error": str(e)}),
                "is_error": True,
            }

    def _build_api_messages(self) -> list[dict]:
        """Build the messages array for the API call."""
        api_messages = []
        for msg in self.messages:
            if msg.role == MessageRole.TOOL_RESULT:
                # Tool results go as user messages with tool_result content
                api_messages.append({
                    "role": "user",
                    "content": msg.tool_results,
                })
            else:
                api_messages.append(msg.to_api_format())
        return api_messages

    def _build_tools_spec(self) -> list[dict]:
        """Build the tools specification for the API."""
        if not self.tools:
            return []

        specs = []
        for tool in self.tools.values():
            spec = {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.parameters or {
                    "type": "object",
                    "properties": {},
                },
            }
            specs.append(spec)
        return specs

    def _get_api_key(self) -> str | None:
        """Read the API key from config."""
        if self._api_key:
            return self._api_key

        # Try environment variable first
        key = os.environ.get("ANTHROPIC_API_KEY")
        if key:
            self._api_key = key.strip()
            return self._api_key

        # Try config file
        if API_KEY_PATH.exists():
            try:
                self._api_key = API_KEY_PATH.read_text().strip()
                return self._api_key
            except OSError:
                pass

        return None

    def _trim_history(self):
        """Keep conversation history within limits."""
        if len(self.messages) > self.MAX_HISTORY:
            # Keep system-relevant messages and trim oldest
            self.messages = self.messages[-self.MAX_HISTORY:]

    def _save_conversation(self):
        """Persist conversation to disk."""
        try:
            CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)
            if not self._conversation_id:
                self._conversation_id = str(int(time.time()))

            path = CONVERSATIONS_DIR / f"{self._conversation_id}.json"
            data = {
                "id": self._conversation_id,
                "messages": [
                    {
                        "role": msg.role.value,
                        "text": msg.text,
                        "timestamp": msg.timestamp,
                        "source": msg.source,
                    }
                    for msg in self.messages
                ],
            }
            path.write_text(json.dumps(data, indent=2))
        except OSError as e:
            logger.warning("Could not save conversation: %s", e)

    def get_render_state(self) -> dict:
        """Return current chat state for UI rendering."""
        return {
            "messages": [
                {
                    "role": msg.role.value,
                    "text": msg.text,
                    "source": msg.source,
                    "timestamp": msg.timestamp,
                }
                for msg in self.messages[-20:]  # Last 20 for display
            ],
            "tools_available": list(self.tools.keys()),
        }

    def clear_history(self):
        """Clear conversation history."""
        self.messages.clear()
        self._conversation_id = None
        logger.info("Conversation cleared")
