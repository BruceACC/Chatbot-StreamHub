"""
hls_capture.py
Capture a stream snapshot with URL fallback for Vision HLS.
"""

from __future__ import annotations

import base64
from typing import Any

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

HLS_STREAM_URLS = [
    "http://localhost:8889/live/stream/?mode=webrtc",
    "http://localhost:8889/live/stream/",
    "http://localhost:8888/live/stream/index.m3u8",
]


def _safe_error(exc: Exception) -> str:
    msg = str(exc).strip()
    return msg if msg else exc.__class__.__name__


def capture_hls_snapshot(urls: list[str] | None = None, timeout_ms: int = 8000) -> dict[str, Any]:
    """
    Try to capture one image from the stream URLs in order.

    Returns:
      {
        "success": bool,
        "image_base64": str,
        "url_used": str,
        "results": [{"url": str, "ok": bool, "detail": str}],
      }
    """
    stream_urls = urls or HLS_STREAM_URLS
    results: list[dict[str, Any]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 640, "height": 360})
        try:
            for url in stream_urls:
                page = context.new_page()
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                    page.wait_for_timeout(1200)
                    image_bytes = page.screenshot(type="jpeg", quality=80, scale="css")
                    if not image_bytes:
                        raise RuntimeError("screenshot vacio")

                    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
                    results.append({"url": url, "ok": True, "detail": f"{len(image_bytes)} bytes"})
                    return {
                        "success": True,
                        "image_base64": image_b64,
                        "url_used": url,
                        "results": results,
                    }
                except PlaywrightTimeoutError:
                    results.append({"url": url, "ok": False, "detail": "timeout"})
                except Exception as exc:
                    results.append({"url": url, "ok": False, "detail": _safe_error(exc)})
                finally:
                    page.close()
        finally:
            context.close()
            browser.close()

    return {
        "success": False,
        "image_base64": "",
        "url_used": "",
        "results": results,
    }
