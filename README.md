# Arch Bootstrap

Arch Bootstrap is an opinionated, interactive Arch Linux installer built on the native Python API and TUI components of `archinstall` 4.x. A small standard-library bootstrap (`install.py`) prepares the live ISO and launches the full `arch_bootstrap` package or release zipapp.

## Project status

This is a public, non-archived, standalone repository rather than a fork. It automates destructive installation onto a selected block device and should be used only from an Arch live environment after backups and target-disk verification. The checkout includes the configuration conversion layer, zipapp workflow, and a focused DMS installer test module; it is not a general replacement for all `archinstall` profiles.

## Architecture and data flow

1. `install.py` reopens `/dev/tty` for piped execution, detects region, adjusts live-ISO mirrors, upgrades pre-4 `archinstall` when required, downloads the release zipapp, and replaces itself with that process.
2. `arch_bootstrap/__main__.py` detects the environment, starts the wizard, passes `WizardState` into `config.py`, and invokes installation after confirmation.
3. `wizard.py` collects localized choices and supports an advanced `archinstall` GlobalMenu escape hatch.
4. `config.py` supplies `build_default_config()` and `apply_wizard_state_to_config()`, converting wizard selections into the `ArchConfig` model.
5. `disk.py` creates the opinionated EFI/Btrfs layout; `installation.py` coordinates archinstall and post-install tasks.
6. `constants.py` centralizes choices and packages; `detection.py`, `mirrors.py`, and `utils.py` provide environment/network support.
7. Desktop integrations are divided among `dms.py`, `dms_manual.py`, and `exo.py`; compatibility imports live in `archinstall_compat.py`.

Installation logs are written to `/var/log/arch-bootstrap/install.log` and copied into the installed system.

## Requirements

- An Arch Linux live ISO in UEFI mode
- Root privileges
- A working network connection
- Python 3.12 or newer for direct package/zipapp execution: `wizard.py` uses PEP 695 generic class syntax
- `archinstall` 4.x for the full installer; `install.py` upgrades an older live-ISO version
- A destination disk whose existing contents may be erased

The bootstrap script itself stays standard-library-only. Hardware detection and installation additionally invoke system utilities supplied by the live ISO or installed during preparation.

## Setup and commands

Boot the official [Arch Linux ISO](https://archlinux.org/download/), connect to the network, inspect available disks, and run the published bootstrap:

```bash
curl -sL https://raw.githubusercontent.com/ParticleG/arch-bootstrap/main/install.py | python
```

Piping remote code into a root installer executes the fetched content immediately. For reviewability, download and inspect it first:

```bash
curl -sLO https://raw.githubusercontent.com/ParticleG/arch-bootstrap/main/install.py
less install.py
sudo python install.py
```

Run a trusted checkout directly:

```bash
git clone https://github.com/ParticleG/arch-bootstrap.git
cd arch-bootstrap
sudo python -m arch_bootstrap
```

Build a zipapp from the checkout:

```bash
rm -rf _staging
mkdir -p _staging
cp -r arch_bootstrap _staging/arch_bootstrap
printf 'from arch_bootstrap.__main__ import main\nmain()\n' > _staging/__main__.py
python -m zipapp _staging -o arch_bootstrap.pyz -p '/usr/bin/env python3'
rm -rf _staging
```

Run the focused tests without starting installation:

```bash
python -m unittest discover -s tests -v
```

## Installation behavior and side effects

The wizard selects language/input, mirrors, disk, hibernation, network backend, hostname, repositories, GPU/audio support, desktop, development/gaming packages, applications, and credentials. Defaults include EFISTUB with a Unified Kernel Image, Btrfs with Snapper, PipeWire, zram, and system services selected by the chosen profile.

Before the wizard reaches final installation confirmation, `install.py` can already modify the live ISO: it may replace the live mirror list, synchronize/install packages, upgrade `archinstall`, start `switcheroo-control.service`, and download the zipapp. These preparation mutations affect the live environment but do not repartition the selected target disk.

After final confirmation, the full installer can:

- stop swap and release LVM/LUKS/device-mapper locks;
- repartition and format the selected disk, destroying existing data;
- create EFI and Btrfs layouts and optional hibernation swap state;
- install packages from official repositories, archlinuxcn, AUR, and selected upstream assets;
- change mirror and repository configuration;
- create users and store the credentials needed during installation;
- enable services, boot configuration, Snapper timers, desktop integrations, virtualization, and GPU passthrough;
- download packages and external release assets; and
- offer reboot or `arch-chroot` after completion.

Back up data, verify the selected device by stable identifiers, and keep network/power available. Use the final confirmation screen to cancel if the disk or configuration is wrong.

## Project structure

- `install.py` — stdlib-only live-ISO bootstrap.
- `arch_bootstrap/__main__.py` — full installer entry point.
- `arch_bootstrap/wizard.py` — multi-step localized TUI.
- `arch_bootstrap/config.py` — default config and wizard-to-`ArchConfig` conversion.
- `arch_bootstrap/disk.py` — partition/Btrfs model.
- `arch_bootstrap/installation.py` — destructive install and post-install orchestration.
- `arch_bootstrap/constants.py` — package/option data.
- `arch_bootstrap/i18n.py` — English, Simplified Chinese, and Japanese strings.
- `arch_bootstrap/archinstall_compat.py` — archinstall API compatibility boundary.
- `tests/test_dms_installers.py` — focused DMS behavior tests.
- `.github/workflows/package.yml` — zipapp build and tagged release automation.

## Limitations

- The installer intentionally applies opinionated disk, boot, filesystem, package, and service choices.
- It depends on live network services, mirrors, package repositories, GitHub-hosted sources, and evolving `archinstall` APIs.
- Only part of the installation surface has automated unit coverage; disk and full installation behavior require disposable-machine testing.
- Hardware detection and third-party package availability can vary by machine, region, and time.
- Python 3.11 is insufficient for the current `wizard.py` syntax even if an older Arch ISO happens to provide it.

## License and attribution

The repository does not contain a license file in this checkout. No permission beyond applicable default copyright law should be inferred; obtain clarification from the repository owner before reuse or redistribution. Arch Linux and `archinstall` are upstream projects used by this installer and are not authored by this repository.
