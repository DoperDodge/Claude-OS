"""
Claude-OS Terminal Emulator

A built-in terminal for power users. Renders a scrollable text buffer
with command input.

Layout:
    ┌──────────────────────────────┐
    │  Terminal                    │
    ├──────────────────────────────┤
    │  claude-os:~$ ls             │
    │  Documents  Downloads        │
    │  claude-os:~$ uname -a       │
    │  Linux claude-os 6.6.20      │
    │  claude-os:~$ _              │
    │                              │
    └──────────────────────────────┘
"""

import os
import subprocess
from dataclasses import dataclass
from typing import Callable

from theme import Colors, Typography, Spacing, Color
from widget import Widget, Size, EdgeInsets, Align, Direction, Event, EventType
from widgets import Container, Label, ScrollView


@dataclass
class TerminalLine:
    """A line in the terminal buffer."""
    text: str
    is_input: bool = False
    color: Color = None

    def __post_init__(self):
        if not self.color:
            self.color = Colors.TEXT_PRIMARY if self.is_input else Colors.TEXT_SECONDARY


class TerminalApp(Widget):
    """
    Terminal emulator application.

    Maintains a scrollback buffer, accepts command input, and can
    optionally execute commands (disabled by default for safety).
    """

    MAX_SCROLLBACK = 500
    PROMPT = "claude-os:~$ "

    def __init__(self, allow_exec: bool = False,
                 on_command: Callable = None):
        super().__init__()
        self.background = Color(0, 0, 0)
        self._lines: list[TerminalLine] = []
        self._input_text = ""
        self._cursor_pos = 0
        self._allow_exec = allow_exec
        self._on_command = on_command
        self._cwd = os.environ.get("HOME", "/")
        self._history: list[str] = []
        self._history_pos = -1

        # Welcome message
        self._add_output("Claude-OS Terminal v0.1")
        self._add_output("Type 'help' for available commands.")
        self._add_output("")

        self._build_ui()

    def _build_ui(self):
        self.clear_children()

        root = Container(direction=Direction.VERTICAL)
        self.add_child(root)

        # Title bar
        title_bar = Container(direction=Direction.HORIZONTAL,
                              cross_align=Align.CENTER)
        title_bar.min_height = 36
        title_bar.background = Color(20, 20, 30)
        title_bar.padding = EdgeInsets.symmetric(horizontal=Spacing.SM)
        title_bar.add_child(Label(
            "Terminal",
            style=Typography.LABEL_LARGE,
            color=Colors.TEXT_PRIMARY,
        ))
        root.add_child(title_bar)

        # Scrollable output
        self._scroll = ScrollView()
        self._scroll.flex = 1
        self._scroll.background = Color(0, 0, 0)
        root.add_child(self._scroll)

        output = Container(direction=Direction.VERTICAL)
        output.padding = EdgeInsets.all(Spacing.XS)
        self._scroll.add_child(output)

        # Render lines
        for line in self._lines:
            lbl = Label(
                line.text,
                style=Typography.BODY_SMALL,
                color=line.color,
            )
            output.add_child(lbl)

        # Current input line
        prompt_text = self.PROMPT + self._input_text + "_"
        input_lbl = Label(
            prompt_text,
            style=Typography.BODY_SMALL,
            color=Color(0, 255, 0),  # Green terminal text
        )
        output.add_child(input_lbl)

    def _add_output(self, text: str, color: Color = None):
        """Add a line to the output buffer."""
        self._lines.append(TerminalLine(text=text, color=color))
        if len(self._lines) > self.MAX_SCROLLBACK:
            self._lines = self._lines[-self.MAX_SCROLLBACK:]

    def _execute_command(self, cmd: str):
        """Execute a command and capture output."""
        # Add input line to buffer
        self._lines.append(TerminalLine(
            text=self.PROMPT + cmd,
            is_input=True,
            color=Color(0, 255, 0),
        ))

        cmd = cmd.strip()
        if not cmd:
            return

        # History
        self._history.append(cmd)
        self._history_pos = -1

        # Built-in commands
        if cmd == "help":
            self._add_output("Built-in commands:")
            self._add_output("  help    - Show this help")
            self._add_output("  clear   - Clear screen")
            self._add_output("  pwd     - Print working directory")
            self._add_output("  cd DIR  - Change directory")
            self._add_output("  exit    - Close terminal")
        elif cmd == "clear":
            self._lines.clear()
        elif cmd == "pwd":
            self._add_output(self._cwd)
        elif cmd.startswith("cd "):
            target = cmd[3:].strip()
            new_path = os.path.normpath(os.path.join(self._cwd, target))
            if os.path.isdir(new_path):
                self._cwd = new_path
            else:
                self._add_output(f"cd: no such directory: {target}",
                                 color=Colors.ERROR)
        elif cmd == "exit":
            self._add_output("Use the app switcher to close.")
        elif self._allow_exec:
            self._run_external(cmd)
        elif self._on_command:
            result = self._on_command(cmd)
            if result:
                self._add_output(result)
        else:
            self._add_output(f"Command not found: {cmd.split()[0]}",
                             color=Colors.ERROR)

    def _run_external(self, cmd: str):
        """Run an external command (only if allow_exec is True)."""
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=10, cwd=self._cwd,
            )
            if result.stdout:
                for line in result.stdout.rstrip().split('\n'):
                    self._add_output(line)
            if result.stderr:
                for line in result.stderr.rstrip().split('\n'):
                    self._add_output(line, color=Colors.ERROR)
        except subprocess.TimeoutExpired:
            self._add_output("Command timed out (10s limit)", color=Colors.WARNING)
        except Exception as e:
            self._add_output(f"Error: {e}", color=Colors.ERROR)

    # --- Public API ---

    def type_char(self, ch: str):
        """Type a character into the terminal."""
        if ch == "BACKSPACE":
            if self._input_text:
                self._input_text = self._input_text[:-1]
        elif ch == "\n" or ch == "ENTER":
            self.submit()
        else:
            self._input_text += ch
        self._build_ui()
        self.mark_dirty()

    def submit(self):
        """Submit the current input."""
        cmd = self._input_text
        self._input_text = ""
        self._execute_command(cmd)
        self._build_ui()
        self.mark_dirty()

    def write(self, text: str, color: Color = None):
        """Write text to the terminal output."""
        for line in text.split('\n'):
            self._add_output(line, color=color)
        self._build_ui()
        self.mark_dirty()

    def clear(self):
        """Clear the terminal."""
        self._lines.clear()
        self._build_ui()
        self.mark_dirty()

    @property
    def line_count(self) -> int:
        return len(self._lines)

    @property
    def input_text(self) -> str:
        return self._input_text

    @property
    def command_history(self) -> list[str]:
        return list(self._history)
