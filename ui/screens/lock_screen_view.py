"""
Lock screen view — clock, date, notifications, swipe-to-unlock.
"""

import time

from ui.widgets.base import Container, Size
from ui.widgets.text import Label
from ui.widgets.layout import VStack, HStack, Spacer


class LockScreenView(Container):
    """
    Full-screen lock screen with clock, date, notification previews,
    and a swipe-up-to-unlock hint.
    """

    def __init__(self, width: int, height: int):
        super().__init__()
        self._screen_w = width
        self._screen_h = height
        self.swipe_progress = 0.0
        self.notifications = []  # list of dicts: {app_name, title, body}

        self._clock_label = None
        self._date_label = None
        self._hint_label = None
        self._notif_container = None

        self._build()

    def _build(self):
        theme = self.theme
        colors = theme.colors if theme else None
        typo = theme.typography if theme else None

        # Background gradient (navy → dark)
        bg = colors.navy if colors else "#1A1A2E"
        root = VStack(background=bg)

        # Top spacer
        root.add(Spacer(min_size=self._screen_h // 5))

        # Clock
        self._clock_label = Label(
            text=time.strftime("%H:%M"),
            font_size=typo.display_large_size if typo else 72.0,
            weight="bold",
            color="#FFFFFF",
            align="center",
        )
        root.add(self._clock_label)

        # Date
        self._date_label = Label(
            text=time.strftime("%A, %B %d"),
            font_size=typo.title_medium_size if typo else 20.0,
            color=colors.text_secondary if colors else "#B8B8CC",
            align="center",
        )
        root.add(self._date_label)

        root.add(Spacer(min_size=40))

        # Notification previews
        self._notif_container = VStack(spacing=8, padding=16)
        root.add(self._notif_container)

        root.add(Spacer())

        # Swipe up hint
        self._hint_label = Label(
            text="Swipe up to unlock",
            font_size=14.0,
            color=colors.text_tertiary if colors else "#7A7A8E",
            align="center",
        )
        root.add(self._hint_label)

        # Home indicator area
        root.add(Spacer(min_size=50))

        self.add(root)

    def update(self):
        """Update clock and apply swipe progress."""
        if self._clock_label:
            self._clock_label.text = time.strftime("%H:%M")
            self._clock_label.opacity = max(0.0, 1.0 - self.swipe_progress * 2)
        if self._date_label:
            self._date_label.text = time.strftime("%A, %B %d")
            self._date_label.opacity = max(0.0, 1.0 - self.swipe_progress * 2)
        if self._hint_label:
            # Pulsing effect approximation
            pulse = abs((time.monotonic() % 2.0) - 1.0)
            self._hint_label.opacity = 0.4 + 0.3 * pulse

        # Update notifications
        self._rebuild_notifications()

    def _rebuild_notifications(self):
        if not self._notif_container:
            return
        self._notif_container.children.clear()
        theme = self.theme
        colors = theme.colors if theme else None
        spacing = theme.spacing if theme else None

        for notif in self.notifications[:4]:
            card = HStack(
                spacing=8,
                background="rgba(255, 255, 255, 0.1)",
                corner_radius=spacing.notification_radius if spacing else 16,
                padding=12,
            )
            card.add(Label(
                text=notif.get("app_name", "App"),
                font_size=13.0,
                weight="bold",
                color="#FFFFFF",
            ))
            card.add(Label(
                text=notif.get("title", ""),
                font_size=13.0,
                color="rgba(255, 255, 255, 0.7)",
            ))
            self._notif_container.add(card)

    def measure(self, max_width, max_height):
        return Size(self._screen_w, self._screen_h)

    def layout(self, x, y, width, height):
        super().layout(x, y, width, height)
        if self.children:
            self.children[0].layout(x, y, width, height)
