from __future__ import annotations

import unittest
from types import SimpleNamespace

from arch_bootstrap.packages import (
    collect_optional_packages,
    normalize_optional_state,
)


def make_state(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        'country': 'US',
        'locale': 'en_US.UTF-8',
        'desktop_env': 'minimal',
        'dms_compositor': 'niri',
        'dms_terminal': 'ghostty',
        'multilib': True,
        'detected_dgpu': False,
        'device_purposes': [],
        'input_methods': [],
        'keyring': None,
        'polkit_agent': None,
        'file_managers': [],
        'proxy_tool': None,
        'dev_environments': [],
        'dev_editors': [],
        'gaming_tools': [],
        'vm_options': [],
        'remote_desktop': [],
        'cn_apps': [],
        'media_tools': [],
        'industrial_tools': [],
        'browsers': [],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def collected(state: SimpleNamespace) -> tuple[set[str], set[str], set[str]]:
    official, late_repo, aur = collect_optional_packages(state)
    return set(official), set(late_repo), set(aur)


class HiddenSelectionTests(unittest.TestCase):
    def test_minimal_ignores_desktop_only_selections(self) -> None:
        state = make_state(
            keyring='gnome',
            polkit_agent='mate',
            file_managers=['nautilus'],
            input_methods=['fcitx5_zh'],
        )
        official, late_repo, aur = collected(state)

        self.assertNotIn('gnome-keyring', official)
        self.assertNotIn('mate-polkit', official)
        self.assertNotIn('nautilus', official)
        self.assertNotIn('fcitx5', official)
        self.assertIsNone(state.keyring)
        self.assertIsNone(state.polkit_agent)
        self.assertEqual(state.file_managers, [])
        self.assertEqual(state.input_methods, [])
        self.assertEqual(late_repo, set())
        self.assertEqual(aur, set())

    def test_hidden_purpose_and_cn_selections_do_not_leak(self) -> None:
        state = make_state(
            country='US',
            device_purposes=[],
            dev_environments=['github-cli', 'oh-my-pi'],
            dev_editors=['vscode'],
            gaming_tools=['steam', 'uuplugin'],
            vm_options=['looking_glass'],
            media_tools=['obs', 'soundcraft'],
            industrial_tools=['freecad', 'lceda-pro'],
            cn_apps=['wechat'],
            proxy_tool='flclash',
        )
        official, late_repo, aur = collected(state)

        self.assertEqual(official, set())
        self.assertEqual(late_repo, set())
        self.assertEqual(aur, set())
        self.assertEqual(state.dev_environments, [])
        self.assertEqual(state.dev_editors, [])
        self.assertEqual(state.gaming_tools, [])
        self.assertEqual(state.vm_options, [])
        self.assertEqual(state.media_tools, [])
        self.assertEqual(state.industrial_tools, [])
        self.assertEqual(state.cn_apps, [])
        self.assertIsNone(state.proxy_tool)

    def test_gaming_requires_multilib(self) -> None:
        state = make_state(
            device_purposes=['gaming'],
            multilib=False,
            gaming_tools=['steam', 'protontricks'],
        )
        official, _, _ = collected(state)
        self.assertNotIn('steam', official)
        self.assertNotIn('protontricks', official)

    def test_english_locale_ignores_stale_input_method(self) -> None:
        state = make_state(
            locale='en_US.UTF-8',
            input_methods=['fcitx5_zh'],
        )
        official, _, aur = collected(state)
        self.assertNotIn('fcitx5', official)
        self.assertNotIn('fcitx5-pinyin-moegirl', aur)


class DuxAndExoTests(unittest.TestCase):
    def test_dux_skips_polkit_and_adds_nautilus_ghostty_integration(self) -> None:
        state = make_state(
            desktop_env='dms',
            dms_terminal='ghostty',
            keyring='gnome',
            polkit_agent='mate',
            file_managers=['nautilus'],
        )
        official, _, _ = collected(state)

        self.assertIn('gnome-keyring', official)
        self.assertIn('gcr-4', official)
        self.assertIn('nautilus', official)
        self.assertIn('gvfs', official)
        self.assertIn('gvfs-mtp', official)
        self.assertIn('gvfs-smb', official)
        self.assertIn('ffmpegthumbnailer', official)
        self.assertIn('ghostty-nautilus', official)
        self.assertNotIn('mate-polkit', official)
        self.assertIsNone(state.polkit_agent)
        self.assertEqual(state.keyring, 'gnome')

    def test_ghostty_nautilus_requires_ghostty_terminal(self) -> None:
        ghostty_state = make_state(
            desktop_env='dms',
            dms_terminal='ghostty',
            file_managers=['nautilus'],
        )
        kitty_state = make_state(
            desktop_env='dms',
            dms_terminal='kitty',
            file_managers=['nautilus'],
        )
        exo_state = make_state(desktop_env='exo', file_managers=[])

        self.assertIn('ghostty-nautilus', collected(ghostty_state)[0])
        self.assertNotIn('ghostty-nautilus', collected(kitty_state)[0])
        self.assertNotIn('ghostty-nautilus', collected(exo_state)[0])

    def test_exo_auto_selects_nautilus(self) -> None:
        state = make_state(desktop_env='exo', file_managers=[])
        official, _, _ = collected(state)

        self.assertEqual(state.file_managers, ['nautilus'])
        self.assertIn('nautilus', official)
        self.assertIn('gvfs-mtp', official)
        self.assertNotIn('ghostty-nautilus', official)

    def test_unknown_desktop_is_rejected(self) -> None:
        state = make_state(
            desktop_env='dms_manual',
            keyring='gnome',
            file_managers=['nautilus'],
            dms_terminal='ghostty',
        )

        with self.assertRaises(ValueError):
            normalize_optional_state(state)
        with self.assertRaises(ValueError):
            collect_optional_packages(state)

    def test_invalid_dux_choices_are_not_silently_replaced(self) -> None:
        for field in ('dms_compositor', 'dms_terminal'):
            with self.subTest(field=field):
                state = make_state(desktop_env='dms', **{field: 'unsupported'})
                with self.assertRaises(ValueError):
                    collect_optional_packages(state)


class RegionRoutingTests(unittest.TestCase):
    def test_cn_sources_replace_corresponding_aur_packages(self) -> None:
        state = make_state(
            country='CN',
            locale='zh_CN.UTF-8',
            desktop_env='exo',
            device_purposes=['development', 'virtual_machine', 'industrial', 'gaming'],
            input_methods=['fcitx5_zh'],
            dev_environments=['oh-my-pi'],
            gaming_tools=['gamescope', 'protontricks', 'protonup-qt', 'uuplugin'],
            vm_options=['kvm_base', 'looking_glass', 'gpu_passthrough'],
            detected_dgpu=True,
            remote_desktop=['sunshine', 'rustdesk'],
            industrial_tools=['orca-slicer', 'lceda-pro'],
            proxy_tool='flclash',
        )
        official, late_repo, aur = collected(state)

        self.assertIn('archlinuxcn/fcitx5-pinyin-moegirl', late_repo)
        self.assertIn('archlinuxcn/oh-my-pi', late_repo)
        self.assertIn('archlinuxcn/orca-slicer', late_repo)
        self.assertIn('archlinuxcn/sunshine', late_repo)
        self.assertIn('archlinuxcn/rustdesk', late_repo)
        self.assertIn('archlinuxcn/flclash', late_repo)
        self.assertNotIn('fcitx5-pinyin-moegirl', aur)
        self.assertNotIn('oh-my-pi', aur)
        self.assertNotIn('orca-slicer-bin', aur)
        self.assertNotIn('sunshine-bin', aur)
        self.assertNotIn('rustdesk-bin', aur)
        self.assertIn('uuplugin-bin', aur)
        self.assertIn('gamescope', official)
        self.assertIn('protontricks', official)
        self.assertIn('protonup-qt', aur)
        self.assertIn('archlinuxcn/lceda-pro', late_repo)
        self.assertNotIn('lceda-pro', aur)

    def test_non_cn_uses_aur_and_drops_cn_only_options(self) -> None:
        state = make_state(
            country='US',
            locale='zh_CN.UTF-8',
            desktop_env='exo',
            device_purposes=['development', 'virtual_machine', 'industrial', 'gaming'],
            input_methods=['fcitx5_zh'],
            dev_environments=['oh-my-pi'],
            gaming_tools=['gamescope', 'protontricks', 'protonup-qt', 'uuplugin'],
            vm_options=['kvm_base', 'looking_glass', 'gpu_passthrough'],
            detected_dgpu=True,
            remote_desktop=['sunshine', 'rustdesk'],
            industrial_tools=['orca-slicer', 'lceda-pro', 'bambustudio', 'cadcraft'],
        )
        official, late_repo, aur = collected(state)

        self.assertEqual(late_repo, set())
        self.assertIn('fcitx5-pinyin-moegirl', aur)
        self.assertIn('oh-my-pi', aur)
        self.assertIn('orca-slicer-bin', aur)
        self.assertIn('sunshine-bin', aur)
        self.assertIn('rustdesk-bin', aur)
        self.assertIn('protonup-qt', aur)
        self.assertIn('bambustudio-bin', aur)
        self.assertIn('cadcraft-bin', aur)
        self.assertNotIn('uuplugin-bin', aur)
        self.assertNotIn('lceda-pro', aur)
        self.assertNotIn('archlinuxcn/orca-slicer', late_repo)
        self.assertIn('gamescope', official)
        self.assertIn('protontricks', official)

    def test_sunshine_not_selectable_on_minimal(self) -> None:
        state = make_state(
            country='US',
            desktop_env='minimal',
            remote_desktop=['sunshine', 'rustdesk'],
        )
        _, late_repo, aur = collected(state)

        self.assertEqual(state.remote_desktop, ['rustdesk'])
        self.assertNotIn('sunshine-bin', aur)
        self.assertNotIn('archlinuxcn/sunshine', late_repo)
        self.assertIn('rustdesk-bin', aur)

    def test_cn_apps_only_install_in_cn(self) -> None:
        cn_state = make_state(
            country='CN', cn_apps=['wechat', 'feishu'], proxy_tool='mihomo',
        )
        us_state = make_state(
            country='US', cn_apps=['wechat'], proxy_tool='mihomo',
        )
        _, cn_late, cn_aur = collected(cn_state)
        _, us_late, us_aur = collected(us_state)

        self.assertIn('wechat-universal-bwrap', cn_aur)
        self.assertIn('feishu-bin', cn_aur)
        self.assertIn('archlinuxcn/mihomo', cn_late)
        self.assertEqual(us_late, set())
        self.assertNotIn('wechat-universal-bwrap', us_aur)


class NewOptionTests(unittest.TestCase):
    def test_development_and_media_industrial_packages(self) -> None:
        state = make_state(
            device_purposes=['development', 'media', 'industrial'],
            dev_environments=[
                'github-cli', 'jq', 'uv', 'shellcheck', 'nodejs',
            ],
            media_tools=['obs', 'blender', 'soundcraft', 'filmcraft'],
            industrial_tools=[
                'openscad', 'freecad', 'bambustudio', 'cadcraft',
            ],
        )
        official, _, aur = collected(state)

        for package in (
            'github-cli', 'jq', 'uv', 'shellcheck',
            'nodejs-lts-krypton', 'obs-studio', 'blender',
            'openscad', 'freecad',
        ):
            self.assertIn(package, official)
        self.assertNotIn('nodejs-lts-jod', official)
        for package in (
            'soundcraft-bin', 'filmcraft-bin',
            'bambustudio-bin', 'cadcraft-bin',
        ):
            self.assertIn(package, aur)
        self.assertNotIn('effectcraft-bin', aur)
        self.assertNotIn('photocraft-bin', aur)
        self.assertNotIn('vectorcraft-bin', aur)
        self.assertNotIn('lightcraft-bin', aur)

    def test_artcraft_choices_are_selectable_but_not_bulk(self) -> None:
        state = make_state(
            device_purposes=['media'],
            media_tools=['effectcraft', 'photocraft', 'vectorcraft', 'lightcraft'],
        )
        _, _, aur = collected(state)
        self.assertEqual(
            aur,
            {
                'effectcraft-bin', 'photocraft-bin',
                'vectorcraft-bin', 'lightcraft-bin',
            },
        )

    def test_vm_base_and_looking_glass_dependencies(self) -> None:
        state = make_state(
            device_purposes=['virtual_machine'],
            detected_dgpu=True,
            vm_options=['looking_glass', 'gpu_passthrough'],
        )
        official, _, aur = collected(state)

        self.assertIn('qemu-full', official)
        self.assertIn('virt-manager', official)
        self.assertIn('virt-viewer', official)
        self.assertIn('swtpm', official)
        self.assertIn('dnsmasq', official)
        self.assertIn('edk2-ovmf', official)
        self.assertIn('switcheroo-control', official)
        self.assertIn('looking-glass', aur)
        self.assertIn('looking-glass-module-dkms', aur)
        self.assertEqual(
            state.vm_options,
            ['kvm_base', 'gpu_passthrough', 'looking_glass'],
        )

    def test_vm_gpu_features_require_dgpu_and_gpu_passthrough(self) -> None:
        no_dgpu = make_state(
            device_purposes=['virtual_machine'],
            detected_dgpu=False,
            vm_options=['kvm_base', 'gpu_passthrough', 'looking_glass'],
        )
        passthrough = make_state(
            device_purposes=['virtual_machine'],
            detected_dgpu=True,
            vm_options=['looking_glass', 'gpu_passthrough'],
        )
        nested = make_state(
            device_purposes=['virtual_machine'],
            detected_dgpu=False,
            vm_options=['nested_virt'],
        )

        no_dgpu_official, _, no_dgpu_aur = collected(no_dgpu)
        self.assertNotIn('switcheroo-control', no_dgpu_official)
        self.assertEqual(no_dgpu_aur, set())
        self.assertIn('qemu-full', no_dgpu_official)

        passthrough_official, _, passthrough_aur = collected(passthrough)
        self.assertIn('switcheroo-control', passthrough_official)
        self.assertIn('qemu-full', passthrough_official)
        self.assertIn('looking-glass', passthrough_aur)
        self.assertIn('looking-glass-module-dkms', passthrough_aur)
        self.assertNotIn('looking-glass-git', passthrough_aur)
        self.assertNotIn('looking-glass-module-dkms-git', passthrough_aur)

        nested_official, _, _ = collected(nested)
        self.assertIn('qemu-full', nested_official)

    def test_browsers_are_excluded_from_optional_packages(self) -> None:
        state = make_state(browsers=['chrome', 'edge', 'firefox'])
        official, late_repo, aur = collected(state)
        for package in (
            'firefox', 'chromium', 'google-chrome',
            'microsoft-edge-stable-bin',
        ):
            self.assertNotIn(package, official)
            self.assertNotIn(package, late_repo)
            self.assertNotIn(package, aur)


if __name__ == '__main__':
    unittest.main()
