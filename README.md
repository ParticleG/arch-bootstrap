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
  <strong>Interactive configuration generator for archinstall 4.1</strong>
</p>

<p align="center">
  <a href="https://github.com/ParticleG/arch-bootstrap/actions"><img src="https://github.com/ParticleG/arch-bootstrap/actions/workflows/package.yml/badge.svg" alt="Build"></a>
  <a href="https://github.com/ParticleG/arch-bootstrap/releases/latest"><img src="https://img.shields.io/github/v/release/ParticleG/arch-bootstrap?label=release" alt="Release"></a>
  <a href="https://github.com/ParticleG/arch-bootstrap/blob/main/LICENSE"><img src="https://img.shields.io/github/license/ParticleG/arch-bootstrap" alt="License"></a>
</p>

---

A full-screen TUI wizard that walks you through Arch Linux installation options for **archinstall 4.1**. No manual JSON editing required.

> **Two interfaces:** a Bash-based config generator (`install.sh`) and a Python-based
> direct installer (`arch_bootstrap.py`). The Python version uses archinstall's native
> TUI and API — no JSON files needed; installation runs directly.

## Python Installer (`arch_bootstrap.py`)

### Usage on Arch ISO

Boot the [Arch Linux ISO](https://archlinux.org/download/), connect to the network, then:

```bash
# Download and run (must be root — which you are on the ISO)
curl -LO https://raw.githubusercontent.com/ParticleG/arch-bootstrap/main/arch_bootstrap.py
python arch_bootstrap.py
```

Or clone and run:

```bash
git clone https://github.com/ParticleG/arch-bootstrap.git
cd arch-bootstrap
python arch_bootstrap.py
```

The script will:

1. Auto-upgrade `archinstall` to the latest version (the ISO ships an older version)
2. Detect your country (IP geolocation), GPU (`lspci`), and preferred disk
3. Walk you through a **9-step wizard** with pre-selected defaults
4. Show a confirmation panel: **Install** / **Advanced Modify** (archinstall GlobalMenu) / **Cancel**
5. Clean up disk locks (swap, LVM, LUKS), format the disk, install Arch Linux
6. Present post-install options: exit, reboot, or arch-chroot

### Wizard Navigation

| Key | Action |
|-----|--------|
| Enter | Confirm / proceed |
| Esc / Skip | Go back to previous step |
| Arrow keys | Navigate menu items |
| Type to filter | Available in region selection |

### Differences from the Bash version

| | Bash (`install.sh`) | Python (`arch_bootstrap.py`) |
|-|---------------------|------------------------------|
| Output | JSON files + `archinstall --config` | Direct archinstall Python API |
| TUI | fzf with preview panels | archinstall's textual TUI |
| Advanced editing | N/A | GlobalMenu escape hatch |
| Disk cleanup | Manual umount/swapoff | Automatic (swap, LVM, LUKS) |
| Post-install | 30s auto-reboot countdown | Choose: exit / reboot / chroot |

### Requirements (ISO environment)

| Dependency | Notes |
|------------|-------|
| Python 3.11+ | Pre-installed on Arch ISO |
| archinstall 4.1+ | Auto-upgraded at script startup |
| pciutils (`lspci`) | Pre-installed on Arch ISO |
| Root privileges | Required |
| Network connection | Required for mirrors and packages |

## Features

- **10-step guided wizard** — language, region, disk, network, repos, GPU drivers, user accounts, and final confirmation
- **fzf-powered TUI** — fuzzy search, multi-select checklists, masked password input, and a live progress sidebar
- **Auto-detection** — IP geolocation for mirror region, `lspci` for GPU vendor, `lsblk` for target disks
- **Smart mirrors** — `reflector` speed-test with per-country fallback pools; `archlinuxcn` repo auto-added for CN users
- **i18n** — English, Simplified Chinese, and Japanese (auto-fallback to English on raw TTY for CJK rendering)
- **Wizard navigation** — `Esc` to go back, `Ctrl-C` to abort, with full step history
- **Self-extracting archive** — CI builds a single `.sh` file via `makeself` for easy distribution

## Bash Config Generator (`install.sh`)

### One-liner

```bash
curl -sL https://github.com/ParticleG/arch-bootstrap/releases/latest/download/bootstrap.sh | bash
```

### From source

```bash
git clone https://github.com/ParticleG/arch-bootstrap.git
cd arch-bootstrap
sudo bash install.sh
```

After the wizard completes, run archinstall with the generated files:

```bash
archinstall --config user_configuration.json --creds user_credentials.json
```

## Wizard Steps

| # | Step | Description |
|---|------|-------------|
| 1 | Language | System locale (`en_US`, `zh_CN`, `ja_JP`); non-English adds `kmscon` |
| 2 | Region | Mirror country (auto-detected via IP), triggers `reflector` speed test |
| 3 | Disk | Target block device; auto-calculates EFI (1 GiB) + Btrfs partition |
| 4 | Network | Backend choice: NetworkManager + iwd or + wpa_supplicant |
| 5 | Repos | Optionally enable `multilib` (32-bit / Steam support) |
| 6 | GPU Drivers | Auto-detects vendor; choose from AMD / Intel / NVIDIA / nouveau |
| 7 | Username | With format validation (`[a-z_][a-z0-9_-]*`) |
| 8 | User Password | Masked input via fzf |
| 9 | Root Password | Masked input (may be left empty) |
| 10 | Confirm | Review summary, then generate JSON |

## Opinionated Defaults

These are baked into every generated configuration and are not configurable through the wizard:

| Option | Value |
|--------|-------|
| Bootloader | EFISTUB + Unified Kernel Image (UKI) |
| Filesystem | Btrfs with `zstd` compression + Snapper snapshots |
| Subvolumes | `@` `/`, `@home` `/home`, `@log` `/var/log`, `@pkg` `/var/cache/pacman/pkg` |
| Audio | PipeWire |
| Bluetooth | Enabled |
| Power | tuned |
| Base packages | `neovim`, `git`, `7zip`, `base-devel`, `zsh` |

## Project Structure

```
arch-bootstrap/
├── arch_bootstrap.py       # Python installer (direct archinstall API)
├── install.sh              # Bash entry point — wizard + JSON generation
├── lib/
│   ├── ui.sh               # TUI engine (fzf integration, ANSI, logging)
│   ├── config.sh            # Pure data (packages, GPU maps, mirrors)
│   ├── wizard.sh            # Step registration & navigation engine
│   ├── generate.sh          # JSON generation for archinstall
│   └── i18n/
│       ├── en.sh            # English (authoritative key set)
│       ├── zh.sh            # Simplified Chinese
│       └── ja.sh            # Japanese
├── scripts/
│   └── bootstrap.sh         # Remote one-liner bootstrap script
└── .github/
    └── workflows/
        └── package.yml      # CI: makeself packaging + GitHub Releases
```

## Requirements (Bash version)

| Dependency | Purpose |
|------------|---------|
| `bash` 4.0+ | Associative arrays |
| `fzf` | TUI menus (auto-installed if missing) |
| `curl` | IP geolocation + downloads |
| `openssl` | SHA-512 password hashing |
| `lsblk` / `blockdev` | Disk enumeration |
| `reflector` | Mirror speed test (graceful fallback if unavailable) |
| `archinstall` 4.1 | Final installation executor |
| Root privileges | Required to run |

## License

See [LICENSE](LICENSE) for details.
