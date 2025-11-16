"""Scene that renders a notification-style feed of Home Assistant events."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterator, List

from PIL import ImageDraw, ImageFont

from ..core.renderer import blank
from ..core.scene import Frame, Scene


class ActivityLogScene(Scene):
    def __init__(
        self,
        log_path: Path | str = Path("data/events.json"),
        max_entries: int = 8,
        font_path: str | None = None,
        title: str = "Recent Activity",
    ) -> None:
        super().__init__(panel=None)
        self.log_path = Path(log_path)
        self.max_entries = max_entries
        self.font = ImageFont.truetype(font_path, 36) if font_path else ImageFont.load_default()
        self.small_font = ImageFont.truetype(font_path, 28) if font_path else ImageFont.load_default()
        self.title = title

    def frames(self) -> Iterator[Frame]:
        if self.panel is None:
            raise RuntimeError("Scene not bootstrapped with panel")

        events = self._load_events()
        canvas = blank((self.panel.width, self.panel.height))
        draw = ImageDraw.Draw(canvas)
        draw.text((40, 30), self.title, font=self.font, fill=0)
        y = 90
        card_height = 110
        gap = 10
        for event in events[: self.max_entries]:
            self._render_card(draw, event, y, card_height)
            y += card_height + gap
        yield canvas, {"hint": "full"}

    def _render_card(self, draw: ImageDraw.ImageDraw, event: Dict[str, str], top: int, height: int) -> None:
        left = 30
        right = self.panel.width - 30
        bottom = top + height
        draw.rectangle((left, top, right, bottom), fill=240, outline=200, width=2)
        icon_text = event.get("domain", "?").upper()[:2]
        draw.text((left + 12, top + 12), icon_text, font=self.small_font, fill=0)
        name = event.get("friendly_name") or event.get("entity_id", "unknown")
        summary = event.get("summary", "State change")
        timestamp = event.get("timestamp")
        actor = event.get("actor")
        time_str = self._format_time(timestamp)
        draw.text((left + 80, top + 8), name, font=self.font, fill=0)
        draw.text((left + 80, top + 52), summary, font=self.small_font, fill=0)
        meta = time_str
        if actor:
            meta += f" · {actor}"
        draw.text((right - 220, top + 8), meta, font=self.small_font, fill=0)

    def _load_events(self) -> List[Dict[str, str]]:
        if not self.log_path.exists():
            return []
        try:
            payload = json.loads(self.log_path.read_text(encoding="utf-8"))
            return payload.get("events", [])
        except Exception:
            return []

    @staticmethod
    def _format_time(timestamp: str | None) -> str:
        if not timestamp:
            return "--"
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            return dt.strftime("%H:%M")
        except ValueError:
            return timestamp
