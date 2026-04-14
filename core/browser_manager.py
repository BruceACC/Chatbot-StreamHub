"""
browser_manager.py
Shared Playwright browser with one isolated context per Kick account.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright
from playwright.async_api import Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError

from core.session_manager import get_proxy, get_session_path

logger = logging.getLogger(__name__)

CHAT_INPUT_SELECTORS = [
    '[data-testid="chat-input"]',
    'div[contenteditable="true"][class*="chat"]',
    'div[contenteditable="true"][aria-label*="message" i]',
    'div[contenteditable="true"][aria-label*="chat" i]',
    'div[contenteditable="true"]',
    'textarea[placeholder*="Send a message"]',
    'textarea[placeholder*="message" i]',
    'input[placeholder*="Send a message"]',
    'input[placeholder*="message" i]',
    '.chat-input',
    '#message-input',
    '[role="textbox"]',
]


class BrowserSession:
    """One account-bound context/page pair managed by the shared browser."""

    def __init__(
        self,
        manager: "SharedBrowserManager",
        account_name: str,
        context: BrowserContext,
        page: Page,
        state_path: Path,
        url: str,
        chat_target: str,
    ):
        self._manager = manager
        self.account_name = account_name
        self._context = context
        self._page = page
        self._state_path = state_path
        self._url = url
        self._chat_target = chat_target
        self._closed = False
        self._close_lock = threading.Lock()

    @property
    def url(self) -> str:
        return self._url

    @property
    def chat_target(self) -> str:
        return self._chat_target

    def send_message(self, text: str):
        """Send a chat message using the managed page."""
        return self._manager.run(self._send_message(text))

    def close(self):
        """Persist the session state and release the context/page."""
        with self._close_lock:
            if self._closed:
                return
            self._closed = True

        try:
            self._manager.run(self._close())
        except Exception as exc:
            logger.warning("Could not close browser session for %s: %s", self.account_name, exc)

    async def _send_message(self, text: str):
        if self._closed:
            raise RuntimeError(f"Browser session for {self.account_name} is closed.")

        locator = await self._find_chat_locator()
        if locator is None:
            raise RuntimeError(await self._collect_chat_diagnostics())

        await locator.click()
        await asyncio.sleep(0.2)

        await locator.fill("")
        await asyncio.sleep(0.1)

        await locator.type(text, delay=30)
        await asyncio.sleep(0.15)

        await locator.press("Enter")
        await asyncio.sleep(0.5)

    async def _close(self):
        try:
            if self._context and self._state_path:
                try:
                    self._state_path.parent.mkdir(parents=True, exist_ok=True)
                    await self._context.storage_state(path=str(self._state_path))
                except Exception as exc:
                    logger.warning(
                        "Could not persist storage state for %s: %s",
                        self.account_name,
                        exc,
                    )
        finally:
            if self._page:
                try:
                    await self._page.close()
                except Exception:
                    pass
                self._page = None

            if self._context:
                try:
                    await self._context.close()
                except Exception:
                    pass
                self._context = None

    async def _find_chat_locator(self):
        if not self._page:
            return None

        search_roots: list[Any] = [self._page]
        try:
            search_roots.extend(self._page.frames)
        except Exception:
            pass

        for root in search_roots:
            for selector in CHAT_INPUT_SELECTORS:
                locator = root.locator(selector).first
                try:
                    await locator.wait_for(state="visible", timeout=5_000)
                    return locator
                except PlaywrightTimeoutError:
                    continue
                except Exception:
                    continue

        return None

    async def _collect_chat_diagnostics(self) -> str:
        try:
            title = await self._page.title() if self._page else "<unknown>"
        except Exception:
            title = "<unknown>"

        try:
            frame_count = len(self._page.frames) if self._page else -1
        except Exception:
            frame_count = -1

        try:
            body_text = await self._page.locator("body").inner_text(timeout=2_000) if self._page else ""
        except Exception:
            body_text = ""

        body_preview = " ".join(body_text.split())[:200]
        return (
            "Could not find chat input on page. "
            f"url={self._url} title={title!r} frames={frame_count} body={body_preview!r}"
        )


class SharedBrowserManager:
    """Runs a single Chromium browser and opens one context per account."""

    def __init__(self, headless: bool = False):
        self._headless = headless
        self._thread = threading.Thread(target=self._thread_main, daemon=True)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ready = threading.Event()
        self._shutdown = threading.Event()
        self._browser: Browser | None = None
        self._playwright = None
        self._startup_error: Exception | None = None
        self._thread.start()

        if not self._ready.wait(timeout=30):
            raise RuntimeError("Timed out starting the shared Playwright browser.")
        if self._startup_error is not None:
            raise RuntimeError("Could not start the shared Playwright browser.") from self._startup_error

    def _thread_main(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop

        try:
            loop.run_until_complete(self._bootstrap())
            self._ready.set()
            loop.run_forever()
        except Exception as exc:
            self._startup_error = exc
            self._ready.set()
        finally:
            try:
                loop.run_until_complete(self._shutdown_browser())
            except Exception:
                pass
            self._shutdown.set()
            loop.close()

    async def _bootstrap(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            channel="chrome",
            headless=self._headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-extensions",
            ],
        )

    async def _shutdown_browser(self):
        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None

        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

    def run(self, coro):
        if self._loop is None or self._startup_error is not None:
            raise RuntimeError("Shared Playwright browser is not available.")

        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()

    def open_session(self, account_name: str, channel: str, chat_target: str = "popout") -> BrowserSession:
        normalized_target = "channel" if chat_target == "channel" else "popout"
        return self.run(self._open_session(account_name, channel.strip(), normalized_target))

    def login_account(self, account_name: str, proxy: dict[str, Any] | None = None) -> bool:
        return self.run(self._login_account(account_name, proxy))

    def shutdown(self):
        if self._shutdown.is_set():
            return

        if self._loop is not None and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

        self._shutdown.wait(timeout=30)

    async def _open_session(self, account_name: str, channel: str, chat_target: str) -> BrowserSession:
        browser = await self._ensure_browser()
        state_path = get_session_path(account_name)
        proxy = get_proxy(account_name)

        channel_url = f"https://kick.com/{channel}"
        popout_url = f"https://kick.com/popout/{channel}/chat"
        target_url = channel_url if chat_target == "channel" else popout_url

        context_kwargs: dict[str, Any] = {}
        if state_path.exists():
            context_kwargs["storage_state"] = str(state_path)
        if proxy:
            context_kwargs["proxy"] = proxy

        if chat_target == "popout":
            context_kwargs["viewport"] = {"width": 390, "height": 844}
        else:
            context_kwargs["viewport"] = None

        context: BrowserContext | None = None
        page: Page | None = None

        try:
            context = await browser.new_context(**context_kwargs)
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            page = await context.new_page()
            await page.goto(target_url, wait_until="domcontentloaded", timeout=30_000)

            try:
                await page.wait_for_load_state("networkidle", timeout=15_000)
            except PlaywrightTimeoutError:
                pass

            if chat_target == "channel":
                await self._optimize_channel_stream(page)

            locator = await self._find_chat_locator(page)
            if locator is None:
                raise RuntimeError(await self._build_chat_input_error(page, target_url))

            return BrowserSession(
                manager=self,
                account_name=account_name,
                context=context,
                page=page,
                state_path=state_path,
                url=target_url,
                chat_target=chat_target,
            )

        except Exception:
            if page is not None:
                try:
                    await page.close()
                except Exception:
                    pass

            if context is not None:
                try:
                    await context.close()
                except Exception:
                    pass

            raise

    async def _login_account(self, account_name: str, proxy: dict[str, Any] | None = None) -> bool:
        browser = await self._ensure_browser()
        state_path = get_session_path(account_name)
        state_path.parent.mkdir(parents=True, exist_ok=True)

        context_kwargs: dict[str, Any] = {}
        if state_path.exists():
            context_kwargs["storage_state"] = str(state_path)
        if proxy:
            context_kwargs["proxy"] = proxy
        context_kwargs["viewport"] = None

        context: BrowserContext | None = None
        page: Page | None = None
        logged_in = False

        try:
            context = await browser.new_context(**context_kwargs)
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            page = await context.new_page()

            await self._try_open_email_login(page)
            page.set_default_timeout(300_000)

            try:
                await page.wait_for_function(
                    """
                    () => {
                        const avatar = document.querySelector('button[aria-label="Open user menu"], [data-testid="user-menu-button"], img[alt*="avatar"], .user-profile-picture, [class*="UserMenu"], [class*="user-menu"]');
                        const kickBtn = Array.from(document.querySelectorAll('button')).find(el => (el.textContent || '').includes("KICKs"));

                        return (avatar !== null || kickBtn !== undefined);
                    }
                    """,
                    timeout=300_000,
                )
                logged_in = True
            except Exception:
                pass

            if logged_in:
                await context.storage_state(path=str(state_path))

            return logged_in

        finally:
            if page is not None:
                try:
                    await page.close()
                except Exception:
                    pass

            if context is not None:
                try:
                    await context.close()
                except Exception:
                    pass

    async def _try_open_email_login(self, page: Page) -> None:
        # Kick can render different auth flows depending on region/account.
        # Try common routes and then the sign-in controls from home.
        candidate_urls = [
            "https://kick.com/login",
            "https://kick.com/auth/login",
            "https://kick.com/",
        ]

        for target in candidate_urls:
            try:
                await page.goto(target, wait_until="domcontentloaded", timeout=30_000)
            except Exception:
                continue

            if await self._has_email_password_form(page):
                return

        sign_in_labels = ["Log in", "Sign in", "Iniciar sesion"]
        for label in sign_in_labels:
            try:
                btn = page.get_by_role("button", name=label)
                if await btn.count() > 0:
                    await btn.first.click(timeout=5_000)
                    await page.wait_for_timeout(800)
                    if await self._has_email_password_form(page):
                        return
            except Exception:
                pass

            try:
                link = page.get_by_role("link", name=label)
                if await link.count() > 0:
                    await link.first.click(timeout=5_000)
                    await page.wait_for_timeout(800)
                    if await self._has_email_password_form(page):
                        return
            except Exception:
                pass

    async def _has_email_password_form(self, page: Page) -> bool:
        try:
            has_email = await page.locator('input[type="email"], input[name*="email" i]').count() > 0
            has_password = await page.locator('input[type="password"], input[name*="password" i]').count() > 0
            return has_email and has_password
        except Exception:
            return False

    async def _ensure_browser(self) -> Browser:
        if self._browser is None:
            raise RuntimeError("Shared browser has not been initialized.")
        return self._browser

    async def _find_chat_locator(self, page: Page):
        search_roots: list[Any] = [page]
        try:
            search_roots.extend(page.frames)
        except Exception:
            pass

        for root in search_roots:
            for selector in CHAT_INPUT_SELECTORS:
                locator = root.locator(selector).first
                try:
                    await locator.wait_for(state="visible", timeout=5_000)
                    return locator
                except PlaywrightTimeoutError:
                    continue
                except Exception:
                    continue

        return None

    async def _build_chat_input_error(self, page: Page, url: str) -> str:
        try:
            title = await page.title()
        except Exception:
            title = "<unknown>"

        try:
            frame_count = len(page.frames)
        except Exception:
            frame_count = -1

        try:
            body_text = await page.locator("body").inner_text(timeout=2_000)
        except Exception:
            body_text = ""

        body_preview = " ".join(body_text.split())[:200]
        return (
            "Could not find chat input on page. "
            f"url={url} title={title!r} frames={frame_count} body={body_preview!r}"
        )

    async def _optimize_channel_stream(self, page: Page):
        try:
            await page.evaluate(
                """
                () => {
                    const click160p = () => {
                        const nodes = Array.from(document.querySelectorAll('button, [role="button"], [role="option"], li, span, div'));
                        const target = nodes.find((el) => /(^|\\s)160p(\\s|$)/i.test((el.textContent || '').trim()));
                        if (target) {
                            target.click();
                            return true;
                        }
                        return false;
                    };

                    const apply = () => {
                        document.querySelectorAll('video, audio').forEach((el) => {
                            el.muted = true;
                            el.volume = 0;
                        });

                        const styleId = 'kickbot-stream-optimize-style';
                        if (!document.getElementById(styleId)) {
                            const style = document.createElement('style');
                            style.id = styleId;
                            style.textContent = `
                                video {
                                    transform: scale(0.6) !important;
                                    transform-origin: top left !important;
                                    max-width: 64px !important;
                                    max-height: 36px !important;
                                    width: 64px !important;
                                    height: 36px !important;
                                }
                                [class*="player"], [class*="video"], [data-testid*="player"] {
                                    max-height: 36px !important;
                                    height: 36px !important;
                                    overflow: hidden !important;
                                }
                            `;
                            document.head.appendChild(style);
                        }

                        click160p();
                    };

                    apply();

                    if (!window.__kickbotOptimizeTimer) {
                        window.__kickbotOptimizeTimer = setInterval(apply, 3000);
                    }
                }
                """
            )
            logger.info("Applied shared browser channel optimization.")
        except Exception as exc:
            logger.warning("Could not optimize channel stream: %s", exc)


_shared_browser_manager: SharedBrowserManager | None = None
_shared_browser_manager_lock = threading.Lock()


def get_shared_browser_manager(headless: bool = False) -> SharedBrowserManager:
    global _shared_browser_manager

    with _shared_browser_manager_lock:
        if _shared_browser_manager is None:
            _shared_browser_manager = SharedBrowserManager(headless=headless)
        return _shared_browser_manager


def shutdown_shared_browser_manager():
    global _shared_browser_manager

    with _shared_browser_manager_lock:
        manager = _shared_browser_manager
        _shared_browser_manager = None

    if manager is not None:
        manager.shutdown()