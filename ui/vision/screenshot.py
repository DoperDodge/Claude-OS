"""
Claude-OS Screenshot & Screen Reader

Provides tools for Claude to see and understand the current display:
    - Screenshot capture: Reads the compositor's pixel buffer and encodes to PNG/base64
    - Screen text reader: Walks the widget tree to extract all visible text
    - Screen description: Generates a structural description of the current UI

These tools let Claude "see" the screen without needing OCR — the widget
tree already knows what text is being displayed and where.
"""

import base64
import struct
import time
import zlib
from dataclasses import dataclass, field


@dataclass
class ScreenRegion:
    """A rectangular region of the screen."""
    x: int
    y: int
    width: int
    height: int

    def contains(self, px: int, py: int) -> bool:
        return (self.x <= px < self.x + self.width and
                self.y <= py < self.y + self.height)

    def intersects(self, other: "ScreenRegion") -> bool:
        return not (self.x + self.width <= other.x or
                    other.x + other.width <= self.x or
                    self.y + self.height <= other.y or
                    other.y + other.height <= self.y)


@dataclass
class TextElement:
    """A piece of text found on screen with its location."""
    text: str
    x: int
    y: int
    width: int
    height: int
    widget_type: str = ""
    widget_id: str = ""

    @property
    def region(self) -> ScreenRegion:
        return ScreenRegion(self.x, self.y, self.width, self.height)


@dataclass
class ScreenDescription:
    """Structured description of the current screen state."""
    screen_name: str = ""
    width: int = 0
    height: int = 0
    text_elements: list[TextElement] = field(default_factory=list)
    visible_widgets: list[str] = field(default_factory=list)
    interactive_elements: list[dict] = field(default_factory=list)
    timestamp: float = 0.0

    def to_text(self) -> str:
        """Generate a human-readable description for Claude."""
        lines = [f"Screen: {self.screen_name} ({self.width}x{self.height})"]
        lines.append(f"Timestamp: {time.strftime('%H:%M:%S', time.localtime(self.timestamp))}")
        lines.append("")

        if self.text_elements:
            lines.append("Text on screen:")
            for te in self.text_elements:
                pos = f"  at ({te.x},{te.y})"
                wtype = f" [{te.widget_type}]" if te.widget_type else ""
                lines.append(f'  "{te.text}"{pos}{wtype}')
            lines.append("")

        if self.interactive_elements:
            lines.append("Interactive elements:")
            for ie in self.interactive_elements:
                lines.append(f"  - {ie.get('type', 'unknown')}: "
                           f"{ie.get('label', 'unlabeled')} "
                           f"at ({ie.get('x', 0)},{ie.get('y', 0)})")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "screen_name": self.screen_name,
            "width": self.width,
            "height": self.height,
            "text_elements": [
                {"text": t.text, "x": t.x, "y": t.y,
                 "width": t.width, "height": t.height,
                 "widget_type": t.widget_type}
                for t in self.text_elements
            ],
            "interactive_elements": self.interactive_elements,
            "timestamp": self.timestamp,
        }


class ScreenshotCapture:
    """
    Captures screenshots from the compositor's pixel buffer.

    Works with both the HeadlessDisplay (testing) and real display
    backends. Encodes raw BGRA pixels to PNG format for the vision API.
    """

    def __init__(self):
        self._last_capture: bytes | None = None
        self._last_capture_time: float = 0

    def capture_raw(self, buffer: bytearray, width: int, height: int,
                    region: ScreenRegion = None) -> bytearray:
        """
        Capture raw BGRA pixel data from the display buffer.

        Args:
            buffer: The compositor's BGRA pixel buffer
            width: Buffer width in pixels
            height: Buffer height in pixels
            region: Optional sub-region to capture (None = full screen)

        Returns:
            BGRA pixel data for the captured region.
        """
        if region is None:
            self._last_capture_time = time.time()
            return bytearray(buffer)

        # Extract sub-region
        rx, ry = max(0, region.x), max(0, region.y)
        rw = min(region.width, width - rx)
        rh = min(region.height, height - ry)

        if rw <= 0 or rh <= 0:
            return bytearray()

        result = bytearray(rw * rh * 4)
        src_stride = width * 4
        dst_stride = rw * 4

        for row in range(rh):
            src_off = (ry + row) * src_stride + rx * 4
            dst_off = row * dst_stride
            result[dst_off:dst_off + dst_stride] = \
                buffer[src_off:src_off + dst_stride]

        self._last_capture_time = time.time()
        return result

    def encode_png(self, bgra_data: bytearray, width: int, height: int) -> bytes:
        """
        Encode BGRA pixel data as a minimal PNG.

        Creates a valid PNG with IHDR, IDAT (zlib-compressed), IEND chunks.
        Converts BGRA → RGBA during encoding.
        """
        if not bgra_data or width <= 0 or height <= 0:
            return b""

        # Build raw image data (filter byte + RGBA pixels per row)
        raw_data = bytearray()
        for y in range(height):
            raw_data.append(0)  # Filter: None
            for x in range(width):
                off = (y * width + x) * 4
                if off + 3 < len(bgra_data):
                    b = bgra_data[off]
                    g = bgra_data[off + 1]
                    r = bgra_data[off + 2]
                    a = bgra_data[off + 3]
                    raw_data.extend([r, g, b, a])
                else:
                    raw_data.extend([0, 0, 0, 255])

        # Compress
        compressed = zlib.compress(bytes(raw_data), 6)

        # Build PNG
        png = bytearray()

        # Signature
        png.extend(b'\x89PNG\r\n\x1a\n')

        # IHDR
        ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
        png.extend(self._png_chunk(b"IHDR", ihdr_data))

        # IDAT
        png.extend(self._png_chunk(b"IDAT", compressed))

        # IEND
        png.extend(self._png_chunk(b"IEND", b""))

        return bytes(png)

    def capture_png(self, buffer: bytearray, width: int, height: int,
                    region: ScreenRegion = None) -> bytes:
        """Capture and encode as PNG in one step."""
        if region:
            raw = self.capture_raw(buffer, width, height, region)
            rw = min(region.width, width - max(0, region.x))
            rh = min(region.height, height - max(0, region.y))
            return self.encode_png(raw, rw, rh)
        else:
            raw = self.capture_raw(buffer, width, height)
            return self.encode_png(raw, width, height)

    def capture_base64(self, buffer: bytearray, width: int, height: int,
                       region: ScreenRegion = None) -> str:
        """Capture and encode as base64 PNG string (for Claude vision API)."""
        png = self.capture_png(buffer, width, height, region)
        self._last_capture = png
        return base64.b64encode(png).decode('ascii')

    @staticmethod
    def _png_chunk(chunk_type: bytes, data: bytes) -> bytearray:
        """Create a PNG chunk with CRC."""
        chunk = bytearray()
        chunk.extend(struct.pack(">I", len(data)))
        chunk.extend(chunk_type)
        chunk.extend(data)
        crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
        chunk.extend(struct.pack(">I", crc))
        return chunk

    @property
    def last_capture_time(self) -> float:
        return self._last_capture_time


