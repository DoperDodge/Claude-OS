"""
Layout widgets: VStack, HStack, Spacer, Padding.

These control how child widgets are arranged and sized.
"""

from __future__ import annotations

from ui.widgets.base import Widget, Container, Size, TouchEvent


class VStack(Container):
    """
    Vertical stack layout — arranges children top to bottom.

    Children are measured and laid out sequentially. Each child
    gets the full available width and its measured height.
    A `spacing` gap is added between children.
    """

    def __init__(self, spacing: int = 0, background: str | None = None,
                 corner_radius: int = 0, padding: int = 0,
                 align: str = "stretch"):
        super().__init__(background=background, corner_radius=corner_radius,
                        padding=padding)
        self.spacing_gap = spacing
        self.align = align  # "stretch", "center", "left", "right"

    def measure(self, max_width: int, max_height: int) -> Size:
        """Measure total height of stacked children."""
        p = self.padding
        avail_w = max_width - 2 * p
        total_h = 0
        max_child_w = 0
        spacer_count = 0

        for i, child in enumerate(self.children):
            if isinstance(child, Spacer):
                spacer_count += 1
                continue
            child_size = child.measure(avail_w, max_height - total_h)
            total_h += child_size.height
            max_child_w = max(max_child_w, child_size.width)
            if i < len(self.children) - 1:
                total_h += self.spacing_gap

        total_h += 2 * p
        return Size(max_width, min(total_h, max_height) if spacer_count == 0 else max_height)

    def layout(self, x: int, y: int, width: int, height: int):
        """Position children vertically."""
        self.bounds.x = x
        self.bounds.y = y
        self.bounds.width = width
        self.bounds.height = height

        p = self.padding
        avail_w = width - 2 * p
        avail_h = height - 2 * p

        # First pass: measure non-spacer children and count spacers
        child_sizes = []
        total_fixed = 0
        spacer_count = 0

        for i, child in enumerate(self.children):
            if isinstance(child, Spacer):
                child_sizes.append(None)
                spacer_count += 1
            else:
                size = child.measure(avail_w, avail_h)
                child_sizes.append(size)
                total_fixed += size.height

        total_gaps = max(0, len(self.children) - 1) * self.spacing_gap
        remaining = avail_h - total_fixed - total_gaps
        spacer_h = max(0, remaining // spacer_count) if spacer_count > 0 else 0

        # Second pass: layout
        cur_y = y + p
        for i, child in enumerate(self.children):
            if isinstance(child, Spacer):
                child.layout(x + p, cur_y, avail_w, spacer_h)
                cur_y += spacer_h
            else:
                size = child_sizes[i]
                child_w = avail_w if self.align == "stretch" else size.width

                if self.align == "center":
                    child_x = x + p + (avail_w - child_w) // 2
                elif self.align == "right":
                    child_x = x + p + avail_w - child_w
                else:
                    child_x = x + p

                child.layout(child_x, cur_y, child_w, size.height)
                cur_y += size.height

            if i < len(self.children) - 1:
                cur_y += self.spacing_gap


class HStack(Container):
    """
    Horizontal stack layout — arranges children left to right.

    Similar to VStack but horizontal. Children get the full
    available height and their measured width.
    """

    def __init__(self, spacing: int = 0, background: str | None = None,
                 corner_radius: int = 0, padding: int = 0,
                 align: str = "stretch"):
        super().__init__(background=background, corner_radius=corner_radius,
                        padding=padding)
        self.spacing_gap = spacing
        self.align = align  # "stretch", "center", "top", "bottom"

    def measure(self, max_width: int, max_height: int) -> Size:
        """Measure total width of stacked children."""
        p = self.padding
        avail_h = max_height - 2 * p
        total_w = 0
        max_child_h = 0
        spacer_count = 0

        for i, child in enumerate(self.children):
            if isinstance(child, Spacer):
                spacer_count += 1
                continue
            child_size = child.measure(max_width - total_w, avail_h)
            total_w += child_size.width
            max_child_h = max(max_child_h, child_size.height)
            if i < len(self.children) - 1:
                total_w += self.spacing_gap

        total_w += 2 * p
        return Size(
            min(total_w, max_width) if spacer_count == 0 else max_width,
            max_child_h + 2 * p
        )

    def layout(self, x: int, y: int, width: int, height: int):
        """Position children horizontally."""
        self.bounds.x = x
        self.bounds.y = y
        self.bounds.width = width
        self.bounds.height = height

        p = self.padding
        avail_w = width - 2 * p
        avail_h = height - 2 * p

        # First pass: measure non-spacer children
        child_sizes = []
        total_fixed = 0
        spacer_count = 0

        for i, child in enumerate(self.children):
            if isinstance(child, Spacer):
                child_sizes.append(None)
                spacer_count += 1
            else:
                size = child.measure(avail_w, avail_h)
                child_sizes.append(size)
                total_fixed += size.width

        total_gaps = max(0, len(self.children) - 1) * self.spacing_gap
        remaining = avail_w - total_fixed - total_gaps
        spacer_w = max(0, remaining // spacer_count) if spacer_count > 0 else 0

        # Second pass: layout
        cur_x = x + p
        for i, child in enumerate(self.children):
            if isinstance(child, Spacer):
                child.layout(cur_x, y + p, spacer_w, avail_h)
                cur_x += spacer_w
            else:
                size = child_sizes[i]
                child_h = avail_h if self.align == "stretch" else size.height

                if self.align == "center":
                    child_y = y + p + (avail_h - child_h) // 2
                elif self.align == "bottom":
                    child_y = y + p + avail_h - child_h
                else:
                    child_y = y + p

                child.layout(cur_x, child_y, size.width, child_h)
                cur_x += size.width

            if i < len(self.children) - 1:
                cur_x += self.spacing_gap


class Spacer(Widget):
    """
    Flexible space that expands to fill available room.

    Used in VStack/HStack to push content apart.
    """

    def __init__(self, min_size: int = 0):
        super().__init__()
        self.min_size = min_size

    def measure(self, max_width: int, max_height: int) -> Size:
        return Size(self.min_size, self.min_size)

    def render(self, ctx):
        pass  # Invisible


class Padding(Container):
    """
    Wraps a single child with padding on all sides.

    Convenience wrapper around Container with padding.
    """

    def __init__(self, child: Widget | None = None,
                 top: int = 0, right: int = 0,
                 bottom: int = 0, left: int = 0,
                 all: int = 0):
        super().__init__()
        self.pad_top = top or all
        self.pad_right = right or all
        self.pad_bottom = bottom or all
        self.pad_left = left or all
        if child:
            self.add(child)

    def measure(self, max_width: int, max_height: int) -> Size:
        avail_w = max_width - self.pad_left - self.pad_right
        avail_h = max_height - self.pad_top - self.pad_bottom
        if self.children:
            child_size = self.children[0].measure(avail_w, avail_h)
            return Size(
                child_size.width + self.pad_left + self.pad_right,
                child_size.height + self.pad_top + self.pad_bottom,
            )
        return Size(self.pad_left + self.pad_right, self.pad_top + self.pad_bottom)

    def layout(self, x: int, y: int, width: int, height: int):
        self.bounds = Size(width, height)
        self.bounds.x = x
        self.bounds.y = y
        self.bounds.width = width
        self.bounds.height = height
        if self.children:
            self.children[0].layout(
                x + self.pad_left,
                y + self.pad_top,
                width - self.pad_left - self.pad_right,
                height - self.pad_top - self.pad_bottom,
            )
