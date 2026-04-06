"""WizardScreen: Split-pane layout with step container and progress panel."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Rule

from .progress import ProgressPanel
from .steps import StepComplete, StepWidget


class WizardScreen(Screen[str]):
    """Main wizard screen with left-right split layout.

    Left panel (55%): Active step widget (swapped on navigation).
    Right panel (45%): Persistent progress summary.
    """

    def __init__(self, steps: list[dict[str, Any]]) -> None:
        super().__init__()
        self._steps = steps
        self._current_index = 0
        self._active_step: StepWidget | None = None

    def compose(self) -> ComposeResult:
        with Horizontal(id='split-pane'):
            yield Vertical(id='left-panel')
            yield Rule(orientation='vertical')
            with Vertical(id='right-panel'):
                yield ProgressPanel(id='progress-panel')

    def on_mount(self) -> None:
        if self._steps:
            self._show_step(0)

    def _show_step(self, index: int) -> None:
        """Mount the step widget at the given index into the left panel."""
        if self._active_step is not None:
            self._active_step.remove()

        step_def = self._steps[index]
        widget_class = step_def['widget_class']
        kwargs = step_def.get('kwargs', {})
        step = widget_class(**kwargs)
        self._active_step = step
        self._current_index = index

        left = self.query_one('#left-panel')
        left.mount(step)

    def on_step_complete(self, message: StepComplete) -> None:
        """Handle step navigation based on StepComplete messages."""
        progress = self.query_one('#progress-panel', ProgressPanel)

        if message.action == 'next':
            # Record progress if label provided
            if message.label and message.value is not None:
                progress.add_entry(message.label, str(message.value))

            next_idx = self._current_index + 1
            if next_idx < len(self._steps):
                self._show_step(next_idx)
            else:
                self.dismiss('install')

        elif message.action == 'back':
            if self._current_index > 0:
                self._show_step(self._current_index - 1)

        elif message.action == 'abort':
            self.dismiss('abort')

        elif message.action == 'advanced':
            self.dismiss('advanced')
