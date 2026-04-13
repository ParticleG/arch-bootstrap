# Virtual Machine (KVM) Device Purpose Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `virtual_machine` device purpose to arch-bootstrap that installs KVM/QEMU, configures GPU hot-switch passthrough (NVIDIA + AMD), and sets up LookingGlass with KVMFR.

**Architecture:** Follows the existing device purpose pattern (`development`/`gaming`): constants define options → wizard step collects user choices → config.py collects packages → installation.py installs packages, enables services, writes config files, and generates scripts. GPU passthrough detection leverages existing `detect_gpu()` infrastructure.

**Tech Stack:** Python 3, arch-bootstrap TUI framework (Selection/MenuItem), systemd, libvirt/QEMU, vfio-pci, KVMFR kernel module

**References:**
- KVM guide: https://github.com/SHORiN-KiWATA/Shorin-ArchLinux-Guide/wiki/KVM虚拟机
- Hot-switch guide: https://github.com/SHORiN-KiWATA/Shorin-ArchLinux-Guide/wiki/热切换显卡直通
- LookingGlass KVMFR: https://looking-glass.io/docs/B7/ivshmem_kvmfr/

**Design Decisions:**
| Decision | Result |
|----------|--------|
| GPU passthrough behavior | Auto pre-select when dGPU detected; user can deselect |
| Hugepage management | Included in hot-switch script; 1GB hugepages when RAM >= 32GB, else 2MB |
| GPU vendor support | NVIDIA + AMD |
| LookingGlass shared memory | Fixed 512MB (no user selection needed) |

---

### Task 1: Add constants to `constants.py`

**Files:**
- Modify: `arch_bootstrap/constants.py`

**Step 1: Add `virtual_machine` to `DEVICE_PURPOSES`**

In the `DEVICE_PURPOSES` dict (around line 564), add:

```python
DEVICE_PURPOSES: dict[str, str] = {
    'development': 'Development',
    'gaming': 'Gaming',
    'media': 'Media Production',
    'industrial': 'Industrial Design',
    'virtual_machine': 'Virtual Machine',
}
```

**Step 2: Add `VM_OPTIONS` dict**

Add after `DEVICE_PURPOSES` (or near the other `*_OPTIONS` dicts):

```python
VM_OPTIONS: dict[str, dict] = {
    'kvm_base': {
        'label': 'KVM/QEMU + virt-manager',
        'packages': ['qemu-full', 'virt-manager', 'swtpm', 'dnsmasq', 'edk2-ovmf'],
        'aur': False,
        'services': ['libvirtd'],
    },
    'nested_virt': {
        'label': 'Nested Virtualization',
        'packages': [],
        'aur': False,
        'services': [],
    },
    'gpu_passthrough': {
        'label': 'GPU Hot-Switch Passthrough',
        'packages': [],
        'aur': False,
        'services': [],
    },
    'looking_glass': {
        'label': 'LookingGlass (KVMFR)',
        'packages': ['linux-headers'],
        'aur': False,
        'services': [],
        'aur_packages': ['looking-glass-module-dkms-git', 'looking-glass-git'],
    },
}
```

Note: `looking_glass` introduces an `aur_packages` field (new pattern) because it needs both pacman packages (`linux-headers`) and AUR packages.

**Step 3: Commit**

```bash
git add arch_bootstrap/constants.py
git commit -m "feat: add virtual_machine device purpose constants"
```

---

### Task 2: Add i18n translations to `i18n.py`

**Files:**
- Modify: `arch_bootstrap/i18n.py`

**Step 1: Add VM-related translation keys**

Add these entries to all three language dicts (`en`, `zh`, `ja`):

```python
# English
'opt.vm.title': 'Virtual Machine Setup',
'opt.vm.desc': 'Select VM components to install',
'confirm.vm_options': 'VM Components',

# Chinese
'opt.vm.title': '虚拟机配置',
'opt.vm.desc': '选择要安装的虚拟机组件',
'confirm.vm_options': '虚拟机组件',

# Japanese
'opt.vm.title': '仮想マシン設定',
'opt.vm.desc': 'インストールするVMコンポーネントを選択',
'confirm.vm_options': 'VMコンポーネント',
```

**Step 2: Commit**

```bash
git add arch_bootstrap/i18n.py
git commit -m "feat: add i18n translations for virtual machine purpose"
```

---

### Task 3: Add wizard step in `wizard.py`

**Files:**
- Modify: `arch_bootstrap/wizard.py`

**Step 1: Add imports**

Add `VM_OPTIONS` to the import from `constants`:

```python
from .constants import ..., VM_OPTIONS
```

**Step 2: Add `vm_options` field to `WizardState`**

After the `gaming_tools` field (around line 120):

```python
vm_options: list[str] = []          # keys from VM_OPTIONS
```

