# Arch Bootstrap

Arch Bootstrap is an opinionated, interactive Arch Linux installer built on the native Python API and TUI components of `archinstall` 4.x. A small standard-library bootstrap (`install.py`) prepares the live ISO and launches the full `arch_bootstrap` package or release zipapp.

## Project status

This is a public, non-archived, standalone repository rather than a fork. It automates destructive installation onto a selected block device and should be used only from an Arch live environment after backups and target-disk verification. The checkout includes the configuration conversion layer, zipapp workflow, and focused desktop-installer and post-install maintenance tests; it is not a general replacement for all `archinstall` profiles.

## Architecture and data flow

1. `install.py` reopens `/dev/tty` for piped execution, detects region, adjusts live-ISO mirrors, upgrades pre-4 `archinstall` when required, downloads the release zipapp, and replaces itself with that process.
2. `arch_bootstrap/__main__.py` detects the environment, starts the wizard, passes `WizardState` into `config.py`, and invokes installation after confirmation.
3. `wizard.py` collects localized choices and supports an advanced `archinstall` GlobalMenu escape hatch.
4. `config.py` supplies `build_default_config()` and `apply_wizard_state_to_config()`, converting wizard selections into the `ArchConfig` model.
5. `disk.py` creates the opinionated EFI/Btrfs layout; `installation.py` coordinates archinstall and post-install tasks.
6. `constants.py` centralizes choices and packages; `packages.py` normalizes optional selections and separates official, region-qualified, and AUR sources. `detection.py`, `mirrors.py`, and `utils.py` provide environment/network support.
7. Desktop integrations live in `dms.py` and `exo.py`; compatibility imports live in `archinstall_compat.py`.

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

Desktop configuration integration tests require `archinstall`; the shell-plugin test additionally requires `zsh`. Those tests are skipped when their dependencies are unavailable. Package-selection, Dux lifecycle, translation, and maintenance-script tests also run without `archinstall`.

## Post-install maintenance

### Remove the GitHub source-download proxy

CN installations deploy `/usr/local/bin/github-proxy-dl` and configure the HTTPS entry in `/etc/makepkg.conf` to use it. To remove this wrapper, run the standalone uninstall script on the installed system, not the live-ISO installer:

```bash
sudo bash arch_bootstrap/scripts/uninstall-github-proxy-dl.sh
```

If the installed system does not have a checkout, download and inspect the script first:

```bash
curl -fLo uninstall-github-proxy-dl.sh \
  https://raw.githubusercontent.com/ParticleG/arch-bootstrap/main/arch_bootstrap/scripts/uninstall-github-proxy-dl.sh
less uninstall-github-proxy-dl.sh
sudo bash uninstall-github-proxy-dl.sh
```

The script requires only Bash and standard Arch system utilities; it does not import `archinstall` or run installation. It restores the HTTPS download command written by arch-bootstrap to `/usr/bin/curl`, then removes the wrapper. Other download agents, build settings, Git URL rewrites, network proxy applications, and package caches are left unchanged.

It is safe to run again if the wrapper is already absent. If the configuration contains a modified wrapper reference that the script cannot safely restore, it exits without changing the configuration or removing the wrapper; review that reference manually before retrying. Start a new `makepkg` or AUR-helper invocation after removal so it reads the updated configuration.

The script is available from the repository; it is not automatically installed into the target system. Future bootstrap deployments can install the proxy again.

## Installation behavior and side effects

The wizard selects language/input, mirrors, disk, hibernation, network backend, hostname, repositories, GPU/audio support, desktop, development/gaming/media/industrial packages, applications, and credentials. Defaults include EFISTUB with a Unified Kernel Image, Btrfs with Snapper, PipeWire, zram, and system services selected by the chosen profile.

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

## Desktop and software choices

### One native Dux 2.0 installation path

The desktop choice `dms` replaces the former DMS/DMS Manual split. It installs `dux-shell`, `dux-gop`, and the selected compositor/terminal stack from Arch repositories, plus the exact AUR targets `dux-greeter-bin` and `dux-search-bin`. It does not download or execute `dankinstall`.

