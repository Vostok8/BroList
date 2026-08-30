import importlib.util
import json
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "resolve.py"
SPEC = importlib.util.spec_from_file_location("resolve", MODULE_PATH)
resolve = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(resolve)


class GlobalAddressTests(unittest.TestCase):
    def test_filters_special_and_invalid_cached_addresses(self):
        self.assertEqual(
            resolve._global_addresses(
                {
                    "8.8.8.8",
                    "2606:4700:4700::1111",
                    "127.0.0.1",
                    "10.0.0.1",
                    "169.254.1.1",
                    "224.0.0.1",
                    "::1",
                    "fc00::1",
                    "fe80::1",
                    "ff02::1",
                    "not-an-ip",
                }
            ),
            {"8.8.8.8", "2606:4700:4700::1111"},
        )

    @patch.object(resolve.socket, "getaddrinfo")
    def test_resolver_publishes_only_global_addresses(self, getaddrinfo):
        getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0)),
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2606:4700:4700::1111", 0, 0, 0)),
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("::1", 0, 0, 0)),
        ]

        self.assertEqual(
            resolve._resolve_records("example.com"),
            ({"8.8.8.8"}, {"2606:4700:4700::1111"}),
        )


class InputValidationTests(unittest.TestCase):
    def test_rejects_noncanonical_cidr_with_line_number(self):
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "brolist.txt"
            input_file.write_text("example.com\n91.108.8.0/20\n", encoding="utf-8")

            with patch.object(resolve, "INPUT_FILE", input_file):
                error = r"brolist\.txt:2: '91\.108\.8\.0/20'"
                with self.assertRaisesRegex(ValueError, error):
                    resolve._parse_input()

    def test_accepts_canonical_cidr(self):
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "brolist.txt"
            input_file.write_text("example.com\n91.108.0.0/20\n", encoding="utf-8")

            with patch.object(resolve, "INPUT_FILE", input_file):
                domains, static_ipv4, static_ipv6 = resolve._parse_input()

            self.assertEqual(domains, {"example.com"})
            self.assertEqual(static_ipv4, {"91.108.0.0/20"})
            self.assertEqual(static_ipv6, set())


class AmneziaOutputTests(unittest.TestCase):
    def test_writes_hostname_and_ip_pairs_in_stable_order(self):
        with tempfile.TemporaryDirectory() as directory:
            output_file = Path(directory) / "amnezia_sites.json"
            resolve._write_amnezia_sites(
                output_file,
                {
                    "example.org": {"2606:4700:4700::1111"},
                    "example.com": {"8.8.8.8", "1.1.1.1"},
                },
            )

            self.assertEqual(
                json.loads(output_file.read_text(encoding="utf-8")),
                [
                    {"hostname": "example.com", "ip": "1.1.1.1"},
                    {"hostname": "example.com", "ip": "8.8.8.8"},
                    {"hostname": "example.org", "ip": "2606:4700:4700::1111"},
                ],
            )


if __name__ == "__main__":
    unittest.main()
