"""
bot_worker.py
One BotWorker per Kick.com account. Runs a Playwright browser context,
navigates to the channel chat popout, and sends messages on demand.
"""

import threading
import time
import logging
import re
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from core.session_manager import get_session_path, get_proxy

logger = logging.getLogger(__name__)

# CSS selectors for Kick.com chat input (may need updating if Kick changes their DOM)
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

SEND_BUTTON_SELECTORS = [
    '[data-testid="send-message-button"]',
    'button[aria-label="Send message"]',
    'button[type="submit"]',
]


class BotWorker:
    def __init__(self, account_name: str, account_index: int, on_log: callable = None, headless: bool = False):
        self.account_name = account_name
        self.account_index = account_index
        self.on_log = on_log  # callback(account_name, message)
        self._headless = headless

        self._thread: threading.Thread | None = None
        self._running = False
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._page1 = None  # Main channel page (kept open for streaming)
        self._chat_target = "popout"
        self._chat_page = None
        self._lock = threading.Lock()
        self._send_queue: list[str] = []
        self._queue_event = threading.Event()

        self.status = "idle"   # idle | starting | ready | sending | error | stopped
        self.last_error = ""

    def _log(self, msg: str):
        logger.info(f"[{self.account_name}] {msg}")
        if self.on_log:
            self.on_log(self.account_name, msg)

    def start(self, channel: str, chat_target: str = "popout"):
        """Start the worker thread and open the chat window."""
        if self._running:
            return
        self._running = True
        self.status = "starting"
        self._chat_target = "channel" if chat_target == "channel" else "popout"
        self._thread = threading.Thread(
            target=self._run, args=(channel,), daemon=True
        )
        self._thread.start()

    def stop(self):
        """Signal the worker to stop and close the browser non-blockingly."""
        if not self._running:
            return
        self._running = False
        self._queue_event.set()  # unblock any wait
        
        # Wait briefly for thread to finish, then timeout
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
            
        self.status = "stopped"
        self._log("Stopped.")

    def send_message(self, text: str):
        """Queue a message to be sent by this worker."""
        with self._lock:
            self._send_queue.append(text)
        self._queue_event.set()

    def _run(self, channel: str):
        channel_url = f"https://kick.com/{channel}"
        popout_url = f"https://kick.com/popout/{channel}/chat"
        state_path = get_session_path(self.account_name)
        pw_proxy = get_proxy(self.account_name)

        try:
            with sync_playwright() as p:
                self._playwright = p
                self._browser = p.chromium.launch(
                    channel="chrome",
                    headless=self._headless,
                    args=[
                        "--start-maximized",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--disable-extensions",
                    ],
                    proxy=pw_proxy if pw_proxy else None
                )
                self._context = self._browser.new_context(
                    storage_state=str(state_path) if state_path.exists() else None,
                    viewport=None,
                )
                
                # Open only selected destination
                if self._chat_target == "channel":
                    self._log(f"Opening {channel_url}")
                    self._page1 = self._context.new_page()
                    self._page1.goto(channel_url, wait_until="domcontentloaded", timeout=30_000)
                    try:
                        self._page1.wait_for_load_state("networkidle", timeout=15_000)
                    except Exception:
                        pass

                    # Keep stream light while counting view
                    try:
                        self._page1.evaluate("""
                            () => {
                                document.querySelectorAll('video, audio').forEach(el => {
                                    el.muted = true;
                                    el.volume = 0;
                                });
                            }
                        """)
                    except Exception:
                        pass
                    self._chat_page = self._page1
                else:
                    self._log(f"Opening {popout_url}")
                    self._page = self._context.new_page()
                    self._page.goto(popout_url, wait_until="domcontentloaded", timeout=30_000)
                    try:
                        self._page.wait_for_load_state("networkidle", timeout=15_000)
                    except Exception:
                        pass
                    self._chat_page = self._page

                # Wait for chat input to appear
                input_el = self._find_chat_input()
                if input_el:
                    self.status = "ready"
                    self._log(f"Chat ready on {self._chat_target}.")
                else:
                    self.status = "error"
                    error_url = channel_url if self._chat_target == "channel" else popout_url
                    self.last_error = self._build_chat_input_error(error_url)
                    self._log(f"ERROR: {self.last_error}")
                    return

                # Main loop: wait for messages to send
                while self._running:
                    self._queue_event.wait(timeout=1.0)
                    self._queue_event.clear()

                    while True:
                        with self._lock:
                            if not self._send_queue:
                                break
                            text = self._send_queue.pop(0)

                        if not self._running:
                            break

                        self._send_to_chat(text)

        except Exception as e:
            self.status = "error"
            self.last_error = str(e)
            self._log(f"ERROR: {e}")
        finally:
            try:
                # Close both pages first
                if self._page:
                    try:
                        self._page.close()
                    except Exception:
                        pass
                    self._page = None
                
                if self._page1:
                    try:
                        self._page1.close()
                    except Exception:
                        pass
                    self._page1 = None
                self._chat_page = None
                
                if self._context:
                    self._context.close()
                    self._context = None
                    
                if self._browser:
                    self._browser.close()
                    self._browser = None
                    
                self._playwright = None
            except Exception:
                pass

    def _find_chat_input(self):
        """Try multiple selectors to find the chat input element."""
        if not self._chat_page:
            return None

        search_roots = [self._chat_page]
        try:
            search_roots.extend(self._chat_page.frames)
        except Exception:
            pass

        for root in search_roots:
            for selector in CHAT_INPUT_SELECTORS:
                try:
                    el = root.wait_for_selector(selector, timeout=5_000)
                    if el:
                        return el
                except PlaywrightTimeout:
                    continue
                except Exception:
                    continue
        return None

    def _build_chat_input_error(self, url: str) -> str:
        """Collect lightweight diagnostics when the chat input cannot be located."""
        try:
            title = self._chat_page.title() if self._chat_page else "<unknown>"
        except Exception:
            title = "<unknown>"

        try:
            frame_count = len(self._chat_page.frames) if self._chat_page else -1
        except Exception:
            frame_count = -1

        try:
            body_text = self._chat_page.locator("body").inner_text(timeout=2_000) if self._chat_page else ""
        except Exception:
            body_text = ""

        body_preview = " ".join(body_text.split())[:200]
        return (
            "Could not find chat input on page. "
            f"url={url} title={title!r} frames={frame_count} body={body_preview!r}"
        )

    def _send_to_chat(self, text: str):
        """Type and send a message in the chat input."""
        try:
            self.status = "sending"
            text = self._sanitize_chat_text(text)
            if not text.strip():
                self.status = "ready"
                return

            input_el = self._find_chat_input()
            if not input_el:
                self._log("Chat input not found, skipping message.")
                self.status = "ready"
                return

            input_el.click()
            time.sleep(0.2)

            # Clear any existing text
            input_el.fill("")
            time.sleep(0.1)

            # Type the message
            input_el.type(text, delay=30)
            time.sleep(0.15)

            # Try pressing Enter first
            input_el.press("Enter")
            time.sleep(0.5)

            self._log(f"Sent: {text[:60]}{'...' if len(text) > 60 else ''}")
            self.status = "ready"

        except Exception as e:
            self.status = "error"
            self.last_error = str(e)
            self._log(f"Send error: {e}")
            self.status = "ready"

    def _sanitize_chat_text(self, text: str) -> str:
        """Normalize spacing while preserving emojis and [emote:*] tags."""
        cleaned = (text or "").replace("\n", " ").replace("\r", " ").replace("\t", " ").strip()
        if not cleaned:
            return ""

        # Drop only control chars that can break input while keeping unicode content.
        cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", " ", cleaned)
        cleaned = re.sub(r"([!?.,])\1+", r"\1", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        return cleaned[:500]
