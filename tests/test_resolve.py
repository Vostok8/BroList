import importlib.util
import socket
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


if __name__ == "__main__":
    unittest.main()