class ScreenReader:
    """
    Extracts text and structure from the widget tree.

    Instead of OCR, we walk the live widget tree and extract text
    directly from Label, Button, TextInput, etc. widgets. This is
    100% accurate since we know exactly what's being rendered.
    """

    def read_screen(self, root_widget, screen_name: str = "",
                    screen_width: int = 360, screen_height: int = 720) -> ScreenDescription:
        """
        Walk the widget tree and extract all visible text and interactive elements.

        Args:
            root_widget: The root of the widget tree to scan
            screen_name: Name of the current screen (e.g., "home", "settings")
            screen_width: Display width
            screen_height: Display height

        Returns:
            ScreenDescription with all found text and interactive elements.
        """
        desc = ScreenDescription(
            screen_name=screen_name,
            width=screen_width,
            height=screen_height,
            timestamp=time.time(),
        )

        if root_widget is None:
            return desc

        self._walk_widget(root_widget, desc, 0, 0)
        return desc

    def _walk_widget(self, widget, desc: ScreenDescription,
                     offset_x: int, offset_y: int):
        """Recursively walk the widget tree."""
        if not widget.visible:
            return

        abs_x = offset_x + widget.x
        abs_y = offset_y + widget.y
        widget_type = type(widget).__name__
        desc.visible_widgets.append(widget_type)

        # Extract text from known widget types
        text = self._extract_text(widget)
        if text:
            desc.text_elements.append(TextElement(
                text=text,
                x=abs_x,
                y=abs_y,
                width=widget.width,
                height=widget.height,
                widget_type=widget_type,
            ))

        # Detect interactive elements
        if self._is_interactive(widget):
            desc.interactive_elements.append({
                "type": widget_type.lower(),
                "label": text or "",
                "x": abs_x,
                "y": abs_y,
                "width": widget.width,
                "height": widget.height,
            })

        # Recurse into children
        for child in widget.children:
            self._walk_widget(child, desc, abs_x, abs_y)

    @staticmethod
    def _extract_text(widget) -> str:
        """Extract text content from a widget."""
        # Label
        if hasattr(widget, 'text') and isinstance(getattr(widget, 'text', None), str):
            text = widget.text.strip()
            if text:
                return text
        # TextInput placeholder
        if hasattr(widget, 'placeholder') and not getattr(widget, 'text', ''):
            return getattr(widget, 'placeholder', '')
        return ""

    @staticmethod
    def _is_interactive(widget) -> bool:
        """Check if a widget is interactive (tappable/editable)."""
        if hasattr(widget, '_on_tap') and widget._on_tap is not None:
            return True
        if type(widget).__name__ in ("Button", "TextInput", "ScrollView"):
            return True
        return False

    def find_text(self, root_widget, query: str,
                  case_sensitive: bool = False) -> list[TextElement]:
        """Find all text elements matching a query string."""
        desc = self.read_screen(root_widget)
        results = []
        for te in desc.text_elements:
            text = te.text if case_sensitive else te.text.lower()
            q = query if case_sensitive else query.lower()
            if q in text:
                results.append(te)
        return results

    def get_element_at(self, root_widget, x: int, y: int) -> TextElement | None:
        """Find the text element at a specific screen position."""
        desc = self.read_screen(root_widget)
        for te in reversed(desc.text_elements):  # Top-most first
            if te.region.contains(x, y):
                return te
        return None
