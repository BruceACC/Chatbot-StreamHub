"""
bot_worker.py
One BotWorker per Kick.com account. Uses a shared Playwright browser,
creates one isolated context per account, and sends messages on demand.
"""

import threading
import logging
import re

from core.browser_manager import get_shared_browser_manager

logger = logging.getLogger(__name__)


class BotWorker:
    def __init__(self, account_name: str, account_index: int, on_log: callable = None, headless: bool = False):
        self.account_name = account_name
        self.account_index = account_index
        self.on_log = on_log  # callback(account_name, message)
        self._headless = headless

        self._thread: threading.Thread | None = None
        self._running = False
        self._browser_session = None
        self._chat_target = "popout"
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

        try:
            browser_manager = get_shared_browser_manager(headless=self._headless)

            self._log(f"Opening {channel_url if self._chat_target == 'channel' else popout_url}")
            self._browser_session = browser_manager.open_session(
                account_name=self.account_name,
                channel=channel,
                chat_target=self._chat_target,
            )

            self.status = "ready"
            self._log(f"Chat ready on {self._chat_target}.")

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
                if self._browser_session:
                    self._browser_session.close()
                    self._browser_session = None
            except Exception:
                pass

    def _send_to_chat(self, text: str):
        """Type and send a message in the chat input."""
        try:
            self.status = "sending"
            text = self._sanitize_chat_text(text)
            if not text.strip():
                self.status = "ready"
                return

            if not self._browser_session:
                self._log("Chat session not ready, skipping message.")
                self.status = "ready"
                return

            self._browser_session.send_message(text)

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
