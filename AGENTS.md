# AGENTS.md

## Project Overview

Arch Bootstrap is an opinionated Arch Linux installer using `archinstall` 4.x. `install.py` is a standard-library bootstrap for the live ISO; the `arch_bootstrap/` package provides the localized TUI, configuration conversion, disk plan, installation orchestration, and desktop integrations. Full execution is destructive and requires root. Current package/zipapp execution requires Python 3.12+ because `wizard.py` uses PEP 695 generic syntax.

## Architecture & Data Flow

- `install.py` detects region, configures mirrors, ensures a compatible `archinstall`, retrieves the zipapp, and `exec`s it. Keep this file standard-library-only.
- `arch_bootstrap/__main__.py` wires detection → wizard → `config.py` → confirmation → installation.
- `wizard.py` mutates `WizardState`; `config.py:build_default_config()` creates the base `ArchConfig`, and `apply_wizard_state_to_config()` maps wizard fields into it.
- `disk.py` builds the EFI/Btrfs layout. `installation.py` performs archinstall and post-install mutations.
- `constants.py` is the source for package lists and option dictionaries. `i18n.py` owns all localized user text.
- `archinstall_compat.py` isolates moved logging and TUI imports across archinstall versions.
- `dms.py`, `dms_manual.py`, and `exo.py` implement desktop-specific install surfaces.

When a wizard field changes, update its state definition, step order, translations, configuration mapping, and installation consumer together.

## Key Directories

- `arch_bootstrap/` — production installer package.
- `arch_bootstrap/scripts/` — files installed or invoked by post-install flows.
- `tests/` — focused `unittest` coverage, currently centered on DMS installers.
- `.github/workflows/` — zipapp packaging and release automation.
- `docs/plans/` — design notes; code remains authoritative.

## Development Commands

```bash
# Run the focused automated checks
python -m unittest discover -s tests -v

# Invoke the installer from source: destructive, root/live ISO only
sudo python -m arch_bootstrap

# Build the same style of zipapp without installing
rm -rf _staging
mkdir -p _staging
cp -r arch_bootstrap _staging/arch_bootstrap
printf 'from arch_bootstrap.__main__ import main\nmain()\n' > _staging/__main__.py
python -m zipapp _staging -o arch_bootstrap.pyz -p '/usr/bin/env python3'
rm -rf _staging
```

Do not use a workstation disk to smoke-test installation. Use a disposable UEFI VM with snapshots and a dedicated virtual disk.

## Code Conventions & Common Patterns

- Keep `install.py` stdlib-only and synchronize duplicated region, mirror, and proxy logic with package equivalents.
- Route every user-facing wizard/installation string through `i18n.py`; add English, Simplified Chinese, and Japanese values together.
- Wizard steps are asynchronous, return navigation outcomes, and are ordered explicitly in `run_wizard()`; preserve conditions based on earlier answers.
- Centralize options and package names in `constants.py` instead of scattering literals.
- Preserve package-source semantics: official repository packages, archlinuxcn-qualified packages, exact AUR targets, and prebuilt assets use different installation paths.
- Import moved archinstall symbols through `archinstall_compat.py`; keep TUI execution and logging teardown/resume boundaries intact.
- Use retry helpers for required transient operations. Optional best-effort downloads should not become interactive blockers.
- Treat disk selection and configuration mapping as safety boundaries: reject invalid state rather than guessing.

## Important Files

- `install.py` — pipe-friendly live-ISO bootstrap.
- `arch_bootstrap/__main__.py` — application entry and top-level control flow.
- `arch_bootstrap/wizard.py` — `WizardState`, steps, and navigation.
- `arch_bootstrap/config.py` — existing default configuration and wizard-to-config conversion boundary.
- `arch_bootstrap/disk.py` — partition and Btrfs layout.
- `arch_bootstrap/installation.py` — installation and post-install actions.
- `arch_bootstrap/constants.py` — package and option definitions.
- `arch_bootstrap/i18n.py` — all translations.
- `arch_bootstrap/archinstall_compat.py` — upstream API compatibility.
- `tests/test_dms_installers.py` — current automated contract coverage.
- `.github/workflows/package.yml` — zipapp/release build.

## Runtime/Tooling Preferences

Use Python 3.12+, `unittest`, the standard-library `zipapp` module, and `archinstall` 4.x. The bootstrap must remain usable before third-party Python dependencies are installed. Production execution assumes an Arch live ISO, UEFI, root, network access, and standard Arch utilities. Prefer archinstall's native API over subprocess reimplementations where an appropriate stable boundary exists.

No repository-wide formatter, linter, or static type checker is configured. Match existing Python style and make focused checks rather than inventing a competing toolchain in an unrelated change.

## Testing & QA

- Run `python -m unittest discover -s tests -v` for non-destructive automated coverage.
- Add tests for observable configuration or desktop-installer behavior when changing those contracts.
- Build and launch the zipapp only far enough to validate startup/navigation in a disposable environment.
- For disk/install changes, use a snapshotted UEFI VM and dedicated virtual disk. Verify partition layout, cancellation before confirmation, logging, package sources, bootability, and post-install services.
- Exercise back navigation and conditional wizard branches across locale, country, desktop, development, gaming, and virtualization selections.
- Confirm every new user-facing key exists in all three language dictionaries.
- Review logs and fixtures so passwords, tokens, private endpoints, and machine-specific paths are never committed.
