#!/usr/bin/env bash
# gpu-passthrough - Hot-switch GPU passthrough for KVM virtual machines
# Usage: gpu-passthrough {on|off|status}
#
# Automatically detects discrete GPU (NVIDIA or AMD) and manages:
# - Driver unbinding/rebinding
# - VFIO-PCI binding
# - Hugepage allocation/release

set -euo pipefail

# --- Auto-detection functions ---

detect_dgpu() {
    # Find discrete GPU (NVIDIA vendor 10de, AMD vendor 1002 on non-root PCI bus)
    local gpu_type=""
    local pci_addrs=()

    # Check for NVIDIA
    local nvidia_addrs
    nvidia_addrs=$(lspci -D -nn | grep -i '10de:' | grep -Ei 'VGA|3D|Display|Audio' | awk '{print $1}' || true)
    if [[ -n "$nvidia_addrs" ]]; then
        gpu_type="nvidia"
        while IFS= read -r addr; do
            pci_addrs+=("$addr")
        done <<< "$nvidia_addrs"
    fi

    # Check for AMD discrete (bus != 00, to exclude iGPU)
    if [[ -z "$gpu_type" ]]; then
        local amd_addrs
        amd_addrs=$(lspci -D -nn | grep -i '1002:' | grep -Ei 'VGA|3D|Display|Audio' | grep -v '^0000:00:' | awk '{print $1}' || true)
        if [[ -n "$amd_addrs" ]]; then
            gpu_type="amd"
            while IFS= read -r addr; do
                pci_addrs+=("$addr")
            done <<< "$amd_addrs"
        fi
    fi

    if [[ -z "$gpu_type" ]]; then
        echo "ERROR: No discrete GPU detected" >&2
        return 1
    fi

    echo "$gpu_type"
    printf '%s\n' "${pci_addrs[@]}"
}

