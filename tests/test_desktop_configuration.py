from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from configparser import ConfigParser
from pathlib import Path
from unittest.mock import patch

try:
    from arch_bootstrap import installation
except ModuleNotFoundError as error:
    if not error.name or not error.name.startswith('archinstall'):
        raise
    installation = None


@unittest.skipIf(installation is None, 'archinstall is required for installer integration tests')
class DesktopConfigurationTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('zsh'), 'zsh is required to evaluate the plugin array')
    def test_commented_plugin_example_does_not_prevent_activation(self) -> None:
        for example in ('git docker', 'git fast-syntax-highlighting'):
            with self.subTest(example=example), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / '.zshrc'
                path.write_text(f'# Example: plugins=({example})\nplugins=(git)\n')
                with patch.object(installation, '_debug'):
                    installation._patch_zshrc_plugins(str(path))
                    installation._patch_zshrc_plugins(str(path))
                result = subprocess.run(
                    ['zsh', '-f', '-c', 'source "$1"; print -rl -- $plugins', '_', str(path)],
                    check=True, capture_output=True, text=True,
                )
                self.assertEqual(result.stdout.splitlines(), ['git', 'fast-syntax-highlighting'])

    def test_gtk_input_method_preserves_theme_and_merges_repeated_sections(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / 'home/alice'
            for version in ('gtk-3.0', 'gtk-4.0'):
                path = home / '.config' / version / 'settings.ini'
                path.parent.mkdir(parents=True)
                path.write_text(
                    '[Settings]\ngtk-theme-name=adw-gtk3-dark\n'
                    'gtk-icon-theme-name=Adwaita\n[Settings]\ngtk-im-module=ibus\n'
                )
            (home / '.gtkrc-2.0').write_text('gtk-font-name="Sans 11"\ngtk-im-module="ibus"\n')
            with patch.object(
                installation, 'run_with_retry', return_value=subprocess.CompletedProcess([], 0),
            ):
                self.assertTrue(installation._configure_gtk_input_method(root, 'alice'))
                self.assertTrue(installation._configure_gtk_input_method(root, 'alice'))
            for version in ('gtk-3.0', 'gtk-4.0'):
                settings = ConfigParser()
                settings.read(home / '.config' / version / 'settings.ini')
                self.assertEqual(settings['Settings']['gtk-theme-name'], 'adw-gtk3-dark')
                self.assertEqual(settings['Settings']['gtk-icon-theme-name'], 'Adwaita')
                self.assertEqual(settings['Settings']['gtk-im-module'], 'fcitx')
            gtk2 = (home / '.gtkrc-2.0').read_text()
            self.assertIn('gtk-font-name="Sans 11"', gtk2)
            self.assertEqual(gtk2.count('gtk-im-module='), 1)
            self.assertNotIn('ibus', gtk2)

    def test_mime_defaults_preserve_user_choices_and_prefer_image_viewer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            applications = root / 'usr/share/applications'
            applications.mkdir(parents=True)
            for name, mime_types in (
                ('org.gnome.FileRoller.desktop', 'application/zip;'),
                ('mpv.desktop', 'video/webm;image/jpeg;x-scheme-handler/http;'),
                ('org.gnome.Loupe.desktop', 'image/jpeg;image/png;'),
                ('org.gnome.Nautilus.desktop', 'inode/directory;'),
            ):
                (applications / name).write_text(f'[Desktop Entry]\nMimeType={mime_types}\n')
            mimeapps = root / 'home/alice/.config/mimeapps.list'
            mimeapps.parent.mkdir(parents=True)
            mimeapps.write_text(
                '[Default Applications]\nimage/png=custom-editor.desktop;\n'
                'x-scheme-handler/http=custom-browser.desktop;\n'
                '[Added Associations]\napplication/pdf=custom-pdf.desktop;\n'
            )
            with patch.object(
                installation, 'run_with_retry', return_value=subprocess.CompletedProcess([], 0),
            ):
                self.assertTrue(installation._configure_desktop_defaults(root, 'alice', ['yazi', 'nautilus']))
            settings = ConfigParser()
            settings.read(mimeapps)
            defaults = settings['Default Applications']
            self.assertEqual(defaults['image/jpeg'], 'org.gnome.Loupe.desktop;')
            self.assertEqual(defaults['video/webm'], 'mpv.desktop;')
            self.assertEqual(defaults['application/zip'], 'org.gnome.FileRoller.desktop;')
            self.assertEqual(defaults['image/png'], 'custom-editor.desktop;')
            self.assertEqual(defaults['inode/directory'], 'org.gnome.Nautilus.desktop;')
            self.assertEqual(defaults['x-scheme-handler/http'], 'custom-browser.desktop;')
            self.assertEqual(settings['Added Associations']['application/pdf'], 'custom-pdf.desktop;')

    def test_iommu_parameters_follow_cpu_vendor(self) -> None:
        self.assertEqual(
            installation._gpu_passthrough_parameters('vendor_id : GenuineIntel\n'),
            ['intel_iommu=on', 'iommu=pt'],
        )
        self.assertEqual(
            installation._gpu_passthrough_parameters('vendor_id : AuthenticAMD\n'),
            ['iommu=pt'],
        )
        with self.assertRaises(ValueError):
            installation._gpu_passthrough_parameters('vendor_id : unknown\n')


if __name__ == '__main__':
    unittest.main()
