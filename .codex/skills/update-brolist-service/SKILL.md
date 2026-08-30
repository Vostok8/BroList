---
name: update-brolist-service
description: Research and add a new service to the BroList repository. Use when the user asks to add a service, app, website, platform, product, or provider to BroList/brolist.txt, including discovering required domains, subdomains, IPv4 addresses, or CIDR ranges, preparing a strict confirmation proposal, syncing the local repository with GitHub before edits, updating only the source list, validating with scripts/resolve.py, and pushing the approved brolist.txt change to main.
---

# Update BroList Service

## Overview

Use this skill to add a service to BroList with a confirm-before-edit workflow. Treat `brolist.txt` as the only source file to edit by default; generated files are handled later by GitHub Actions unless the user explicitly asks otherwise.

## Repository Rules

- Work from the current BroList checkout unless the user gives another one. Resolve its root with `git rev-parse --show-toplevel`, run repository commands from that root, and verify it contains `brolist.txt` and `scripts/resolve.py` before making changes.
- Synchronize with GitHub before editing:
  - Check `git status --short`.
  - If there are unrelated local changes, stop and explain what blocks a clean sync.
  - Run `git fetch origin` and `git pull --ff-only origin main` before changing `brolist.txt`.
- Push directly to `main` after approval and validation.
- Do not manually edit generated outputs unless explicitly requested:
  - `ips.txt`
  - `ips_v4.txt`
  - `ips_v6.txt`
  - `wireguard_allowed_ips.txt`
  - `shadowsocks_ips.txt`
  - `amnezia_sites.json`
  - `state/resolve_state.json`
- It is acceptable to run `python3 scripts/resolve.py` locally as validation. If generated files change, review the signal, then restore or avoid staging them unless the user explicitly wants those files committed.

## Workflow

### 1. Understand the Service

Identify the exact service name and intended use. If the service is ambiguous, ask one concise clarifying question before research.

### 2. Research Domains and Ranges

Use current internet research for service-owned domains, official documentation, support articles, app/web network behavior, package/update endpoints, auth domains, CDN domains, API domains, and known static IP ranges.

Prefer:

- Official service documentation.
- Vendor support pages about domains, firewall allowlists, network requirements, or API endpoints.
- DNS lookups and lightweight tests for candidate hostnames.
- Reputable technical references when official docs are incomplete.

Avoid adding overly broad infrastructure by default:

- Cloudflare, Akamai, Fastly, AWS, Google Cloud, Azure, or similar shared CDN/cloud IP ranges.
- Generic identity, analytics, payment, or support providers unless they are necessary for the service to function and the user confirms them.
- Wildcards. `brolist.txt` stores concrete domains, IPs, and CIDR ranges.

Static IPv4/CIDR entries are allowed only when they are officially published or clearly necessary. Prefer domain entries for CDN-backed services.

### 3. Present Strict Confirmation Format

Before editing files, present exactly this format and wait for user confirmation:

```markdown
Service: <service>
Placement: <existing section or proposed new section header>

ADD_REQUIRED:
- <domain-or-ip> - <short reason/source>

ADD_OPTIONAL:
- <domain-or-ip> - <short reason/source>

SKIP:
- <domain-or-ip> - <why not adding by default>

NOTES:
- <important uncertainty, broad range warning, or validation note>
```

Rules for the proposal:

- Keep each entry one concrete domain, IP, or CIDR.
- Put only high-confidence functional entries in `ADD_REQUIRED`.
- Put telemetry, analytics, auth providers, broad CDN aliases, or uncertain dependencies in `ADD_OPTIONAL`.
- Put unsafe or too-broad ranges in `SKIP`.
- Include the proposed destination section. If no existing section fits, propose a new section header such as `#AI | SERVICE` or `#DEV | SERVICE`.

Proceed only after the user confirms the final list, edits the list, or says an equivalent of "ok, add".

### 4. Edit `brolist.txt`

After confirmation:

- Re-check sync state if meaningful time has passed or new local changes appeared.
- Insert entries into the confirmed section.
- Preserve the file's existing style:
  - Section headers are comment lines such as `#AI | OPEN AI`.
  - One domain, IP, or CIDR per line.
  - Lowercase domains.
  - No inline source comments on entries.
  - Avoid duplicate entries already present elsewhere in the file.
- If creating a new section, place it near related categories.

### 5. Validate

Run:

```bash
python3 scripts/resolve.py
```

Then inspect:

```bash
git diff -- brolist.txt
git status --short
```

If generated files changed, do not stage them by default. If needed, restore generated outputs before staging so the commit contains only `brolist.txt`.

### 6. Commit and Push

Commit only `brolist.txt` by default:

```bash
git add brolist.txt
git commit -m "Add <service> to BroList"
git push origin main
```

If validation fails, do not commit or push. Explain the failure and the safest next step.

## Final Response

Report:

- The section used or created.
- The entries added.
- Whether `scripts/resolve.py` passed.
- The commit hash if pushed.
- Any generated files that changed locally but were intentionally not committed.
