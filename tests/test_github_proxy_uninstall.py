from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / 'arch_bootstrap/scripts/uninstall-github-proxy-dl.sh'
)


class GitHubProxyUninstallTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_dir.cleanup)
        self.root = Path(temporary_dir.name)
        self.config = self.root / 'etc/makepkg.conf'
        self.config.parent.mkdir(parents=True)
        self.wrapper = self.root / 'usr/local/bin/github-proxy-dl'
        self.wrapper.parent.mkdir(parents=True)
        self.wrapper.write_text('Installed download wrapper fixture\n')

    def uninstall(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                'bash', '-c',
                'source "$1"; uninstall_github_proxy_dl "$2"',
                'uninstall-github-proxy-dl', str(SCRIPT_PATH), str(self.root),
            ],
            capture_output=True,
            text=True,
        )

    def test_restores_https_and_preserves_other_settings_on_repeated_runs(self) -> None:
        self.config.write_text(
            'DLAGENTS=(\n'
            "    'https::/usr/local/bin/github-proxy-dl %u %o'\n"
            "    'http::/usr/bin/wget -c -O %o %u'\n"
            ')\n'
            'MAKEFLAGS="-j6"\n'
        )

        for _ in range(2):
            result = self.uninstall()
            self.assertEqual(result.returncode, 0, result.stderr)

        self.assertFalse(self.wrapper.exists())
        self.assertEqual(
            self.config.read_text(),
            'DLAGENTS=(\n'
            '    \'https::/usr/bin/curl -qgb "" -fLC - --retry 3 --retry-delay 3 -o %o %u\'\n'
            "    'http::/usr/bin/wget -c -O %o %u'\n"
            ')\n'
            'MAKEFLAGS="-j6"\n',
        )

    def test_preserves_a_custom_https_agent(self) -> None:
        content = (
            "DLAGENTS=('https::/usr/bin/wget --timeout=20 -O %o %u')\n"
            'CFLAGS="-O3 -pipe"\n'
        )
        self.config.write_text(content)

        result = self.uninstall()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.config.read_text(), content)
        self.assertFalse(self.wrapper.exists())

    def test_restores_configuration_when_wrapper_is_already_missing(self) -> None:
        self.wrapper.unlink()
        self.config.write_text(
            "DLAGENTS=('https::/usr/local/bin/github-proxy-dl %u %o')\n"
        )

        result = self.uninstall()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.config.read_text(),
            'DLAGENTS=(\'https::/usr/bin/curl -qgb "" -fLC - --retry 3 --retry-delay 3 -o %o %u\')\n',
        )

    def test_removes_wrapper_when_configuration_is_missing(self) -> None:
        result = self.uninstall()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.wrapper.exists())
        self.assertFalse(self.config.exists())

    def test_keeps_wrapper_and_config_for_an_unsupported_reference(self) -> None:
        content = (
            "DLAGENTS=('https::/usr/local/bin/github-proxy-dl --custom %u %o')\n"
        )
        self.config.write_text(content)

        result = self.uninstall()

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.config.read_text(), content)
        self.assertEqual(
            self.wrapper.read_text(), 'Installed download wrapper fixture\n'
        )


if __name__ == '__main__':
    unittest.main()
