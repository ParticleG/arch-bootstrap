from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from arch_bootstrap import dms, i18n


class GreeterConfigurationTests(unittest.TestCase):
    def test_embedded_ui_config_and_sync_order(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            chroot_dir = Path(temporary_dir)
            calls: list[list[str]] = []

            def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess:
                calls.append(command)
                return subprocess.CompletedProcess(command, 0)

            with (
                patch.object(dms.subprocess, 'run', side_effect=fake_run),
                patch.object(dms, '_info'),
                patch.object(dms, '_debug'),
            ):
                self.assertTrue(dms.configure_dms_greeter(chroot_dir, 'alice', 'niri'))

            config = (chroot_dir / 'etc/greetd/config.toml').read_text()
            self.assertIn(
                'command = "/usr/bin/dms-greeter --command niri"',
                config,
            )
            self.assertNotIn('/usr/share/quickshell/dms', config)
            self.assertNotIn(' -p ', config)
            self.assertEqual(calls[0][-2:], ['-u', 'greeter'])
            self.assertEqual(calls[1][-2:], ['--create', '/usr/lib/tmpfiles.d/dms-greeter.conf'])
            self.assertEqual(calls[2][-3:], ['-aG', 'greeter', 'alice'])
            self.assertEqual(
                calls[3][-1],
                'env LANG=C.UTF-8 DMS_PRIVESC=sudo dms-greeter sync -y',
            )

    def test_sync_failure_keeps_valid_bootstrap_config(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            chroot_dir = Path(temporary_dir)
            return_codes = iter([0, 0, 0, 7])

            def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess:
                return subprocess.CompletedProcess(command, next(return_codes))

            with (
                patch.object(dms.subprocess, 'run', side_effect=fake_run),
                patch.object(dms, '_info'),
                patch.object(dms, '_debug'),
            ):
                self.assertFalse(dms.configure_dms_greeter(chroot_dir, 'alice', 'niri'))

            config = (chroot_dir / 'etc/greetd/config.toml').read_text()
            self.assertIn('/usr/bin/dms-greeter --command niri', config)
            self.assertNotIn(' -p ', config)

    def test_missing_greeter_account_stops_before_sync(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            chroot_dir = Path(temporary_dir)
            calls: list[list[str]] = []

            def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess:
                calls.append(command)
                return subprocess.CompletedProcess(command, 1)

            with (
                patch.object(dms.subprocess, 'run', side_effect=fake_run),
                patch.object(dms, '_info'),
                patch.object(dms, '_debug'),
            ):
                self.assertFalse(dms.configure_dms_greeter(chroot_dir, 'alice', 'hyprland'))

            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][-2:], ['-u', 'greeter'])


class InstallerFailureTests(unittest.TestCase):
    def test_package_failure_does_not_setup_or_enable_services(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            chroot_dir = Path(temporary_dir)
            run_setup = Mock()
            configure_greeter = Mock()
            enable_services = Mock()

            with (
                patch.object(dms, 'install_chroot_packages', return_value=False),
                patch.object(dms, 'run_dms_setup', run_setup),
                patch.object(dms, 'configure_dms_greeter', configure_greeter),
                patch.object(dms, '_enable_dms_services', enable_services),
                patch.object(dms, '_info'),
                patch.object(dms, '_debug'),
            ):
                self.assertFalse(dms.install_dms(chroot_dir, 'alice', 'niri', 'ghostty'))

            run_setup.assert_not_called()
            configure_greeter.assert_not_called()
            enable_services.assert_not_called()
            self.assertFalse((chroot_dir / 'etc/sudoers.d/99-dms-temp').exists())

    def test_missing_package_stops_before_setup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            chroot_dir = Path(temporary_dir)
            run_setup = Mock()

            with (
                patch.object(dms, 'install_chroot_packages', return_value=True),
                patch.object(dms, 'verify_dms_installation', return_value=False),
                patch.object(dms, 'run_dms_setup', run_setup),
                patch.object(dms, '_info'),
                patch.object(dms, '_debug'),
            ):
                self.assertFalse(dms.install_dms(chroot_dir, 'alice', 'niri', 'ghostty'))

            run_setup.assert_not_called()

    def test_setup_failure_does_not_configure_greeter_or_enable_services(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            chroot_dir = Path(temporary_dir)
            configure_greeter = Mock()
            enable_services = Mock()

            with (
                patch.object(dms, 'install_chroot_packages', return_value=True),
                patch.object(dms, 'verify_dms_installation', return_value=True),
                patch.object(dms, 'run_dms_setup', return_value=False),
                patch.object(dms, 'configure_dms_greeter', configure_greeter),
                patch.object(dms, '_enable_dms_services', enable_services),
                patch.object(dms, '_info'),
                patch.object(dms, '_debug'),
            ):
                self.assertFalse(dms.install_dms(chroot_dir, 'alice', 'niri', 'ghostty'))

            configure_greeter.assert_not_called()
            enable_services.assert_not_called()

    def test_greeter_failure_does_not_enable_services(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            chroot_dir = Path(temporary_dir)
            enable_services = Mock()

            with (
                patch.object(dms, 'install_chroot_packages', return_value=True),
                patch.object(dms, 'verify_dms_installation', return_value=True),
                patch.object(dms, 'run_dms_setup', return_value=True),
                patch.object(dms, 'configure_dms_shortcuts', return_value=True),
                patch.object(dms, 'normalize_dms_ownership', return_value=True),
                patch.object(dms, 'configure_dms_greeter', return_value=False),
                patch.object(dms, '_enable_dms_services', enable_services),
                patch.object(dms, '_info'),
                patch.object(dms, '_debug'),
            ):
                self.assertFalse(dms.install_dms(chroot_dir, 'alice', 'niri', 'ghostty'))

            enable_services.assert_not_called()

    def test_search_failure_does_not_enable_services(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            chroot_dir = Path(temporary_dir)
            enable_services = Mock()

            with (
                patch.object(dms, 'install_chroot_packages', return_value=True),
                patch.object(dms, 'verify_dms_installation', return_value=True),
                patch.object(dms, 'run_dms_setup', return_value=True),
                patch.object(dms, 'configure_dms_shortcuts', return_value=True),
                patch.object(dms, 'normalize_dms_ownership', return_value=True),
                patch.object(dms, 'configure_dms_greeter', return_value=True),
                patch.object(dms, 'configure_dms_environment'),
                patch.object(dms, '_configure_i2c'),
                patch.object(dms, 'configure_dms_autostart', return_value=True),
                patch.object(dms, '_prepare_dsearch', return_value=False),
                patch.object(dms, '_enable_dms_services', enable_services),
                patch.object(dms, '_info'),
                patch.object(dms, '_debug'),
            ):
                self.assertFalse(dms.install_dms(chroot_dir, 'alice', 'hyprland', 'kitty'))

            enable_services.assert_not_called()

    def test_service_link_failure_returns_false(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            chroot_dir = Path(temporary_dir)

            with (
                patch.object(dms, 'install_chroot_packages', return_value=True),
                patch.object(dms, 'verify_dms_installation', return_value=True),
                patch.object(dms, 'run_dms_setup', return_value=True),
                patch.object(dms, 'configure_dms_shortcuts', return_value=True),
                patch.object(dms, 'normalize_dms_ownership', return_value=True),
                patch.object(dms, 'configure_dms_greeter', return_value=True),
                patch.object(dms, 'configure_dms_environment'),
                patch.object(dms, '_configure_i2c'),
                patch.object(dms, 'configure_dms_autostart', return_value=True),
                patch.object(dms, '_prepare_dsearch', return_value=True),
                patch.object(dms, '_enable_dms_services', return_value=False),
                patch.object(dms, '_info'),
                patch.object(dms, '_debug'),
            ):
                self.assertFalse(dms.install_dms(chroot_dir, 'alice', 'niri', 'ghostty'))


class SetupCommandTests(unittest.TestCase):
    def test_failed_setup_removes_early_service_activation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            link = root / 'home/alice/.config/systemd/user/niri.service.wants/dms.service'

            def partially_failed_setup(command: list[str], **_: object) -> subprocess.CompletedProcess:
                link.parent.mkdir(parents=True)
                link.symlink_to('/usr/lib/systemd/user/dms.service')
                return subprocess.CompletedProcess(command, 3)

            with (
                patch.object(dms.subprocess, 'run', side_effect=partially_failed_setup),
                patch.object(dms, '_info'),
                patch.object(dms, '_debug'),
            ):
                self.assertFalse(dms.run_dms_setup(root, 'alice', 'niri', 'kitty'))
            self.assertFalse(link.is_symlink())


class IntegrationFileTests(unittest.TestCase):
    def test_environment_uses_capitalized_adwaita(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            chroot_dir = Path(temporary_dir)
            (chroot_dir / 'etc').mkdir()
            env_file = chroot_dir / 'etc/environment'
            env_file.write_text('EXISTING=1\nQS_ICON_THEME=adwaita\n')

            with patch.object(dms, '_info'), patch.object(dms, '_debug'):
                dms.configure_dms_environment(chroot_dir)
                dms.configure_dms_environment(chroot_dir)

            content = env_file.read_text()
            self.assertIn('QS_ICON_THEME=Adwaita\n', content)
            self.assertNotIn('QS_ICON_THEME=adwaita', content)
            self.assertIn('QT_QPA_PLATFORMTHEME=qt6ct', content)
            self.assertEqual(content.count('EXISTING=1'), 1)
            self.assertEqual(content.count('QS_ICON_THEME='), 1)

    def test_service_links_cover_both_compositors(self) -> None:
        for compositor, wants in (
            ('niri', 'niri.service.wants'),
            ('hyprland', 'hyprland-session.target.wants'),
        ):
            with self.subTest(compositor=compositor):
                with tempfile.TemporaryDirectory() as temporary_dir:
                    chroot_dir = Path(temporary_dir)
                    system_dir = chroot_dir / 'usr/lib/systemd/system'
                    user_dir = chroot_dir / 'usr/lib/systemd/user'
                    system_dir.mkdir(parents=True)
                    user_dir.mkdir(parents=True)
                    (system_dir / 'greetd.service').write_text('')
                    (system_dir / 'graphical.target').write_text('')
                    (user_dir / 'dms.service').write_text('')
                    (user_dir / 'dsearch.service').write_text('')
                    (user_dir / wants.removesuffix('.wants')).write_text('')

                    with (
                        patch.object(
                            dms.subprocess,
                            'run',
                            return_value=subprocess.CompletedProcess([], 0),
                        ),
                        patch.object(dms, '_info'),
                        patch.object(dms, '_debug'),
                    ):
                        self.assertTrue(
                            dms._enable_dms_services(chroot_dir, 'alice', compositor),
                        )

                    dm_link = (
                        chroot_dir / 'etc/systemd/system/display-manager.service'
                    )
                    self.assertEqual(
                        dm_link.readlink(),
                        Path('/usr/lib/systemd/system/greetd.service'),
                    )
                    dms_link = (
                        chroot_dir / 'home/alice/.config/systemd/user'
                        / wants / 'dms.service'
                    )
                    self.assertEqual(
                        dms_link.readlink(),
                        Path('/usr/lib/systemd/user/dms.service'),
                    )
                    search_link = dms_link.with_name('dsearch.service')
                    self.assertEqual(
                        search_link.readlink(),
                        Path('/usr/lib/systemd/user/dsearch.service'),
                    )

    def test_ownership_failure_does_not_activate_any_service(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            for relative_path in (
                'usr/lib/systemd/system/greetd.service',
                'usr/lib/systemd/system/graphical.target',
                'usr/lib/systemd/user/niri.service',
                'usr/lib/systemd/user/dms.service',
                'usr/lib/systemd/user/dsearch.service',
            ):
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            with (
                patch.object(dms.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1)),
                patch.object(dms, '_info'),
            ):
                self.assertFalse(dms._enable_dms_services(root, 'alice', 'niri'))
            self.assertFalse(any(path.is_symlink() for path in root.rglob('*')))

    def test_search_binary_and_unit_are_required_before_enablement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            chroot_dir = Path(temporary_dir)
            for path in (
                'usr/bin/dms',
                'usr/bin/dms-greeter',
                'usr/lib/systemd/user/dms.service',
                'usr/lib/systemd/user/dsearch.service',
            ):
                target = chroot_dir / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('')

            self.assertFalse(dms.verify_dms_installation(chroot_dir))
            with patch.object(dms, '_info'), patch.object(dms, '_debug'):
                self.assertFalse(dms._prepare_dsearch(chroot_dir, 'alice'))

            (chroot_dir / 'usr/bin/dsearch').write_text('')
            self.assertTrue(dms.verify_dms_installation(chroot_dir))

    def test_missing_user_unit_prevents_service_links(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            chroot_dir = Path(temporary_dir)
            with (
                patch.object(dms, '_info'),
                patch.object(dms, '_debug'),
            ):
                self.assertFalse(
                    dms._enable_dms_services(chroot_dir, 'alice', 'niri'),
                )
            self.assertFalse(
                (chroot_dir / 'etc/systemd/system/display-manager.service').exists(),
            )


class TranslationContractTests(unittest.TestCase):
    def test_translation_keys_match_across_languages(self) -> None:
        key_sets = {
            language: set(translations)
            for language, translations in i18n.TRANSLATIONS.items()
        }
        self.assertTrue(all(keys == key_sets['en'] for keys in key_sets.values()))


if __name__ == '__main__':
    unittest.main()
