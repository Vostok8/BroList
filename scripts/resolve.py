#!/usr/bin/env python3
import ipaddress
import json
import re
import socket
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT_FILE = ROOT / "brolist.txt"
STATE_FILE = ROOT / "state" / "resolve_state.json"
RETENTION_SECONDS = 24 * 60 * 60

OUTPUT_IPS = ROOT / "ips.txt"
OUTPUT_IPS_V4 = ROOT / "ips_v4.txt"
OUTPUT_IPS_V6 = ROOT / "ips_v6.txt"
OUTPUT_WG = ROOT / "wireguard_allowed_ips.txt"
OUTPUT_SS = ROOT / "shadowsocks_ips.txt"

DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?!-)[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+\.?$")


def _sorted_ip_entries(entries: set[str]) -> list[str]:
    def key(value: str):
        if "/" in value:
            net = ipaddress.ip_network(value, strict=False)
            return (1, int(net.network_address), net.prefixlen, value)
        addr = ipaddress.ip_address(value)
        return (0, int(addr), value)

    return sorted(entries, key=key)


def _write_lines(path: Path, lines: list[str]) -> None:
    content = "\n".join(lines).rstrip("\n") + "\n"
    path.write_text(content, encoding="utf-8")


def _load_state() -> dict:
    if not STATE_FILE.exists():
        return {"domains": {}}
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"domains": {}}
        if "domains" not in data or not isinstance(data["domains"], dict):
            return {"domains": {}}
        return data
    except json.JSONDecodeError:
        return {"domains": {}}


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _parse_input() -> tuple[set[str], set[str]]:
    domains: set[str] = set()
    static_ipv4: set[str] = set()

    for raw_line in INPUT_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue

        try:
            addr = ipaddress.ip_address(line)
            if addr.version == 4:
                static_ipv4.add(str(addr))
            continue
        except ValueError:
            pass

        try:
            net = ipaddress.ip_network(line, strict=False)
            if net.version == 4:
                static_ipv4.add(str(net))
            continue
        except ValueError:
            pass

        domain = line.lower().rstrip(".")
        if DOMAIN_RE.fullmatch(domain):
            domains.add(domain)

    return domains, static_ipv4


def _resolve_a_records(domain: str) -> list[str]:
    ips = set()
    try:
        # AF_INET limits resolution to IPv4 as requested.
        for item in socket.getaddrinfo(domain, None, socket.AF_INET, socket.SOCK_STREAM):
            sockaddr = item[4]
            if sockaddr and sockaddr[0]:
                ips.add(sockaddr[0])
    except socket.gaierror:
        return []

    return _sorted_ip_entries(ips)


def main() -> int:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

    now = int(time.time())
    state = _load_state()
    domains_state: dict = state.get("domains", {})

    domains, static_ipv4 = _parse_input()

    next_state_domains: dict[str, dict] = {}
    resolved_ipv4: set[str] = set()

    for domain in sorted(domains):
        resolved = _resolve_a_records(domain)
        if resolved:
            resolved_ipv4.update(resolved)
            next_state_domains[domain] = {
                "ips": resolved,
                "last_success_ts": now,
            }
            continue

        previous = domains_state.get(domain)
        if not previous:
            continue

        prev_ips = previous.get("ips") or []
        last_success_ts = int(previous.get("last_success_ts") or 0)

        if prev_ips and (now - last_success_ts) <= RETENTION_SECONDS:
            resolved_ipv4.update(prev_ips)
            next_state_domains[domain] = {
                "ips": _sorted_ip_entries(set(prev_ips)),
                "last_success_ts": last_success_ts,
            }

    merged_ipv4 = _sorted_ip_entries(static_ipv4 | resolved_ipv4)

    _write_lines(OUTPUT_IPS, merged_ipv4)
    _write_lines(OUTPUT_IPS_V4, merged_ipv4)
    _write_lines(OUTPUT_IPS_V6, [])

    wg_entries = []
    for entry in merged_ipv4:
        if "/" in entry:
            wg_entries.append(entry)
        else:
            wg_entries.append(f"{entry}/32")
    _write_lines(OUTPUT_WG, [f"AllowedIPs = {', '.join(wg_entries)}"])

    _write_lines(OUTPUT_SS, merged_ipv4)

    _save_state({"domains": next_state_domains})

    print(f"Domains in source: {len(domains)}")
    print(f"Static IPv4/CIDR in source: {len(static_ipv4)}")
    print(f"Final IPv4 entries: {len(merged_ipv4)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
