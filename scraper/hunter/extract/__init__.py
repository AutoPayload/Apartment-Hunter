from __future__ import annotations

from ..config import Settings
from .base import Extractor
from .keywords import KeywordExtractor


def build_extractor(settings: Settings) -> Extractor:
    """Jev when TYPESAFE_API_KEY is set, keyword rules otherwise."""
    if settings.typesafe_api_key:
        from .jev import JevExtractor

        return JevExtractor(settings.typesafe_api_key, settings.jev_min_confidence)
    return KeywordExtractor()


__all__ = ["Extractor", "KeywordExtractor", "build_extractor"]
