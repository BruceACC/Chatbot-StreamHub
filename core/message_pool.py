"""
message_pool.py
Manages the pool of messages (one per line) and selection logic.
"""

import random


class MessagePool:
    def __init__(self):
        self._lines: list[str] = []
        self._index: int = 0

    def set_text(self, text: str):
        """Parse multiline text into individual messages, stripping blanks."""
        self._lines = [line for line in text.splitlines() if line.strip()]
        self._index = 0

    def has_messages(self) -> bool:
        return len(self._lines) > 0

    def get_message(self, account_index: int = 0, random_mode: bool = False) -> str:
        """
        Return a message for the given account.
        - random_mode=True  → random line per call
        - random_mode=False → sequential: account_index % len(lines)
        """
        if not self._lines:
            return ""
        if random_mode:
            return random.choice(self._lines)
        return self._lines[account_index % len(self._lines)]

    def get_next_sequential(self) -> str:
        """Returns next message in round-robin order (shared counter)."""
        if not self._lines:
            return ""
        msg = self._lines[self._index % len(self._lines)]
        self._index += 1
        return msg

    @property
    def count(self) -> int:
        return len(self._lines)

    @property
    def lines(self) -> list[str]:
        return list(self._lines)
