"""Rendering helpers built on Pillow."""
from __future__ import annotations

from typing import Tuple

from PIL import Image, ImageDraw, ImageFont


def blank(size: Tuple[int, int], gray: int = 255) -> Image.Image:
    return Image.new("L", size, color=gray)


def draw_center_text(
    image: Image.Image,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    y_offset: int = 0,
) -> Image.Image:
    draw = ImageDraw.Draw(image)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    canvas_w, canvas_h = image.size
    x = (canvas_w - text_w) // 2
    y = (canvas_h - text_h) // 2 + y_offset
    draw.text((x, y), text, font=font, fill=0)
    return image


def wipe_mask(size: Tuple[int, int], progress: float) -> Image.Image:
    width, height = size
    mask = Image.new("L", size, color=0)
    draw = ImageDraw.Draw(mask)
    x = int(max(0.0, min(1.0, progress)) * width)
    draw.rectangle((0, 0, x, height), fill=255)
    return mask
