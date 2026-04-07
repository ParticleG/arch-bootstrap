# Arch Bootstrap

<p align="center">

```
                -@                 ___           _          _     _
               .##@               / _ \         | |        | |   (_)
              .####@             / /_\ \_ __ ___| |__      | |    _ _ __  _   ___  __
              @#####@            |  _  | '__/ __| '_ \     | |   | | '_ \| | | \ \/ /
            . *######@           | | | | | | (__| | | |    | |___| | | | | |_| |>  <
           .##@o@#####@          \_| |_/_|  \___|_| |_|    \_____/_|_| |_|\__,_/_/\_\
          /############@
         /##############@        ______             _       _
        @######@**%######@       | ___ \           | |     | |
       @######`     %#####o      | |_/ / ___   ___ | |_ ___| |_ _ __ __ _ _ __
      @######@       ######%     | ___ \/ _ \ / _ \| __/ __| __| '__/ _` | '_ \
    -@#######h       ######@.`   | |_/ / (_) | (_) | |_\__ \ |_| | | (_| | |_) |
   /#####h**``       `**%@####@  \____/ \___/ \___/ \__|___/\__|_|  \__,_| .__/
  @H@*`                    `*%#@                                         | |
 *`                            `*                                        |_|
```

</p>

<p align="center">
  <strong>Opinionated Arch Linux installer powered by archinstall 4.1</strong>
</p>

<p align="center">
  <a href="https://github.com/ParticleG/arch-bootstrap/actions"><img src="https://github.com/ParticleG/arch-bootstrap/actions/workflows/package.yml/badge.svg" alt="Build"></a>
  <a href="https://github.com/ParticleG/arch-bootstrap/releases/latest"><img src="https://img.shields.io/github/v/release/ParticleG/arch-bootstrap?label=release" alt="Release"></a>
  <a href="https://github.com/ParticleG/arch-bootstrap/blob/main/LICENSE"><img src="https://img.shields.io/github/license/ParticleG/arch-bootstrap" alt="License"></a>
</p>

---

A 9-step TUI wizard that walks you through Arch Linux installation using archinstall's native Python API. No manual JSON editing required — the installer detects your hardware, guides you through options, and runs the installation directly.

## Quick Start

Boot the [Arch Linux ISO](https://archlinux.org/download/), connect to the network, then:

```bash
curl -sL https://raw.githubusercontent.com/ParticleG/arch-bootstrap/main/install.py | python
```

Or download the pre-built zipapp from [Releases](https://github.com/ParticleG/arch-bootstrap/releases/latest):

```bash
curl -LO https://github.com/ParticleG/arch-bootstrap/releases/latest/download/arch_bootstrap.pyz
python arch_bootstrap.pyz
```

> **CN users:** The bootstrap script automatically detects your region and routes GitHub downloads through a proxy (ghproxy.link / ghfast.top) for faster access.

## How It Works

`install.py` is a lightweight bootstrap script (stdlib only) that:

1. Reopens stdin from `/dev/tty` (for pipe-friendly `curl | python` usage)
2. Detects your country and applies fast mirrors to the live ISO
3. Upgrades `archinstall` to the latest version (the ISO ships an older one)
4. Downloads and runs the full installer (`arch_bootstrap.pyz`)

The full installer then:

1. **Auto-detects** your country (IP geolocation), GPU (`lspci`), and preferred disk
2. **Walks you through a 9-step wizard** with pre-selected defaults
3. Shows a **confirmation panel**: Install / Advanced Modify (archinstall GlobalMenu) / Cancel
4. Cleans up disk locks (swap, LVM, LUKS), formats the disk, installs Arch Linux
5. Presents **post-install options**: exit, reboot, or arch-chroot

## Wizard Steps

| # | Step | Description |
|---|------|-------------|
| 1 | Language | System locale (`en_US`, `zh_CN`, `ja_JP`); non-English adds `kmscon` |
| 2 | Region | Mirror country (auto-detected via IP); applies mirrors to live ISO immediately |
| 3 | Disk | Target block device with partition preview; confirms data destruction |
| 4 | Network | Backend choice: NetworkManager + iwd (recommended) or + wpa_supplicant |
| 5 | Repos | Optionally enable `multilib` (32-bit / Steam support) |
| 6 | GPU Drivers | Auto-detects vendor; choose from AMD / Intel / NVIDIA (open) / nouveau |
| 7 | Username | With format validation (`[a-z_][a-z0-9_-]*`) |
| 8 | User Password | Masked input via archinstall's `get_password()` |
| 9 | Root Password | Optional; prompted only if you choose to set one |

### Navigation

| Key | Action |
|-----|--------|
| Enter | Confirm / proceed |
| Esc | Go back to previous step |
| Arrow keys | Navigate menu items |
| Type to filter | Available in region selection |

## Opinionated Defaults

These are baked into every installation and are **not configurable** through the wizard:

| Option | Value |
|--------|-------|
| Bootloader | EFISTUB + Unified Kernel Image (UKI) |
| Filesystem | Btrfs with `zstd` compression + Snapper snapshots |
| Subvolumes | `@` `/`, `@home` `/home`, `@log` `/var/log`, `@pkg` `/var/cache/pacman/pkg` |
| Partitions | 1 GiB EFI (FAT32) + remaining space Btrfs |
| Audio | PipeWire |
| Bluetooth | Enabled |
| Power | tuned |
| Swap | zram (lzo-rle) |
| Base packages | `neovim`, `git`, `7zip`, `base-devel`, `zsh` |
| CN extras | `archlinuxcn` repo auto-added for CN region |

## Features

- **archinstall native TUI** — uses archinstall's textual-based Selection, Input, and Confirmation components
- **Auto-detection** — IP geolocation for mirror region, `lspci` for GPU vendor (NVIDIA Turing+ detection via PCI Device ID), `lsblk` for target disks
- **Smart mirrors** — per-country fallback mirror pools (CN, US, JP, DE); applied to live ISO before any `pacman` operation
- **i18n** — English, Simplified Chinese, and Japanese (auto-fallback to English on raw TTY where CJK cannot render)
- **Advanced escape hatch** — archinstall's GlobalMenu available from the confirmation panel for full manual override
- **Pipe-friendly** — designed for `curl | python` with automatic stdin recovery from `/dev/tty`
- **GitHub proxy for CN** — auto-detects China region and routes `.pyz` downloads through ghproxy.link / ghfast.top

## Requirements

| Dependency | Notes |
|------------|-------|
| Python 3.11+ | Pre-installed on Arch ISO |
| archinstall 4.1+ | Auto-upgraded by the bootstrap script |
| pciutils (`lspci`) | Pre-installed on Arch ISO |
| Root privileges | Required |
| Network connection | Required for mirrors and packages |

## Development

Run from source:

```bash
git clone https://github.com/ParticleG/arch-bootstrap.git
cd arch-bootstrap
python install.py
```

Or invoke the package directly:

```bash
python -m arch_bootstrap
```

Build the zipapp manually:

```bash
mkdir -p _staging
cp -r arch_bootstrap _staging/arch_bootstrap
printf 'from arch_bootstrap.__main__ import main\nmain()\n' > _staging/__main__.py
python -m zipapp _staging -o arch_bootstrap.pyz -p '/usr/bin/env python3'
```

## Project Structure

```
arch-bootstrap/
├── install.py              # Bootstrap script (stdlib only, pipe-friendly)
├── arch_bootstrap/         # Main Python package
│   ├── __init__.py         # Version (0.2.0)
│   ├── __main__.py         # Entry point: detect → wizard → install
│   ├── config.py           # ArchConfig builder
│   ├── constants.py        # GPU maps, mirrors, languages, countries
│   ├── detection.py        # Hardware & environment detection
│   ├── disk.py             # Btrfs disk layout builder
│   ├── i18n.py             # Trilingual translations (en/zh/ja)
│   ├── installation.py     # archinstall API integration
│   ├── mirrors.py          # Mirror resolution & fallback
│   └── wizard.py           # 9-step interactive wizard
└── .github/
    └── workflows/
        └── package.yml     # CI: build .pyz + GitHub Release
```

## License

See [LICENSE](LICENSE) for details.
