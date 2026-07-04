"""Compatibility shims for archinstall API changes."""
from __future__ import annotations

import sys
import time
from enum import Enum, auto
from typing import Any

try:  # archinstall <= 2.x / older API
    from archinstall.lib.output import Font, debug, error, info  # type: ignore[import-not-found]
except ImportError:
    try:  # archinstall 4.x moved these symbols to archinstall.lib.log
        from archinstall.lib.log import Font, debug, error, info  # type: ignore[import-not-found]
    except ImportError:
        class Font(Enum):
            """Fallback font enum used when archinstall is unavailable in tests."""

            bold = '1'
            italic = '3'
            underscore = '4'
            blink = '5'
            reverse = '7'
            conceal = '8'

        def _print(*msgs: Any, **_: Any) -> None:
            print(' '.join(str(msg) for msg in msgs))

        info = _print
        debug = _print
        error = _print

try:  # archinstall 4.x
    from archinstall.tui.components import OptionListScreen, tui  # type: ignore[import-not-found]
except ImportError:
    try:  # archinstall <= 3.x
        from archinstall.tui.ui.components import OptionListScreen, tui  # type: ignore[import-not-found]
    except ImportError:
        class OptionListScreen:  # type: ignore[no-redef]
            def __init__(self, *_: Any, **__: Any) -> None:
                raise RuntimeError('archinstall TUI components are unavailable')

        class _FallbackTui:
            def run(self, *_: Any, **__: Any) -> Any:
                raise RuntimeError('archinstall TUI runner is unavailable')

        tui = _FallbackTui()

try:  # archinstall 4.x
    from archinstall.tui.menu_item import MenuItem, MenuItemGroup  # type: ignore[import-not-found]
except ImportError:
    try:  # archinstall <= 3.x
        from archinstall.tui.ui.menu_item import MenuItem, MenuItemGroup  # type: ignore[import-not-found]
    except ImportError:
        class MenuItem:  # type: ignore[no-redef]
            _yes: 'MenuItem | None' = None
            _no: 'MenuItem | None' = None

            def __init__(self, text: str, value: Any | None = None, **_: Any) -> None:
                self.text = text
                self.value = value

            @classmethod
            def yes(cls) -> 'MenuItem':
                if cls._yes is None:
                    cls._yes = cls('Yes', value=True)
                return cls._yes

            @classmethod
            def no(cls) -> 'MenuItem':
                if cls._no is None:
                    cls._no = cls('No', value=False)
                return cls._no

            def get_value(self) -> Any:
                return self.value

        class MenuItemGroup:  # type: ignore[no-redef]
            def __init__(self, items: list[MenuItem], **_: Any) -> None:
                self.items = items

            @classmethod
            def yes_no(cls) -> 'MenuItemGroup':
                return cls([MenuItem.yes(), MenuItem.no()])

try:  # archinstall 4.x
    from archinstall.tui.result import ResultType  # type: ignore[import-not-found]
except ImportError:
    try:  # archinstall <= 3.x
        from archinstall.tui.ui.result import ResultType  # type: ignore[import-not-found]
    except ImportError:
        class ResultType(Enum):  # type: ignore[no-redef]
            Selection = auto()
            Skip = auto()
            Reset = auto()

try:
    from archinstall.lib.menu.util import delayed_warning  # type: ignore[import-not-found]
except (ImportError, AttributeError):
    def delayed_warning(message: str) -> bool:
        """Fallback countdown used before destructive operations."""
        print(message, end='', flush=True)
        try:
            for char in '\n5...4...3...2...1\n':
                print(char, end='', flush=True)
                time.sleep(0.25)
        except KeyboardInterrupt:
            sys.exit(1)
        return True