Dux still names its command-line tool `dms`. Configuration is generated with `dms setup headless --compositor ... --terminal ... --force`, using the upstream Niri or Hyprland templates rather than a separate hand-maintained desktop configuration. See the [Dux 2.0 headless setup implementation](https://github.com/duxlabs-dev/dux-shell/blob/v2.0.0/core/cmd/dms/commands_setup_headless.go) and [configuration deployer](https://github.com/duxlabs-dev/dux-shell/blob/v2.0.0/core/internal/config/deployer.go).

The installer retains these customizations from the manual flow:

- The selected Ghostty, Kitty, or Alacritty terminal, browser shortcut, and file-manager shortcut. Bindings are added through `dms keybinds set`, retaining the upstream defaults. GUI file managers take precedence; Yazi-only selections launch in the selected terminal.
- User configuration ownership before greeter synchronization, greeter-group membership, and `dms-greeter sync -y`.
- `QT_QPA_PLATFORMTHEME=qt6ct`, case-correct `QS_ICON_THEME=Adwaita`, I2C access, and an `app-@autostart.service` drop-in ordered after `dms.service`.
- Dux Search indexing and compositor-specific user-service activation. A failed initial index can be rebuilt after login; missing required packages, units, or failed configuration stop service activation.

There is one intentional chroot adaptation: upstream setup cannot reach a user systemd manager there and falls back to direct shell startup. The installer removes that fallback and restores upstream systemd startup behavior, then creates the final service links only after required setup succeeds. This avoids starting Dux twice or enabling an incomplete session.

Dux uses its embedded shell fonts, `adw-gtk-theme`, and Qt multimedia runtime packages. General-purpose and CJK fonts remain wizard choices. No separate polkit agent or `cliphist` is added for Dux; Exo retains its `cliphist` dependency. `clipsync` is not installed.

### Desktop defaults

Graphical installations include File Roller, Loupe, mpv, and `mpv-mpris`. MIME defaults are derived from their installed desktop entries without overwriting existing user associations. Nautilus selections include GVFS, MTP/SMB support, and thumbnails; `ghostty-nautilus` is added only for a Dux/Ghostty/Nautilus combination. `nm-connection-editor` is excluded.

GNOME Keyring selections enable the packaged GCR SSH agent socket and set `SSH_AUTH_SOCK=${XDG_RUNTIME_DIR}/gcr/ssh` through `environment.d`, without a fixed UID. Fcitx GTK settings are merged into existing theme settings rather than appending duplicate `[Settings]` sections.

### Purpose-specific selections

| Purpose | Available additions |
| --- | --- |
| Media production | OBS Studio, Blender; individually selectable SoundCraft, FilmCraft, EffectCraft, PhotoCraft, VectorCraft, and LightCraft binary AUR packages |
| Industrial design | OpenSCAD, FreeCAD, OrcaSlicer, Bambu Studio, CADCraft; LCEDA Pro in CN |
| Software development | GitHub CLI, jq, uv, ShellCheck, oh-my-pi, and Node.js LTS via `nodejs-lts-krypton`, alongside the existing language/editor choices |
| Gaming and streaming | Gamescope, Protontricks, ProtonUp-Qt; UU accelerator in CN; optional Sunshine through its packaged user service |
| Virtualization | `virt-viewer`, stable `looking-glass` and `looking-glass-module-dkms`, and CPU-specific IOMMU boot parameters when GPU passthrough is selected |

ArtCraft applications are opt-in, not a bulk suite installation. OBS does not pull in `v4l2loopback-dkms` through this installer. GPU passthrough does not copy machine-specific PCI IDs or driver quirks; firmware settings, IOMMU groups, and guest setup still require hardware-specific validation.

For CN selections, Moegirl, oh-my-pi, RustDesk, Sunshine, OrcaSlicer, and LCEDA Pro use explicit `archlinuxcn/` targets after repository setup. Other regions use the configured AUR targets where offered, including binary RustDesk and Sunshine packages. The Sougou input dictionary remains a separate optional prebuilt download. Hidden or no-longer-applicable selections are cleared before configuration and installation.

### Edge and personal dotfiles

Selecting Edge writes its own `microsoft-edge-stable-flags.conf` with X11/XWayland, ANGLE OpenGL, Vulkan, and `VulkanFromANGLE` disabled. These flags are separate from Electron/VS Code Wayland flags. They preserve the requested WebGPU/WebGL workaround, but GPU behavior must still be checked on the target driver and hardware.

Personal configuration belongs in a separate chezmoi source repository, not in the public installer. The installer does not automatically import or apply a workstation's dotfiles, account state, credentials, display layouts, or hardware identifiers.

## Project structure

- `install.py` — stdlib-only live-ISO bootstrap.
- `arch_bootstrap/__main__.py` — full installer entry point.
- `arch_bootstrap/wizard.py` — multi-step localized TUI.
- `arch_bootstrap/config.py` — default config and wizard-to-`ArchConfig` conversion.
- `arch_bootstrap/disk.py` — partition/Btrfs model.
- `arch_bootstrap/installation.py` — destructive install and post-install orchestration.
- `arch_bootstrap/constants.py` — package/option data.
- `arch_bootstrap/packages.py` — optional-selection normalization and package-source routing.
- `arch_bootstrap/dms.py` — native Dux installation, official setup, and retained desktop customizations.
- `arch_bootstrap/i18n.py` — English, Simplified Chinese, and Japanese strings.
- `arch_bootstrap/archinstall_compat.py` — archinstall API compatibility boundary.
- `arch_bootstrap/scripts/uninstall-github-proxy-dl.sh` — standalone post-install download-proxy removal.
- `tests/test_dms_installers.py` — focused DMS behavior tests.
- `tests/test_package_selection.py` — conditional selections, source routing, and package dependencies.
- `tests/test_desktop_configuration.py` — shell activation, GTK/MIME preservation, and IOMMU parameters.
- `tests/test_github_proxy_uninstall.py` — configuration preservation and uninstall behavior tests.
- `.github/workflows/package.yml` — zipapp build and tagged release automation.

## Limitations

- The installer intentionally applies opinionated disk, boot, filesystem, package, and service choices.
- It depends on live network services, mirrors, package repositories, GitHub-hosted sources, and evolving `archinstall` APIs.
- Only part of the installation surface has automated unit coverage; disk and full installation behavior require disposable-machine testing.
- Hardware detection and third-party package availability can vary by machine, region, and time.
- Python 3.11 is insufficient for the current `wizard.py` syntax even if an older Arch ISO happens to provide it.

## License and attribution

The repository does not contain a license file in this checkout. No permission beyond applicable default copyright law should be inferred; obtain clarification from the repository owner before reuse or redistribution. Arch Linux and `archinstall` are upstream projects used by this installer and are not authored by this repository.
