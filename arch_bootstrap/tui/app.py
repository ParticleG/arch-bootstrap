"""WizardApp: Custom Textual App for the split-pane wizard."""

from __future__ import annotations

from typing import Any

from textual.app import App

from .screen import WizardScreen


class WizardApp(App[str]):
    """Independent Textual App for the wizard phase.

    Manages step navigation and provides split-pane layout via WizardScreen.
    Returns 'install', 'advanced', or 'abort' when wizard completes.
    """

    ENABLE_COMMAND_PALETTE = False

    CSS = """
    Screen {
        background: $surface;
    }

    #split-pane {
        height: 1fr;
    }

    #left-panel {
        width: 55%;
        height: 100%;
        padding: 1 2;
    }

    #right-panel {
        width: 45%;
        height: 100%;
        padding: 1 2;
    }

    .step-header {
        text-style: bold;
        margin-bottom: 1;
    }

    #step-options {
        height: 1fr;
    }
    """

    def __init__(
        self,
        steps: list[dict[str, Any]],
        *,
        ansi_color: bool = True,
    ) -> None:
        super().__init__(ansi_color=ansi_color)
        self._steps = steps

    def on_mount(self) -> None:
        self.push_screen(WizardScreen(self._steps))
