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
OUTPUT_AMNEZIA_SITES = ROOT / "amnezia_sites.json"

DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?!-)[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+\.?$")


def _sorted_ip_entries(entries: set[str]) -> list[str]:
    def key(value: str):
        if "/" in value:
            net = ipaddress.ip_network(value, strict=False)
            return (net.version, 1, int(net.network_address), net.prefixlen, value)
        addr = ipaddress.ip_address(value)
        return (addr.version, 0, int(addr), value)

    return sorted(entries, key=key)


def _write_lines(path: Path, lines: list[str]) -> None:
    content = "\n".join(lines).rstrip("\n") + "\n"
    path.write_text(content, encoding="utf-8")


def _write_amnezia_sites(path: Path, domains: set[str]) -> None:
    items = [{"hostname": domain} for domain in sorted(domains)]
    path.write_text(
        json.dumps(items, ensure_ascii=False, indent=2, separators=(",", " : ")) + "\n",
        encoding="utf-8",
    )


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


def _parse_input() -> tuple[set[str], set[str], set[str]]:
    domains: set[str] = set()
    static_ipv4: set[str] = set()
    static_ipv6: set[str] = set()

    for raw_line in INPUT_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue

        try:
            addr = ipaddress.ip_address(line)
            if addr.version == 4:
                static_ipv4.add(str(addr))
            else:
                static_ipv6.add(str(addr))
            continue
        except ValueError:
            pass

        try:
            net = ipaddress.ip_network(line, strict=False)
            if net.version == 4:
                static_ipv4.add(str(net))
            else:
                static_ipv6.add(str(net))
            continue
        except ValueError:
            pass

        domain = line.lower().rstrip(".")
        if DOMAIN_RE.fullmatch(domain):
            domains.add(domain)

    return domains, static_ipv4, static_ipv6


def _resolve_records(domain: str) -> tuple[set[str], set[str]]:
    ipv4: set[str] = set()
    ipv6: set[str] = set()
    try:
        for item in socket.getaddrinfo(domain, None, socket.AF_UNSPEC, socket.SOCK_STREAM):
            sockaddr = item[4]
            if sockaddr and sockaddr[0]:
                ip = str(ipaddress.ip_address(sockaddr[0]))
                if ":" in ip:
                    ipv6.add(ip)
                else:
                    ipv4.add(ip)
    except socket.gaierror:
        return set(), set()

    return ipv4, ipv6


def main() -> int:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

    now = int(time.time())
    state = _load_state()
    domains_state: dict = state.get("domains", {})

    domains, static_ipv4, static_ipv6 = _parse_input()

    next_state_domains: dict[str, dict] = {}
    resolved_ipv4: set[str] = set()
    resolved_ipv6: set[str] = set()

    for domain in sorted(domains):
        resolved_v4, resolved_v6 = _resolve_records(domain)
        if resolved_v4 or resolved_v6:
            resolved_ipv4.update(resolved_v4)
            resolved_ipv6.update(resolved_v6)
            next_state_domains[domain] = {
                "ips_v4": _sorted_ip_entries(resolved_v4),
                "ips_v6": _sorted_ip_entries(resolved_v6),
                "last_success_ts": now,
            }
            continue

        previous = domains_state.get(domain)
        if not previous:
            continue

        prev_ips_v4 = previous.get("ips_v4") or previous.get("ips") or []
        prev_ips_v6 = previous.get("ips_v6") or []
        last_success_ts = int(previous.get("last_success_ts") or 0)

        if (prev_ips_v4 or prev_ips_v6) and (now - last_success_ts) <= RETENTION_SECONDS:
            resolved_ipv4.update(prev_ips_v4)
            resolved_ipv6.update(prev_ips_v6)
            next_state_domains[domain] = {
                "ips_v4": _sorted_ip_entries(set(prev_ips_v4)),
                "ips_v6": _sorted_ip_entries(set(prev_ips_v6)),
                "last_success_ts": last_success_ts,
            }

    merged_ipv4 = _sorted_ip_entries(static_ipv4 | resolved_ipv4)
    merged_ipv6 = _sorted_ip_entries(static_ipv6 | resolved_ipv6)
    merged_all = _sorted_ip_entries(static_ipv4 | resolved_ipv4 | static_ipv6 | resolved_ipv6)

    _write_lines(OUTPUT_IPS, merged_all)
    _write_lines(OUTPUT_IPS_V4, merged_ipv4)
    _write_lines(OUTPUT_IPS_V6, merged_ipv6)

    wg_entries = []
    for entry in merged_ipv4:
        if "/" in entry:
            wg_entries.append(entry)
        else:
            wg_entries.append(f"{entry}/32")
    _write_lines(OUTPUT_WG, [f"AllowedIPs = {', '.join(wg_entries)}"])

    _write_lines(OUTPUT_SS, merged_ipv4)
    _write_amnezia_sites(OUTPUT_AMNEZIA_SITES, domains)

    _save_state({"domains": next_state_domains})

    print(f"Domains in source: {len(domains)}")
    print(f"Static IPv4/CIDR in source: {len(static_ipv4)}")
    print(f"Static IPv6/CIDR in source: {len(static_ipv6)}")
    print(f"Final IPv4 entries: {len(merged_ipv4)}")
    print(f"Final IPv6 entries: {len(merged_ipv6)}")
    print(f"Final combined entries: {len(merged_all)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
