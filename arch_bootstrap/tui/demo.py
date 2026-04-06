"""Demo script to test split-pane layout.

Run: python -m arch_bootstrap.tui.demo
"""

from __future__ import annotations

from .app import WizardApp
from .steps import DemoSelectStep


def main() -> None:
    steps = [
        {
            'name': 'Language',
            'widget_class': DemoSelectStep,
            'kwargs': {
                'title': 'Select Language',
                'options': ['English', '\u7b80\u4f53\u4e2d\u6587', '\u65e5\u672c\u8a9e'],
            },
        },
        {
            'name': 'Region',
            'widget_class': DemoSelectStep,
            'kwargs': {
                'title': 'Select Region',
                'options': ['China', 'United States', 'Japan', 'Germany'],
            },
        },
        {
            'name': 'Confirm',
            'widget_class': DemoSelectStep,
            'kwargs': {
                'title': 'Ready to install?',
                'options': ['Install', 'Cancel'],
            },
        },
    ]

    result = WizardApp(steps).run()
    print(f'Wizard result: {result}')


if __name__ == '__main__':
    main()
