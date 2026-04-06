"""Step widgets for the wizard."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Label, OptionList
from textual.widgets.option_list import Option


class StepComplete(Message):
    """Posted by a step widget when the user completes or navigates."""

    def __init__(
        self,
        action: str,
        *,
        label: str | None = None,
        value: Any = None,
    ) -> None:
        self.action = action   # 'next', 'back', 'abort', 'advanced'
        self.label = label     # display label for progress panel
        self.value = value     # selected value
        super().__init__()


class StepWidget(Widget):
    """Base class for wizard step widgets.

    Subclasses should call self.complete() to signal navigation.
    """

    step_title: str = ''

    def complete(
        self,
        action: str,
        *,
        label: str | None = None,
        value: Any = None,
    ) -> None:
        """Signal step completion/navigation."""
        self.post_message(StepComplete(action, label=label, value=value))


class DemoSelectStep(StepWidget):
    """Demo step with a simple option list for testing the framework."""

    def __init__(self, title: str, options: list[str], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._title = title
        self._options = options

    def compose(self) -> ComposeResult:
        yield Label(self._title, classes='step-header')
        yield OptionList(
            *[Option(opt, id=f'opt-{i}') for i, opt in enumerate(self._options)],
            id='step-options',
        )

    def on_mount(self) -> None:
        """Focus the option list so it receives keyboard input immediately."""
        self.query_one('#step-options', OptionList).focus()

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected,
    ) -> None:
        selected = self._options[event.option_index]
        self.complete('next', label=self._title, value=selected)

    def key_escape(self) -> None:
        self.complete('back')