**Step 3: Create `step_virtual_machine()` function**

Add after `step_gaming()` (around line 984):

```python
async def step_virtual_machine(state: WizardState) -> str:
    """Select VM components (only if virtual_machine purpose selected)."""
    if 'virtual_machine' not in state.device_purposes:
        return 'next'

    # Detect if discrete GPU is available for passthrough
    has_dgpu = (
        len(state.detected_gpu) > 1
        or (
            any(g in state.detected_gpu for g in ['nvidia_open', 'nouveau'])
            and any(g in state.detected_gpu for g in ['amd', 'intel'])
        )
    )

    # Build option items
    items = []
    for key, info in VM_OPTIONS.items():
        if key in ('gpu_passthrough', 'looking_glass') and not has_dgpu:
            continue
        items.append(MenuItem(info['label'], value=key))

    group = MenuItemGroup(items)

    # Pre-select: kvm_base + nested_virt always; gpu_passthrough + looking_glass if dGPU
    preselect = ['kvm_base', 'nested_virt']
    if has_dgpu:
        preselect.extend(['gpu_passthrough', 'looking_glass'])
    if state.vm_options:
        group.set_selected_by_value(state.vm_options)
    else:
        group.set_selected_by_value(preselect)

    result = await Selection[str](
        group,
        title=t('opt.vm.title'),
        description=t('opt.vm.desc'),
        multi=True,
        allow_skip=True,
    ).show()

    if result.is_skip:
        state.vm_options = []
        return 'next'
    if result.is_back:
        return 'back'

    selected = result.get_values()

    # Enforce dependency: looking_glass requires gpu_passthrough
    if 'looking_glass' in selected and 'gpu_passthrough' not in selected:
        selected.remove('looking_glass')

    state.vm_options = selected
    return 'next'
```

**Step 4: Register skip condition**

In `_STEP_SKIP_CONDITIONS` dict (around line 1154), add:

```python
step_virtual_machine: lambda s: 'virtual_machine' not in s.device_purposes,
```

**Step 5: Add to steps list**

In `run_wizard()` steps list (around line 1372), insert `step_virtual_machine` after `step_gaming`:

```python
step_device_purpose, step_dev_tools, step_gaming, step_virtual_machine,
```

**Step 6: Add to confirmation page**

In the confirmation display section (around line 1251+), add VM options display:

```python
if 'virtual_machine' in state.device_purposes and state.vm_options:
    # Display selected VM components
    vm_labels = ', '.join(VM_OPTIONS[k]['label'] for k in state.vm_options if k in VM_OPTIONS)
    # Add to confirmation items
```

Follow the existing pattern used for dev_tools and gaming_tools confirmation display.

**Step 7: Commit**

```bash
git add arch_bootstrap/wizard.py
git commit -m "feat: add step_virtual_machine wizard step with GPU detection"
```

---

### Task 4: Collect VM packages in `config.py`

**Files:**
- Modify: `arch_bootstrap/config.py`

**Step 1: Add import**

Add `VM_OPTIONS` to imports from constants.

**Step 2: Add VM package collection**

In `apply_wizard_state_to_config()`, after the gaming packages collection block, add:

```python
# VM packages (non-AUR only)
for vm_key in state.vm_options:
    if vm_key in VM_OPTIONS and not VM_OPTIONS[vm_key].get('aur', False):
        all_packages.extend(VM_OPTIONS[vm_key]['packages'])
```

**Step 3: Commit**

```bash
git add arch_bootstrap/config.py
git commit -m "feat: collect VM packages in config"
```

---

### Task 5: Add VM installation logic to `installation.py`

**Files:**
- Modify: `arch_bootstrap/installation.py`

This is the largest task. The installation logic needs to handle:

**Step 1: Add imports**

Add `VM_OPTIONS` to imports from constants.

**Step 2: Add VM AUR package installation**

In the AUR packages section (where dev_editors and other AUR packages are collected), add:

```python
# VM AUR packages (looking_glass)
for vm_key in state.vm_options:
    if vm_key in VM_OPTIONS:
        for pkg in VM_OPTIONS[vm_key].get('aur_packages', []):
            if pkg not in aur_packages:
                aur_packages.append(pkg)
```

**Step 3: Add VM services enablement**

After the dev_environments services block (around line 762), add:

```python
# VM services
for vm_key in state.vm_options:
    if vm_key in VM_OPTIONS:
        for service in VM_OPTIONS[vm_key].get('services', []):
            run_with_retry(
                ['arch-chroot', str(chroot_dir), 'systemctl', 'enable', service],
                description=f'enable {service}',
            )
```

**Step 4: Add user to libvirt and kvm groups**

