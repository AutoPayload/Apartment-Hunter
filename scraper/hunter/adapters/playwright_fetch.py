"""Render a JavaScript-heavy page with Playwright. Only used by adapters with needs_js = True.

Install with: pip install 'apartment-hunter[js]' && playwright install chromium
"""

from __future__ import annotations


def render(url: str, user_agent: str, wait_ms: int = 2500) -> str:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page(user_agent=user_agent, locale="es-CR")
            page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_timeout(wait_ms)
            return page.content()
        finally:
            browser.close()
