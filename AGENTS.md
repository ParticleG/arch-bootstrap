# AGENTS.md

## Overview

Opinionated Arch Linux installer. A bootstrap script (`install.py`, stdlib-only) downloads and runs a zipapp (`arch_bootstrap.pyz`) built from the `arch_bootstrap/` package. Targets Python 3.11+ on the Arch ISO with `archinstall >= 4.1`.

## Key architecture

- **`install.py`** — standalone bootstrap (stdlib only, no third-party imports). Detects region, upgrades archinstall on ISO, downloads `.pyz`, then `os.execv`s into it. Must stay stdlib-only.
- **`arch_bootstrap/`** — the real installer package. Entry point is `__main__.py:main()`. Depends on `archinstall` (TUI components, disk API, installation API).
- **`arch_bootstrap/__init__.py`** — contains `__version__`. CI auto-stamps this on tagged releases; don't manually bump it.

## Development

```bash
# Run from source (requires root + archinstall 4.1+ installed)
python -m arch_bootstrap

# Build zipapp locally
mkdir -p _staging
cp -r arch_bootstrap _staging/arch_bootstrap
printf 'from arch_bootstrap.__main__ import main\nmain()\n' > _staging/__main__.py
python -m zipapp _staging -o arch_bootstrap.pyz -p '/usr/bin/env python3'
rm -rf _staging
```

No test suite, no linter, no formatter configured.

## CI / Release

- **`.github/workflows/package.yml`** — builds `.pyz` on every push to `main`; creates a GitHub Release on `v*` tags.
- On tag push, CI stamps `__version__` in `__init__.py` and pushes the bump back to `main`.
- Release artifacts: `arch_bootstrap.pyz` + `install.py`.

## Conventions

- `install.py` must use **only stdlib** — it runs before any packages are installed.
- All user-facing strings go through `arch_bootstrap/i18n.py` (en/zh/ja).
- Hardware detection lives in `detection.py`; mirror logic in `mirrors.py`; disk layout in `disk.py`.
- Desktop environment profiles: `dms.py` (tiling DMS), `dms_manual.py` (manual DMS), `exo.py` (full DE). NVIDIA quirks in `nvidia.py`.
- Logs written to `/var/log/arch-bootstrap/install.log`.

## Code patterns to follow

### i18n — every user-facing string must be translated

`i18n.py` has a flat `TRANSLATIONS` dict with keys for `en`, `zh`, `ja`. Use `t('key.name')` for lookups; `t('key', arg1, arg2)` for `%s` interpolation. When adding any new user-facing text:

1. Add the key to all three language dicts in `i18n.py`.
2. Use `t()` at the call site — never inline raw strings in wizard/installation code.

### Adding a new wizard step

Wizard steps live in `wizard.py` as `async def step_*(state: WizardState) -> str` returning `'next'`, `'back'`, or `'abort'`. The step sequence is orchestrated by `run_wizard()` at the bottom of `wizard.py`. To add a step:

1. Define option constants in `constants.py` (dict of `key → label` or `key → package list`).
2. Add the `async def step_*` function in `wizard.py`.
3. Add corresponding state fields to `WizardState.__init__`.
4. Wire the step into `run_wizard()`'s step list (order matters — some steps are conditional on prior state like `country == 'CN'` or `desktop_env != 'minimal'`).
5. Handle the packages/config in `config.py:apply_wizard_state_to_config()` and/or `installation.py:perform_installation()`.
6. Add i18n keys for the step title/options.

### Package and option definitions

All package lists and option dicts are centralized in `constants.py`. Wizard steps and installation code reference these by key — don't scatter package names across files.

### archinstall API usage

The codebase imports heavily from `archinstall.lib.*` and `archinstall.tui.*`. Key patterns:
- TUI widgets: `Selection`, `Input`, `Confirmation` from `archinstall.lib.menu.helpers`; `OptionListScreen`, `MenuItem`, `MenuItemGroup` from `archinstall.tui.ui.*`.
- All TUI code runs inside `tui.run(lambda: ...)` (async context managed by archinstall's textual app).
- Logging must be torn down before TUI and resumed after (`teardown_logging()` / `resume_logging()`) — the TUI and log TeeStream conflict on stdout.

### install.py ↔ arch_bootstrap duplication

`install.py` intentionally duplicates some logic from the package (country detection, mirror lists, GitHub proxy resolution) because it runs before the package is available. When updating these, keep both copies in sync.

### Retry helpers

`utils.py` provides `run_with_retry()` (for subprocesses) and `retry_on_failure()` (for callables). Both auto-retry then interactively prompt the user. Use these for any network or pacman operations that can transiently fail.
