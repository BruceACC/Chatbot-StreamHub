"""
hls_capture.py
Capture high-quality stream snapshot with URL fallback for Vision HLS/WebRTC.
"""

from __future__ import annotations

import base64
from typing import Any

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

HLS_STREAM_URLS = [
    "http://desktop-fufpeoh:8889/live/stream/?mode=webrtc",
    "http://desktop-fufpeoh:8889/live/stream/",
    "http://desktop-fufpeoh:8888/live/stream/index.m3u8",
]


def _safe_error(exc: Exception) -> str:
    msg = str(exc).strip()
    return msg if msg else exc.__class__.__name__


def _extract_video_frame_base64(page, wait_ms: int = 2000) -> str:
    """
    Extracts the real frame from the <video> element at native video resolution.
    Returns pure base64 PNG, without data:image/png;base64 prefix.
    """
    return page.evaluate(
        """
        async (waitMs) => {
            const video = document.querySelector("video");

            if (!video) {
                throw new Error("No se encontró elemento <video>");
            }

            try {
                await video.play();
            } catch (e) {
                // En headless puede fallar autoplay, pero igual intentamos capturar.
            }

            const start = Date.now();

            while (
                Date.now() - start < waitMs &&
                (!video.videoWidth || !video.videoHeight || video.readyState < 2)
            ) {
                await new Promise(resolve => setTimeout(resolve, 100));
            }

            if (!video.videoWidth || !video.videoHeight) {
                throw new Error("El video no tiene resolución disponible todavía");
            }

            const canvas = document.createElement("canvas");
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;

            const ctx = canvas.getContext("2d");
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

            const dataUrl = canvas.toDataURL("image/png");
            return dataUrl.split(",")[1];
        }
        """,
        wait_ms,
    )


def capture_hls_snapshot(
    urls: list[str] | None = None,
    timeout_ms: int = 10000,
    wait_video_ms: int = 2500,
) -> dict[str, Any]:
    """
    Try to capture one high-quality image from the stream URLs in order.

    Returns:
      {
        "success": bool,
        "image_base64": str,
        "url_used": str,
        "format": "png",
        "results": [{"url": str, "ok": bool, "detail": str}],
      }
    """
    stream_urls = urls or HLS_STREAM_URLS
    results: list[dict[str, Any]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--autoplay-policy=no-user-gesture-required",
                "--disable-web-security",
            ],
        )

        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=2,
        )

        try:
            for url in stream_urls:
                page = context.new_page()

                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

                    # Espera a que aparezca el video.
                    page.wait_for_selector("video", timeout=timeout_ms)

                    # Captura el frame real del stream, no la página.
                    image_b64 = _extract_video_frame_base64(page, wait_ms=wait_video_ms)

                    if not image_b64:
                        raise RuntimeError("frame vacío")

                    size_bytes = len(base64.b64decode(image_b64))

                    results.append(
                        {
                            "url": url,
                            "ok": True,
                            "detail": f"{size_bytes} bytes PNG desde frame real",
                        }
                    )

                    return {
                        "success": True,
                        "image_base64": image_b64,
                        "url_used": url,
                        "format": "png",
                        "results": results,
                    }

                except PlaywrightTimeoutError:
                    results.append({"url": url, "ok": False, "detail": "timeout"})

                except Exception as exc:
                    # Fallback: si no puede extraer el video, toma screenshot de página en PNG.
                    try:
                        image_bytes = page.screenshot(
                            type="png",
                            full_page=False,
                            scale="device",
                        )

                        if image_bytes:
                            image_b64 = base64.b64encode(image_bytes).decode("utf-8")

                            results.append(
                                {
                                    "url": url,
                                    "ok": True,
                                    "detail": f"{len(image_bytes)} bytes PNG fallback screenshot",
                                }
                            )

                            return {
                                "success": True,
                                "image_base64": image_b64,
                                "url_used": url,
                                "format": "png",
                                "results": results,
                            }

                    except Exception:
                        pass

                    results.append(
                        {
                            "url": url,
                            "ok": False,
                            "detail": _safe_error(exc),
                        }
                    )

                finally:
                    page.close()

        finally:
            context.close()
            browser.close()

    return {
        "success": False,
        "image_base64": "",
        "url_used": "",
        "format": "png",
        "results": results,
    }