```python
if state.vm_options:
    run_with_retry(
        ['arch-chroot', str(chroot_dir), 'usermod', '-a', '-G', 'libvirt,kvm', username],
        description='add user to libvirt and kvm groups',
    )
```

**Step 5: Create KVM network setup first-boot service**

If `'kvm_base' in state.vm_options`:

Write `/etc/systemd/system/kvm-network-setup.service`:

```ini
[Unit]
Description=KVM Default Network Setup
After=libvirtd.service
Requires=libvirtd.service
ConditionPathExists=!/etc/kvm-network-configured

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'virsh net-start default; virsh net-autostart default; touch /etc/kvm-network-configured'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

Then `systemctl enable kvm-network-setup`.

**Step 6: Configure nested virtualization**

If `'nested_virt' in state.vm_options`:

Detect CPU vendor from `/proc/cpuinfo` (look for `GenuineIntel` or `AuthenticAMD`).

Write `/etc/modprobe.d/kvm_{intel,amd}.conf`:
```
options kvm_intel nested=1
```
or
```
options kvm_amd nested=1
```

**Step 7: Configure OVMF nvram**

If `'kvm_base' in state.vm_options`:

Write or append to `/etc/libvirt/qemu.conf`:
```
nvram = [
    "/usr/share/ovmf/x64/OVMF_CODE.fd:/usr/share/ovmf/x64/OVMF_VARS.fd"
]
```

Note: The file may already exist (installed by libvirt package). Need to check if `nvram` line exists and is commented, then uncomment and set, or append if not present.

**Step 8: Generate GPU hot-switch script**

If `'gpu_passthrough' in state.vm_options`:

Write `/usr/local/bin/gpu-passthrough` (chmod 755):

The script should be a self-contained bash script with three subcommands: `on`, `off`, `status`.

Key features:
- Auto-detect dGPU vendor (NVIDIA `10de` / AMD `1002`) and PCI addresses via `lspci`
- Distinguish AMD iGPU from dGPU using PCI bus topology (iGPU typically on bus 00, dGPU on higher buses)
- Find all IOMMU group siblings for the dGPU
- NVIDIA path: kill nvidia processes → rmmod nvidia_drm/nvidia_modeset/nvidia_uvm/nvidia → unbind → vfio-pci
- AMD path: rmmod amdgpu → unbind → vfio-pci
- Reverse path for `off`: clear override → unbind vfio → reload driver → reprobe
- Hugepage management:
  - Detect total RAM from `/proc/meminfo`
  - >= 32GB → 1GB hugepages (`/sys/kernel/mm/hugepages/hugepages-1048576kB/nr_hugepages`)
  - < 32GB → 2MB hugepages (`sysctl -w vm.nr_hugepages=N`)
  - Calculate hugepage count: (total_ram_gb / 2) rounded, in appropriate units
  - `on`: sync + drop caches + compact memory + allocate
  - `off`: release hugepages
- `status`: show current driver binding + hugepage info

**Step 9: Configure LookingGlass KVMFR**

If `'looking_glass' in state.vm_options`:

Write these files in chroot:

1. `/etc/modprobe.d/kvmfr.conf`:
```
options kvmfr static_size_mb=512
```

2. `/etc/modules-load.d/kvmfr.conf`:
```
# KVMFR Looking Glass module
kvmfr
```

3. `/etc/udev/rules.d/99-kvmfr.rules`:
```
SUBSYSTEM=="kvmfr", OWNER="<username>", GROUP="kvm", MODE="0660"
```

4. Edit `/etc/libvirt/qemu.conf` — find `cgroup_device_acl` block, uncomment it, add `/dev/kvmfr0`:
```
cgroup_device_acl = [
    "/dev/null", "/dev/full", "/dev/zero",
    "/dev/random", "/dev/urandom",
    "/dev/ptmx", "/dev/kvm", "/dev/kqemu",
    "/dev/rtc", "/dev/hpet", "/dev/vfio/vfio",
    "/dev/kvmfr0"
]
```

**Step 10: Commit**

```bash
git add arch_bootstrap/installation.py
git commit -m "feat: add VM installation logic with GPU passthrough and LookingGlass"
```

---

### Task 6: Final verification

**Step 1: Run linter/type check if available**

```bash
python -m py_compile arch_bootstrap/constants.py
python -m py_compile arch_bootstrap/wizard.py
python -m py_compile arch_bootstrap/config.py
python -m py_compile arch_bootstrap/installation.py
python -m py_compile arch_bootstrap/i18n.py
```

**Step 2: Verify all imports resolve**

```bash
cd /home/particleg/coding/arch-bootstrap
python -c "from arch_bootstrap.constants import VM_OPTIONS, DEVICE_PURPOSES; print('OK')"
```

**Step 3: Final commit if needed**

Fix any issues found during verification.
