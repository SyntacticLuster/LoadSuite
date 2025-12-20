from __future__ import annotations

import asyncio
import logging
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Iterable, List

logger = logging.getLogger(__name__)

_FEEDS: list[tuple[str, str]] = [
    ("Trucking Info", "https://www.truckinginfo.com/rss"),
    ("FreightWaves", "https://www.freightwaves.com/feed"),
]
_CACHE_TTL = timedelta(minutes=5)
_MAX_ITEMS = 32

_cache_lock = asyncio.Lock()
_cache_state = {
    "items": [],
    "expires_at": datetime(1970, 1, 1, tzinfo=timezone.utc),
}


@dataclass
class NewsItem:
    title: str
    link: str
    source: str
    published: datetime | None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "title": self.title,
            "link": self.link,
            "source": self.source,
            "published": self.published.isoformat() if self.published else None,
        }


def _safe_text(element: ET.Element | None) -> str | None:
    if element is None or not element.text:
        return None
    return element.text.strip()


def _parse_pub_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:  # pragma: no cover - defensive
        logger.debug("Unable to parse pubDate %r", value)
        return None


def _fetch_feed(url: str, source: str) -> list[NewsItem]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "LoadSuite News Ticker/1.0",
            "Accept": "application/rss+xml, application/xml, text/xml",
        },
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        payload = response.read()

    root = ET.fromstring(payload)
    channel = root.find("channel") or root
    items: list[NewsItem] = []
    for element in channel.findall("item"):
        title = _safe_text(element.find("title"))
        link = _safe_text(element.find("link"))
        if not title or not link:
            continue
        published = _parse_pub_date(_safe_text(element.find("pubDate")))
        items.append(NewsItem(title=title, link=link, source=source, published=published))
        if len(items) >= _MAX_ITEMS:
            break
    return items


def _gather_news() -> list[NewsItem]:
    entries: list[NewsItem] = []
    for source, url in _FEEDS:
        try:
            entries.extend(_fetch_feed(url, source))
        except Exception:
            logger.exception("Failed to refresh news feed %s", source)
    entries.sort(key=lambda item: item.published or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return entries


async def get_news_items(limit: int = 20) -> list[NewsItem]:
    limit = max(1, min(limit, 50))
    now = datetime.now(timezone.utc)
    if _cache_state["items"] and _cache_state["expires_at"] > now:
        return _cache_state["items"][:limit]

    async with _cache_lock:
        now = datetime.now(timezone.utc)
        if _cache_state["items"] and _cache_state["expires_at"] > now:
            return _cache_state["items"][:limit]
        items = await asyncio.to_thread(_gather_news)
        _cache_state["items"] = items
        _cache_state["expires_at"] = now + _CACHE_TTL
    return _cache_state["items"][:limit]
