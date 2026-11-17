"""Shared font loader (bold cartoon-friendly fonts on Windows)."""
import os
from functools import lru_cache

from PIL import ImageFont

_CANDIDATES = [
    "C:/Windows/Fonts/ariblk.ttf",   # Arial Black
    "C:/Windows/Fonts/impact.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
]


def font_path() -> str | None:
    return next((p for p in _CANDIDATES if os.path.exists(p)), None)


@lru_cache(maxsize=64)
def get_font(size: int):
    p = font_path()
    return ImageFont.truetype(p, size) if p else ImageFont.load_default()
