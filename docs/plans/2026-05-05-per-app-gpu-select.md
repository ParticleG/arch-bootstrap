# Per-App GPU Selection Tool — Plan

## Problem

Linux lacks a unified, persistent per-app GPU selection mechanism equivalent to Windows NVIDIA Control Panel. Users with hybrid GPU laptops (iGPU + dGPU) need to control which GPU each application uses at launch, especially when preparing for GPU passthrough.

## Current State of the Art

- **`.desktop` file `PrefersNonDefaultGPU=true`** — binary choice, only for DE-launched apps
- **KDE KMenuEdit** — persistent checkbox in Plasma 6.4+, KDE only
- **`switcherooctl`** — per-invocation, not persistent
- **`prime-run` / env vars** — manual, not persistent
- **`RunAsGPU`** (github.com/BC100Dev/RunAsGPU) — closest existing tool, but requires launching through it

**Gap:** No tool provides a config-file-based mapping of app names/patterns → GPU env vars that is honored regardless of launch method (CLI, DE, systemd, etc.).

## Proposed Solution

A lightweight tool (`gpu-select` or similar) that:

1. **Config file** (`~/.config/gpu-select/apps.toml` or system-wide `/etc/gpu-select/apps.toml`):
   ```toml
   [defaults]
   gpu = "igpu"  # default for unlisted apps

   [[rules]]
   match = "blender"  # match by process name or .desktop app-id
   gpu = "dgpu"

   [[rules]]
   match = "code"     # VSCode
   gpu = "igpu"

   [[rules]]
   match = "steam"
   gpu = "dgpu"

   [[rules]]
   match = "electron*"  # glob pattern
   gpu = "igpu"
   ```

2. **Integration methods** (in order of preference):
   - **`.desktop` file generator**: reads config, generates/updates user-local `.desktop` overrides with correct `Exec=env ...` prefixes
   - **Shell wrapper/alias generator**: outputs shell config for CLI launches
   - **niri/Hyprland exec rules**: compositor-level env var injection per window rule (if compositor supports it)

3. **CLI interface**:
   ```bash
   gpu-select list                    # show configured apps
   gpu-select set blender dgpu       # set preference
   gpu-select set "electron*" igpu   # glob pattern
   gpu-select run blender            # launch with configured GPU
   gpu-select apply                  # regenerate .desktop overrides and shell aliases
   gpu-select detect                 # auto-detect GPUs and show env vars for each
   ```

4. **GPU passthrough integration**: `gpu-hotswitch-vfio on` could call `gpu-select check` before proceeding, warning about apps configured to use dGPU that are currently running.

## Architecture Considerations

- **Python script** (can be bundled in arch-bootstrap's zipapp or standalone)
- Uses `switcherooctl list` output to detect GPUs and their env vars
- Generates env var sets based on the hardware:
  - `igpu`: `DRI_PRIME=0` or nothing (default)
  - `dgpu`: `__NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia ...` (from switcherooctl)
- `.desktop` overrides go to `~/.local/share/applications/`
- Shell aliases go to `~/.config/gpu-select/env.sh` (sourced from shell rc)

## Non-Goals (for now)

- GUI configuration panel (can be added later)
- Runtime GPU migration (impossible on Linux)
- Automatic detection of which apps "should" use dGPU
- Per-launch override UI in compositor (compositor-specific)

## Dependencies

- `switcheroo-control` (for GPU detection and env var generation)
- Python 3.11+ (stdlib only for core functionality)

## Integration with arch-bootstrap

- Install `switcheroo-control` and enable `switcheroo-control.service` when GPU passthrough is selected
- Optionally install the `gpu-select` tool
- Pre-configure sensible defaults (electron/chromium → iGPU, games → dGPU)

## References

- [NVIDIA PRIME Render Offload docs](https://download.nvidia.com/XFree86/Linux-x86_64/550.142/README/primerenderoffload.html)
- [FreeDesktop .desktop spec — PrefersNonDefaultGPU](https://specifications.freedesktop.org/desktop-entry-spec/latest/)
- [switcheroo-control](https://gitlab.freedesktop.org/hadess/switcheroo-control)
- [RunAsGPU](https://github.com/BC100Dev/RunAsGPU) — existing similar tool
- [COSMIC settings GPU issue](https://github.com/pop-os/cosmic-settings/issues/1680)