get_iommu_group_devices() {
    # Given a PCI address, find all devices in the same IOMMU group
    local pci_addr="$1"
    local iommu_group
    iommu_group=$(basename "$(readlink /sys/bus/pci/devices/"$pci_addr"/iommu_group)")

    for dev in /sys/kernel/iommu_groups/"$iommu_group"/devices/*; do
        basename "$dev"
    done
}

get_current_driver() {
    local pci_addr="$1"
    local driver_link="/sys/bus/pci/devices/$pci_addr/driver"
    if [[ -L "$driver_link" ]]; then
        basename "$(readlink "$driver_link")"
    else
        echo "none"
    fi
}

# --- Hugepage management ---

get_total_ram_gb() {
    awk '/MemTotal/ {printf "%d", $2 / 1024 / 1024}' /proc/meminfo
}

allocate_hugepages() {
    local total_ram_gb
    total_ram_gb=$(get_total_ram_gb)
    local vm_mem_gb=$(( total_ram_gb / 2 ))

    echo "Allocating hugepages for ${vm_mem_gb}GB VM memory..."

    # Flush caches and compact memory
    sync
    echo 3 > /proc/sys/vm/drop_caches
    echo 1 > /proc/sys/vm/compact_memory

    if (( total_ram_gb >= 32 )); then
        # Use 1GB hugepages — allocate incrementally to avoid system freeze
        local nr_pages=$vm_mem_gb
        echo "Using 1GB hugepages: target ${nr_pages} pages (allocating incrementally)..."

        local current=0
        local batch=4  # allocate 4GB at a time
        while (( current < nr_pages )); do
            local target=$(( current + batch ))
            if (( target > nr_pages )); then
                target=$nr_pages
            fi
            echo "$target" > /sys/kernel/mm/hugepages/hugepages-1048576kB/nr_hugepages
            current=$(cat /sys/kernel/mm/hugepages/hugepages-1048576kB/nr_hugepages)
            echo "  Allocated: ${current}/${nr_pages} x 1GB hugepages"
            if (( current < target )); then
                echo "  WARNING: Could only allocate ${current} pages (fragmentation?)"
                break
            fi
            # Brief pause to let system breathe
            sleep 0.2
        done

        echo "Allocated: ${current} x 1GB hugepages"
    else
        # Use 2MB hugepages
        local nr_pages=$(( vm_mem_gb * 1024 / 2 ))
        echo "Using 2MB hugepages: ${nr_pages} pages"
        sysctl -w vm.nr_hugepages="$nr_pages" > /dev/null
        local actual
        actual=$(cat /proc/sys/vm/nr_hugepages)
        echo "Allocated: ${actual} x 2MB hugepages"
    fi
}

release_hugepages() {
    local total_ram_gb
    total_ram_gb=$(get_total_ram_gb)

    echo "Releasing hugepages..."

    if (( total_ram_gb >= 32 )); then
        echo 0 > /sys/kernel/mm/hugepages/hugepages-1048576kB/nr_hugepages
    fi
    sysctl -w vm.nr_hugepages=0 > /dev/null

    echo "Hugepages released"
}

# --- GPU passthrough control ---

# Ensure running compositor ignores dGPU DRM devices and renders on iGPU.
# Currently supports niri; extend for other compositors if needed.
configure_compositor_ignore_dgpu() {
    local -a gpu_pci_slots=("$@")

    # Only handle niri for now
    pgrep -x niri &>/dev/null || return 0

    # Find niri config for the user who owns the niri process
    local niri_pid niri_user niri_config
    niri_pid=$(pgrep -x niri | head -1)
    niri_user=$(stat -c '%U' "/proc/$niri_pid" 2>/dev/null || echo "")
    [[ -n "$niri_user" ]] || return 0

    if [[ "$niri_user" == "root" ]]; then
        niri_config="/root/.config/niri/config.kdl"
    else
        niri_config="/home/$niri_user/.config/niri/config.kdl"
    fi

    [[ -f "$niri_config" ]] || return 0

    local changed=false

    # Build the lines to insert
    local -a new_lines=()

    # --- Set render-drm-device to iGPU (non-dGPU render device) ---
    if ! grep -q 'render-drm-device' "$niri_config" 2>/dev/null; then
        local igpu_render=""
        for rdev in /dev/dri/by-path/*-render; do
            [[ -e "$rdev" ]] || continue
            local is_dgpu=false
            for slot in "${gpu_pci_slots[@]}"; do
                local base_slot="${slot%.*}.0"
                if [[ "$rdev" == *"$base_slot"* ]]; then
                    is_dgpu=true
                    break
                fi
            done
            if [[ "$is_dgpu" == "false" ]]; then
                igpu_render="$rdev"
                break
            fi
        done

        if [[ -n "$igpu_render" ]]; then
            new_lines+=("    render-drm-device \"$igpu_render\"")
            echo "  Set render-drm-device to $igpu_render"
        fi
    fi

    # --- Add ignore-drm-device for each dGPU PCI slot ---
    for slot in "${gpu_pci_slots[@]}"; do
        local base_slot="${slot%.*}.0"
        local card_path="/dev/dri/by-path/pci-${base_slot}-card"
        local render_path="/dev/dri/by-path/pci-${base_slot}-render"

        if ! grep -qF "$card_path" "$niri_config" 2>/dev/null; then
            new_lines+=("    ignore-drm-device \"$card_path\"")
            new_lines+=("    ignore-drm-device \"$render_path\"")
            echo "  Added ignore-drm-device for $base_slot"
        fi
    done

    if [[ ${#new_lines[@]} -eq 0 ]]; then
        echo "  Compositor config already up to date"
        return 0
    fi

    # Insert lines into the debug {} block using a temp file (avoids sed escaping issues)
    local tmpfile
    tmpfile=$(mktemp)
    local inserted=false
    while IFS= read -r line; do
        echo "$line" >> "$tmpfile"
        if [[ "$inserted" == "false" ]] && [[ "$line" =~ ^[[:space:]]*debug[[:space:]]*\{ ]]; then
            for nl in "${new_lines[@]}"; do
                echo "$nl" >> "$tmpfile"
            done
            inserted=true
        fi
    done < "$niri_config"

    if [[ "$inserted" == "false" ]]; then
        # No debug {} block found, append one
        echo "" >> "$tmpfile"
        echo "debug {" >> "$tmpfile"
        for nl in "${new_lines[@]}"; do
            echo "$nl" >> "$tmpfile"
        done
        echo "}" >> "$tmpfile"
    fi

    cp "$tmpfile" "$niri_config"
    rm -f "$tmpfile"
    changed=true

    if [[ "$changed" == "true" ]]; then
        echo "  Reloading niri config..."
        if command -v niri &>/dev/null; then
            runuser -l "$niri_user" -c 'niri msg action do-screen-transition && niri msg reload' 2>/dev/null || true
        fi
    fi
}

# Safely kill processes using /dev/nvidia* without killing compositor/desktop sessions.
# Shows user a list and asks for confirmation. Uses SIGTERM first, then SIGKILL.
safe_kill_nvidia_users() {
    # Collect PIDs using /dev/nvidia*
    local -a pids=()
    local raw
    raw=$(fuser /dev/nvidia* 2>/dev/null) || true
    for p in $raw; do
        # strip trailing access mode chars (e.g. "1234m")
        p="${p%%[a-zA-Z]*}"
        [[ -n "$p" ]] && pids+=("$p")
    done

    if [[ ${#pids[@]} -eq 0 ]]; then
        return 0
    fi

    # Compositors / desktop sessions we must never kill
    local -a protected_re=(
        'niri' 'hyprland' 'sway' 'kwin' 'gnome-shell' 'mutter'
        'weston' 'labwc' 'wayfire' 'Xorg' 'Xwayland'
        'xwayland-satellite' 'quickshell' 'dms-shell'
        'gdm' 'sddm' 'greetd' 'tuigreet' 'login'
    )
    local re
    re=$(IFS='|'; echo "${protected_re[*]}")

    # Categorize processes
    local -a killable_pids=()
    local -a killable_names=()

    for pid in "${pids[@]}"; do
        local comm
        comm=$(cat "/proc/$pid/comm" 2>/dev/null || echo "")
        if [[ -z "$comm" ]]; then
            continue
        fi
        if echo "$comm" | grep -qEi "($re)"; then
            echo "  Protected (will not kill): $comm (PID $pid)"
            continue
        fi
        killable_pids+=("$pid")
        killable_names+=("$comm")
    done

    if [[ ${#killable_pids[@]} -eq 0 ]]; then
        return 0
    fi

    # Display processes and ask for confirmation
    echo ""
    echo "  The following processes are using the NVIDIA GPU:"
    echo "  ─────────────────────────────────────────────────"
    for i in "${!killable_pids[@]}"; do
        local pid="${killable_pids[$i]}"
        local comm="${killable_names[$i]}"
        local cmdline
        cmdline=$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null | head -c 80 || echo "")
        printf "    [%d] %s (PID %s)\n" "$((i+1))" "$comm" "$pid"
        if [[ -n "$cmdline" && "$cmdline" != "$comm "* ]]; then
            printf "        %s\n" "$cmdline"
        fi
    done
    echo ""

    # If running non-interactively (no tty), kill without asking
    if [[ ! -t 0 ]]; then
        echo "  Non-interactive mode: terminating all GPU users..."
    else
        echo -n "  Terminate these processes to proceed? [Y/n] "
        local answer
        read -r answer < /dev/tty
        if [[ "$answer" =~ ^[Nn] ]]; then
            echo "  Aborted by user."
            return 1
        fi
    fi

    # SIGTERM first (graceful shutdown)
    echo "  Sending SIGTERM..."
    for pid in "${killable_pids[@]}"; do
        kill -TERM "$pid" 2>/dev/null || true
    done

    # Wait up to 5 seconds for graceful exit
    local waited=0
    while (( waited < 5 )); do
        local still_running=false
        for pid in "${killable_pids[@]}"; do
            if [[ -d "/proc/$pid" ]]; then
                still_running=true
                break
            fi
        done
        if [[ "$still_running" == "false" ]]; then
            echo "  All processes exited gracefully."
            return 0
        fi
        sleep 1
        waited=$(( waited + 1 ))
    done

    # SIGKILL remaining
    echo "  Some processes didn't exit, sending SIGKILL..."
    for pid in "${killable_pids[@]}"; do
        if [[ -d "/proc/$pid" ]]; then
            local comm
            comm=$(cat "/proc/$pid/comm" 2>/dev/null || echo "PID $pid")
            echo "    Force killing: $comm (PID $pid)"
            kill -9 "$pid" 2>/dev/null || true
        fi
    done
    sleep 0.5
}

passthrough_on() {
    echo "=== Enabling GPU passthrough ==="

    # Detect GPU
    local detection
    detection=$(detect_dgpu)
    local gpu_type
    gpu_type=$(echo "$detection" | head -1)
    local -a gpu_addrs
    mapfile -t gpu_addrs < <(echo "$detection" | tail -n +2)

    echo "Detected ${gpu_type} GPU at: ${gpu_addrs[*]}"

    # Configure compositor to ignore dGPU DRM devices BEFORE killing anything
    echo "Ensuring compositor ignores dGPU..."
    configure_compositor_ignore_dgpu "${gpu_addrs[@]}"

    # Collect ALL IOMMU group devices
    local -a all_devices=()
    local -A seen_devices=()
    for addr in "${gpu_addrs[@]}"; do
        while IFS= read -r dev; do
            if [[ -z "${seen_devices[$dev]:-}" ]]; then
                all_devices+=("$dev")
                seen_devices[$dev]=1
            fi
        done < <(get_iommu_group_devices "$addr")
    done

    echo "IOMMU group devices: ${all_devices[*]}"

    if [[ ${#all_devices[@]} -eq 0 ]]; then
        echo "ERROR: No IOMMU group devices found. Cannot proceed." >&2
        return 1
    fi

    case "$gpu_type" in
        nvidia)
            # Retry loop: kill GPU users, then try to unload modules.
            # Some processes respawn or take time to release the device.
            local max_attempts=5
            local attempt=0
            while (( attempt < max_attempts )); do
                attempt=$(( attempt + 1 ))
                echo "Attempt $attempt/$max_attempts: stopping NVIDIA GPU users..."
                if ! safe_kill_nvidia_users; then
                    echo "Aborted."
                    return 1
                fi

                echo "Unloading NVIDIA modules..."
                for mod in nvidia_drm nvidia_modeset nvidia_uvm nvidia; do
                    rmmod "$mod" 2>/dev/null || true
                done

                if ! lsmod | grep -q '^nvidia'; then
                    echo "NVIDIA modules unloaded successfully."
                    break
                fi

                if (( attempt < max_attempts )); then
                    echo "  Modules still loaded, retrying in 2s..."
                    # Show what's still holding the device
                    fuser -v /dev/nvidia* 2>/dev/null || true
                    sleep 2
                fi
            done

            if lsmod | grep -q '^nvidia'; then
                echo "WARNING: nvidia module still loaded after $max_attempts attempts."
                echo "  Remaining users:"
                fuser -v /dev/nvidia* 2>/dev/null || true
                echo "  Proceeding with forced unbind via sysfs..."
            fi
            ;;
        amd)
            echo "Unloading AMD GPU module..."
            rmmod amdgpu 2>/dev/null || true
            ;;
    esac

    # Unbind all devices from current drivers
    echo "Unbinding devices from current drivers..."
    for dev in "${all_devices[@]}"; do
        local current_driver
        current_driver=$(get_current_driver "$dev")
        if [[ "$current_driver" == "none" || "$current_driver" == "vfio-pci" ]]; then
            continue
        fi
        # Skip if the driver module was already removed (device auto-unbound)
        if [[ ! -d "/sys/bus/pci/drivers/$current_driver" ]]; then
            echo "  $dev: driver $current_driver already removed, skipping"
            continue
        fi
        echo "  Unbinding $dev from $current_driver"
        # Use timeout to avoid hanging on kernel deadlocks
        timeout 5 bash -c "echo '$dev' > '/sys/bus/pci/drivers/$current_driver/unbind'" 2>/dev/null || {
            echo "  WARNING: unbind of $dev timed out or failed (may already be unbound)"
        }
    done

    # Load vfio-pci and bind devices
    echo "Loading vfio-pci module..."
    modprobe vfio-pci

    echo "Binding devices to vfio-pci..."
    for dev in "${all_devices[@]}"; do
        timeout 5 bash -c "echo 'vfio-pci' > '/sys/bus/pci/devices/$dev/driver_override'" || {
            echo "  ERROR: Failed to set driver_override for $dev" >&2
            return 1
        }
        timeout 5 bash -c "echo '$dev' > /sys/bus/pci/drivers_probe" || {
            echo "  ERROR: Failed to probe $dev" >&2
            return 1
        }
    done

    # Allocate hugepages
    allocate_hugepages

    echo "=== GPU passthrough enabled ==="
    echo "You can now start your VM with GPU passthrough."
}

passthrough_off() {
    echo "=== Disabling GPU passthrough ==="

    # Detect GPU type
    local detection
    detection=$(detect_dgpu 2>/dev/null) || true
    local gpu_type

    # If detection fails (GPU bound to vfio), try to determine from loaded modules
    if [[ -z "$detection" ]]; then
        # Check vfio-bound devices to determine GPU type
        for dev in /sys/bus/pci/drivers/vfio-pci/*/; do
            local pci_addr
            pci_addr=$(basename "$dev")
            [[ "$pci_addr" =~ ^[0-9a-fA-F]{4}: ]] || continue
            local vendor
            vendor=$(cat "/sys/bus/pci/devices/$pci_addr/vendor" 2>/dev/null || echo "")
            case "$vendor" in
                0x10de) gpu_type="nvidia"; break ;;
                0x1002) gpu_type="amd"; break ;;
            esac
        done
    else
        gpu_type=$(echo "$detection" | head -1)
    fi

    if [[ -z "${gpu_type:-}" ]]; then
        echo "ERROR: Cannot determine GPU type" >&2
        return 1
    fi

    # Find all vfio-pci bound devices
    local -a vfio_devices=()
    for dev_path in /sys/bus/pci/drivers/vfio-pci/*/; do
        [[ -d "$dev_path" ]] || continue
        local pci_addr
        pci_addr=$(basename "$dev_path")
        # Skip non-PCI entries like "module"
        [[ "$pci_addr" =~ ^[0-9a-fA-F]{4}: ]] || continue
        # Only process GPU-related devices (vendor 10de or 1002)
        local vendor
        vendor=$(cat "/sys/bus/pci/devices/$pci_addr/vendor" 2>/dev/null || echo "")
        if [[ "$vendor" == "0x10de" || "$vendor" == "0x1002" ]]; then
            vfio_devices+=("$pci_addr")
        fi
    done

    # Clear driver overrides and unbind from vfio-pci
    echo "Unbinding devices from vfio-pci..."
    for dev in "${vfio_devices[@]}"; do
        timeout 5 bash -c "echo '' > '/sys/bus/pci/devices/$dev/driver_override'" 2>/dev/null || true
        timeout 5 bash -c "echo '$dev' > /sys/bus/pci/drivers/vfio-pci/unbind" 2>/dev/null || true
    done

    # Reload original driver
    case "$gpu_type" in
        nvidia)
            echo "Reloading NVIDIA modules..."
            modprobe nvidia
            modprobe nvidia_drm
            modprobe nvidia_modeset
            modprobe nvidia_uvm
            ;;
        amd)
            echo "Reloading AMD GPU module..."
            modprobe amdgpu
            ;;
    esac

    # Reprobe devices
    echo "Reprobing devices..."
    for dev in "${vfio_devices[@]}"; do
        timeout 5 bash -c "echo '$dev' > /sys/bus/pci/drivers_probe" 2>/dev/null || true
    done

    # Release hugepages
    release_hugepages

    echo "=== GPU passthrough disabled ==="
}

passthrough_status() {
    echo "=== GPU Passthrough Status ==="

    # Show GPU devices and their current drivers
    echo ""
    echo "GPU Devices:"
    lspci -D -nn -k 2>/dev/null | grep -A 2 -Ei 'VGA|3D|Display' | head -30

    echo ""
    echo "VFIO-PCI bound devices:"
    if [[ -d /sys/bus/pci/drivers/vfio-pci ]]; then
        for dev_path in /sys/bus/pci/drivers/vfio-pci/*/; do
            [[ -d "$dev_path" ]] || { echo "  (none)"; break; }
            local pci_addr
            pci_addr=$(basename "$dev_path")
            # Skip non-PCI entries like "module"
            [[ "$pci_addr" =~ ^[0-9a-fA-F]{4}: ]] || continue
            echo "  $pci_addr: $(lspci -s "${pci_addr#*:}" 2>/dev/null || echo 'unknown')"
        done
    else
        echo "  vfio-pci module not loaded"
    fi

    echo ""
    echo "Hugepages:"
    echo "  2MB: $(cat /proc/sys/vm/nr_hugepages) allocated"
    if [[ -f /sys/kernel/mm/hugepages/hugepages-1048576kB/nr_hugepages ]]; then
        echo "  1GB: $(cat /sys/kernel/mm/hugepages/hugepages-1048576kB/nr_hugepages) allocated"
    fi

    echo ""
    echo "Total RAM: $(get_total_ram_gb) GB"
}

# --- Main ---

if [[ $EUID -ne 0 ]]; then
    echo "ERROR: This script must be run as root (use sudo)" >&2
    exit 1
fi

case "${1:-}" in
    on)  passthrough_on ;;
    off) passthrough_off ;;
    status) passthrough_status ;;
    *)
        echo "Usage: gpu-passthrough {on|off|status}" >&2
        exit 1
        ;;
esac
