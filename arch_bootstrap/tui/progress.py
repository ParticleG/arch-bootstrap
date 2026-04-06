"""ProgressPanel: Persistent right-side summary of wizard progress."""

from __future__ import annotations

from typing import Any

from textual.app import RenderResult
from textual.widgets import Static


class ProgressPanel(Static):
    """Displays completed wizard step summaries on the right panel."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._entries: list[tuple[str, str]] = []

    def add_entry(self, key: str, value: str) -> None:
        """Add or update a progress entry."""
        for i, (k, _) in enumerate(self._entries):
            if k == key:
                self._entries[i] = (key, value)
                self.refresh()
                return
        self._entries.append((key, value))
        self.refresh()

    def render(self) -> RenderResult:
        if not self._entries:
            return '\u2500\u2500 Configuration \u2500\u2500\n\n  (no selections yet)'

        lines = ['\u2500\u2500 Configuration \u2500\u2500', '']
        for key, val in self._entries:
            lines.append(f'  \u2713 {key}: {val}')
        return '\n'.join(lines)
