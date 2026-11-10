from __future__ import annotations

import os
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
        self.git_env = dict(
            os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
        )
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
            env=self.git_env,
        )

    def git(self, *args: str | Path) -> str:
        return subprocess.run(
            ['git', *map(str, args)],
            capture_output=True, text=True, check=True, env=self.git_env,
        ).stdout.strip()

    def config_values(self, config: Path, key: str) -> list[str]:
        result = subprocess.run(
            ['git', 'config', '--file', str(config), '--null', '--get-all', key],
            capture_output=True, text=True, env=self.git_env,
        )
        self.assertIn(result.returncode, (0, 1), result.stderr)
        return result.stdout.split('\0')[:-1]

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
        gitconfig = self.root / 'etc/gitconfig'
        git_proxy = (
            '[url "https://ghfast.top/https://github.com/"]\n'
            '\tinsteadOf = https://github.com/\n'
        )
        gitconfig.write_text(git_proxy)

        result = self.uninstall()

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.config.read_text(), content)
        self.assertEqual(
            self.wrapper.read_text(), 'Installed download wrapper fixture\n'
        )
        self.assertEqual(gitconfig.read_text(), git_proxy)

    def test_removes_system_proxy_rewrites_but_preserves_other_values(self) -> None:
        configs = [
            self.root / 'etc/gitconfig',
            self.root / 'etc/makepkg.d/gitconfig',
        ]
        for config in configs:
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text(
                '[user]\n'
                '\tname = Keep Me\n'
                '[url "https://ghfast.top/https://github.com/"]\n'
                '\tinsteadOf = https://github.com/\n'
                '\tinsteadOf = https://github.com/\n'
                '\tinsteadOf = gh:\n'
                '\tpushInsteadOf = keep-push:\n'
                '[url "https://gh-proxy.org/https://github.com/"]\n'
                '\tinsteadOf = https://github.com/\n'
                '[url "ssh://git@github.com/"]\n'
                '\tinsteadOf = https://github.com/\n'
                '[url "https://mirror.example/https://gitlab.com/"]\n'
                '\tinsteadOf = https://gitlab.com/\n',
            )

        for _ in range(2):
            result = self.uninstall()
            self.assertEqual(result.returncode, 0, result.stderr)

        for config in configs:
            with self.subTest(config=config):
                self.assertEqual(
                    self.config_values(
                        config, 'url.https://ghfast.top/https://github.com/.insteadof',
                    ),
                    ['gh:'],
                )
                self.assertEqual(
                    self.config_values(
                        config, 'url.https://gh-proxy.org/https://github.com/.insteadof',
                    ),
                    [],
                )
                self.assertEqual(
                    self.config_values(
                        config, 'url.https://ghfast.top/https://github.com/.pushinsteadof',
                    ),
                    ['keep-push:'],
                )
                self.assertEqual(
                    self.config_values(config, 'url.ssh://git@github.com/.insteadof'),
                    ['https://github.com/'],
                )
                self.assertEqual(
                    self.config_values(
                        config, 'url.https://mirror.example/https://gitlab.com/.insteadof',
                    ),
                    ['https://gitlab.com/'],
                )
                self.assertEqual(self.config_values(config, 'user.name'), ['Keep Me'])

    def test_cleans_all_omz_repositories_without_touching_other_projects(self) -> None:
        github = 'https://github.com/example/project.git'
        proxy = f'https://ghfast.top/{github}'
        backup = 'https://github.com/example/backup.git'
        repositories = []
        for home in ('root', 'home/alice', 'home/bob'):
            omz = self.root / home / '.oh-my-zsh'
            for suffix in ('', 'custom/plugins/first', 'custom/plugins/second plugin'):
                repo = omz / suffix
                self.git('init', '--quiet', repo)
                self.git('-C', repo, 'remote', 'add', 'origin', proxy)
                config = repo / '.git/config'
                self.git('config', '--file', config, '--add', 'remote.origin.url', proxy)
                self.git('config', '--file', config, '--add', 'remote.origin.url', backup)
                self.git(
                    'config', '--file', config, '--add', 'remote.origin.pushurl',
                    f'http://mirror.example/{github}',
                )
                self.git('config', '--file', config, '--add', 'remote.origin.pushurl', backup)
                self.git('-C', repo, 'remote', 'add', 'fork', proxy)
                self.git('-C', repo, 'remote', 'add', 'upstream', 'git@github.com:example/project.git')
                self.git(
                    '-C', repo, 'remote', 'add', 'gitlab',
                    'https://mirror.example/https://gitlab.com/example/project.git',
                )
                config.chmod(0o640)
                repositories.append((repo, config.stat()))

        other = self.root / 'home/alice/other-project'
        self.git('init', '--quiet', other)
        self.git('-C', other, 'remote', 'add', 'origin', proxy)

        for _ in range(2):
            result = self.uninstall()
            self.assertEqual(result.returncode, 0, result.stderr)

        for repo, before in repositories:
            with self.subTest(repo=repo):
                self.assertEqual(
                    self.git('-C', repo, 'remote', 'get-url', '--all', 'origin'),
                    f'{github}\n{backup}',
                )
                self.assertEqual(
                    self.git('-C', repo, 'remote', 'get-url', '--push', '--all', 'origin'),
                    f'{github}\n{backup}',
                )
                self.assertEqual(self.git('-C', repo, 'remote', 'get-url', 'fork'), github)
                self.assertEqual(
                    self.git('-C', repo, 'remote', 'get-url', 'upstream'),
                    'git@github.com:example/project.git',
                )
                self.assertEqual(
                    self.git('-C', repo, 'remote', 'get-url', 'gitlab'),
                    'https://mirror.example/https://gitlab.com/example/project.git',
                )
                after = (repo / '.git/config').stat()
                self.assertEqual(
                    (after.st_uid, after.st_gid, after.st_mode),
                    (before.st_uid, before.st_gid, before.st_mode),
                )
        self.assertEqual(self.git('-C', other, 'remote', 'get-url', 'origin'), proxy)

    def test_reports_invalid_git_configuration(self) -> None:
        config = self.root / 'etc/makepkg.d/gitconfig'
        config.parent.mkdir()
        content = '[url "https://ghfast.top/https://github.com/"\n'
        config.write_text(content)

        result = self.uninstall()

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(config.read_text(), content)


if __name__ == '__main__':
    unittest.main()
