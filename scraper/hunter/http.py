"""A slow, polite HTTP client: one request per host every few seconds, robots.txt respected."""

from __future__ import annotations

import logging
import time
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

log = logging.getLogger(__name__)


class RobotsDisallowed(Exception):
    pass


class PoliteClient:
    def __init__(self, user_agent: str, delay: float = 4.0, timeout: float = 20.0, retries: int = 2):
        self.delay = delay
        self.retries = retries
        self.user_agent = user_agent
        self._last: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser | None] = {}
        self._client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": user_agent,
                "Accept-Language": "es-CR,es;q=0.9,en;q=0.6",
                "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            },
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "PoliteClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _wait(self, host: str) -> None:
        elapsed = time.monotonic() - self._last.get(host, 0.0)
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last[host] = time.monotonic()

    def allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        root = f"{parts.scheme}://{parts.netloc}"
        if root not in self._robots:
            parser: RobotFileParser | None = RobotFileParser()
            try:
                resp = self._client.get(root + "/robots.txt")
                if resp.status_code >= 400:
                    parser = None  # no robots.txt: everything allowed
                else:
                    parser.parse(resp.text.splitlines())
            except httpx.HTTPError as exc:
                log.warning("robots.txt fetch failed for %s: %s", root, exc)
                parser = None
            self._robots[root] = parser
        parser = self._robots[root]
        return parser is None or parser.can_fetch(self.user_agent, url)

    def get(self, url: str, check_robots: bool = True) -> httpx.Response:
        if check_robots and not self.allowed(url):
            raise RobotsDisallowed(url)
        host = urlsplit(url).netloc
        last_exc: Exception | None = None
        for attempt in range(self.retries + 1):
            self._wait(host)
            try:
                resp = self._client.get(url)
                if resp.status_code in (429, 502, 503, 504) and attempt < self.retries:
                    time.sleep(self.delay * (attempt + 2))
                    continue
                resp.raise_for_status()
                return resp
            except httpx.HTTPError as exc:
                last_exc = exc
                if attempt < self.retries:
                    time.sleep(self.delay * (attempt + 1))
        assert last_exc is not None
        raise last_exc

    def get_text(self, url: str) -> str:
        return self.get(url).text
