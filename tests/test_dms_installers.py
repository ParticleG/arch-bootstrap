from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from arch_bootstrap import constants, dms, dms_manual, i18n


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
            self.assertEqual(calls[3][-3:], ['-aG', 'greeter', 'alice'])
            self.assertEqual(
                calls[4][-1],
                'env LANG=C.UTF-8 DMS_PRIVESC=sudo dms-greeter sync -y',
            )

    def test_sync_failure_keeps_valid_bootstrap_config(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            chroot_dir = Path(temporary_dir)
            return_codes = iter([0, 0, 0, 0, 7])

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


class InstallerFailureTests(unittest.TestCase):
    def test_dankinstall_failure_does_not_enable_services(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            chroot_dir = Path(temporary_dir)
            (chroot_dir / 'etc/sudoers.d').mkdir(parents=True)
            binary_path = chroot_dir / 'var/tmp/dankinstall'
            binary_path.parent.mkdir(parents=True)
            binary_path.write_bytes(b'binary')
            enable_services = Mock()

            with (
                patch.object(dms, '_download_dankinstall', return_value=binary_path),
                patch.object(
                    dms.subprocess,
                    'run',
                    return_value=subprocess.CompletedProcess([], 9),
                ),
                patch.object(dms, '_enable_dms_services', enable_services),
                patch.object(dms, '_info'),
                patch.object(dms, '_debug'),
            ):
                self.assertFalse(dms.install_dms(chroot_dir, 'alice', 'niri', 'ghostty'))

            enable_services.assert_not_called()
            self.assertFalse(binary_path.exists())
            self.assertFalse((chroot_dir / 'etc/sudoers.d/dankinstall-tmp').exists())

    def test_runtime_package_failure_does_not_enable_services(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            chroot_dir = Path(temporary_dir)
            (chroot_dir / 'etc/sudoers.d').mkdir(parents=True)
            binary_path = chroot_dir / 'var/tmp/dankinstall'
            binary_path.parent.mkdir(parents=True)
            binary_path.write_bytes(b'binary')
            enable_services = Mock()
            configure_environment = Mock()

            with (
                patch.object(dms, '_download_dankinstall', return_value=binary_path),
                patch.object(
                    dms.subprocess,
                    'run',
                    return_value=subprocess.CompletedProcess([], 0),
                ),
                patch.object(dms, 'configure_dms_greeter', return_value=True),
                patch.object(dms, '_install_dms_extras', return_value=False),
                patch.object(dms, '_configure_dms_environment', configure_environment),
                patch.object(dms, '_enable_dms_services', enable_services),
                patch.object(dms, '_info'),
                patch.object(dms, '_debug'),
            ):
                self.assertFalse(dms.install_dms(chroot_dir, 'alice', 'niri', 'ghostty'))

            configure_environment.assert_not_called()
            enable_services.assert_not_called()

    def test_manual_setup_failure_does_not_configure_or_enable_greeter(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            chroot_dir = Path(temporary_dir)
            configure_greeter = Mock()
            enable_services = Mock()

            with (
                patch.object(dms_manual, '_install_prereq_packages', return_value=True),
                patch.object(dms_manual, '_install_packages', return_value=True),
                patch.object(dms_manual, '_run_dms_setup', return_value=False),
                patch.object(dms_manual, 'configure_dms_greeter', configure_greeter),
                patch.object(dms_manual, '_enable_services', enable_services),
                patch.object(dms_manual, '_info'),
                patch.object(dms_manual, '_debug'),
            ):
                self.assertFalse(dms_manual.install_dms_manual(chroot_dir, 'alice'))

            configure_greeter.assert_not_called()
            enable_services.assert_not_called()
            self.assertFalse(
                (chroot_dir / 'etc/sudoers.d/99-dms-manual-temp').exists()
            )

    def test_manual_greeter_failure_does_not_enable_services(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            chroot_dir = Path(temporary_dir)
            enable_services = Mock()

            with (
                patch.object(dms_manual, '_install_prereq_packages', return_value=True),
                patch.object(dms_manual, '_install_packages', return_value=True),
                patch.object(dms_manual, '_run_dms_setup', return_value=True),
                patch.object(dms_manual, '_patch_niri_binds'),
                patch.object(dms_manual, '_fix_ownership'),
                patch.object(dms_manual, 'configure_dms_greeter', return_value=False),
                patch.object(dms_manual, '_enable_services', enable_services),
                patch.object(dms_manual, '_info'),
                patch.object(dms_manual, '_debug'),
            ):
                self.assertFalse(dms_manual.install_dms_manual(chroot_dir, 'alice'))

            enable_services.assert_not_called()
            self.assertFalse(
                (chroot_dir / 'etc/sudoers.d/99-dms-manual-temp').exists()
            )


class DesktopContractTests(unittest.TestCase):
    def test_runtime_packages_cover_default_font_and_sound(self) -> None:
        expected = {
            'inter-font',
            'qt6-multimedia',
            'qt6-multimedia-ffmpeg',
        }
        self.assertEqual(set(constants.DMS_RUNTIME_PACKAGES), expected)
        self.assertTrue(expected.issubset(constants.DMS_MANUAL_SYSTEM_PACKAGES))
        self.assertTrue(expected.issubset(dms._DMS_EXTRA_PACKAGES))

    def test_translation_keys_match_across_languages(self) -> None:
        key_sets = {
            language: set(translations)
            for language, translations in i18n.TRANSLATIONS.items()
        }
        self.assertTrue(all(keys == key_sets['en'] for keys in key_sets.values()))


if __name__ == '__main__':
    unittest.main()
