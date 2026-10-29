from __future__ import annotations

import shutil
import ssl
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from arch_bootstrap import utils


ASSET_URL = 'https://github.com/example/project/releases/download/v1/asset.deb'
PROXY_HOST = 'proxy.invalid'
PAYLOAD = b'arch-bootstrap release asset fixture\n' * 32


class AssetHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        host = self.headers['Host']
        byte_range = self.headers.get('Range')
        self.server.requests.append((host, self.path, byte_range))
        status, body = self.server.responses.get((host, self.path), (404, b'Not found'))
        offset = int(byte_range.removeprefix('bytes=').removesuffix('-')) if byte_range else 0
        if status == 200 and byte_range:
            self.send_response(206)
            self.send_header('Content-Range', f'bytes {offset}-{len(body) - 1}/{len(body)}')
            body = body[offset:]
        else:
            self.send_response(status)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        pass


class TunnelHandler(BaseHTTPRequestHandler):
    """Terminate HTTPS locally; never forward a request to the public network."""

    def do_CONNECT(self) -> None:
        host, _, port = self.path.rpartition(':')
        if host not in {'github.com', PROXY_HOST, 'downloads.invalid'} or port != '443':
            self.send_error(502)
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.flush()
        self.close_connection = True
        context = (
            self.server.http1_context if host == 'downloads.invalid'
            else self.server.broken_http2_context
        )
        with context.wrap_socket(self.connection, server_side=True) as connection:
            protocol = connection.selected_alpn_protocol()
            self.server.protocols.append((host, protocol))
            # Model a route that advertises HTTP/2 but resets the connection.
            if protocol != 'h2':
                AssetHandler(connection, self.client_address, self.server)

    def log_message(self, format: str, *args: object) -> None:
        pass


@unittest.skipUnless(
    Path('/usr/bin/curl').is_file() and shutil.which('openssl') and ssl.HAS_ALPN,
    'curl, openssl, and TLS ALPN are required for download integration tests',
)
class GitHubProxyDownloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        certificates = tempfile.TemporaryDirectory()
        cls.addClassCleanup(certificates.cleanup)
        cls.certificate = Path(certificates.name) / 'certificate.pem'
        key = Path(certificates.name) / 'key.pem'
        subprocess.run(
            [
                'openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                '-keyout', str(key), '-out', str(cls.certificate), '-days', '1',
                '-subj', '/CN=github.com',
                '-addext', 'subjectAltName=DNS:github.com,DNS:proxy.invalid,DNS:downloads.invalid',
            ],
            check=True, capture_output=True, text=True,
        )
        cls.broken_http2_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        cls.broken_http2_context.load_cert_chain(cls.certificate, key)
        cls.broken_http2_context.set_alpn_protocols(['h2', 'http/1.1'])
        cls.http1_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        cls.http1_context.load_cert_chain(cls.certificate, key)
        cls.http1_context.set_alpn_protocols(['http/1.1'])

    def setUp(self) -> None:
        temporary_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_dir.cleanup)
        self.root = Path(temporary_dir.name)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), TunnelHandler)
        self.server.broken_http2_context = self.broken_http2_context
        self.server.http1_context = self.http1_context
        self.server.responses = {}
        self.server.requests = []
        self.server.protocols = []
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            kwargs={'poll_interval': 0.01},
            daemon=True,
        )
        self.thread.start()
        self.addCleanup(self.stop_server)
        with patch.object(utils, '_info'), patch.object(utils, '_debug'):
            utils.install_github_proxy_dl(self.root, f'https://{PROXY_HOST}')
        self.wrapper = self.root / 'usr/local/bin/github-proxy-dl'
        self.output = self.root / 'asset.deb.part'
        self.environment = {
            'PATH': '/usr/bin:/bin',
            'HOME': str(self.root),
            'LANG': 'C',
            'CURL_CA_BUNDLE': str(self.certificate),
            'https_proxy': f'http://127.0.0.1:{self.server.server_port}',
        }

    def stop_server(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def download(self, url: str = ASSET_URL) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(self.wrapper), url, str(self.output)],
            env=self.environment, cwd=self.root,
            capture_output=True, text=True, timeout=15,
        )

    def test_github_asset_download_avoids_broken_http2_route(self) -> None:
        self.server.responses[(PROXY_HOST, '/' + ASSET_URL)] = (200, PAYLOAD)

        result = self.download()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output.read_bytes(), PAYLOAD)
        self.assertEqual(self.server.protocols, [(PROXY_HOST, 'http/1.1')])
        self.assertEqual(self.server.requests, [(PROXY_HOST, '/' + ASSET_URL, None)])

    def test_failed_proxy_reports_error_and_resumes_direct_download(self) -> None:
        self.output.write_bytes(PAYLOAD[:17])
        self.server.responses[('github.com', '/example/project/releases/download/v1/asset.deb')] = (200, PAYLOAD)

        result = self.download()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output.read_bytes(), PAYLOAD)
        self.assertIn('404', result.stderr)
        self.assertEqual(
            self.server.protocols,
            [(PROXY_HOST, 'http/1.1'), ('github.com', 'http/1.1')],
        )
        self.assertEqual(
            self.server.requests[-1],
            ('github.com', '/example/project/releases/download/v1/asset.deb', 'bytes=17-'),
        )

    def test_failed_origin_preserves_partial_file_and_returns_curl_error(self) -> None:
        partial = PAYLOAD[:17]
        self.output.write_bytes(partial)

        result = self.download()

        self.assertEqual(result.returncode, 22)
        self.assertEqual(self.output.read_bytes(), partial)
        self.assertEqual(
            [host for host, _, _ in self.server.requests],
            [PROXY_HOST, 'github.com'],
        )

    def test_other_https_sources_bypass_github_proxy(self) -> None:
        self.server.responses[('downloads.invalid', '/asset.deb')] = (200, PAYLOAD)

        result = self.download('https://downloads.invalid/asset.deb')

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output.read_bytes(), PAYLOAD)
        self.assertEqual(self.server.requests, [('downloads.invalid', '/asset.deb', None)])


if __name__ == '__main__':
    unittest.main()
