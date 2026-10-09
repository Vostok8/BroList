---
name: update-brolist-service
description: Research and add a new service to the BroList repository. Use when the user asks to add a service, app, website, platform, product, or provider to BroList/brolist.txt, including discovering required domains, subdomains, IPv4 addresses, or CIDR ranges, preparing a strict confirmation proposal, syncing the local repository with GitHub before edits, updating only the source list, validating with scripts/resolve.py, and pushing the approved brolist.txt change to main.
---

# Update BroList Service

## Overview

Use this skill to add a service to BroList with a confirm-before-edit workflow. Treat `brolist.txt` as the only source file to edit by default; generated files are handled later by GitHub Actions unless the user explicitly asks otherwise.

## Repository Rules

- Resolve the current BroList root with `git rev-parse --show-toplevel` and verify it contains `brolist.txt` and `scripts/resolve.py`.
- Synchronize the current repository with GitHub at skill startup, before researching or adding the service. `brolist.txt` is the authoritative source; the generated files listed below are replaceable outputs.
  - Inspect the current branch, staged and unstaged changes, then run `git fetch origin`. Compare `main` with `origin/main`, checking both `brolist.txt` and the paths changed by any local-only commits. Do not treat a cached `origin/main` as current after a failed fetch.
  - On `main` with no local-only commits and no pending source changes, replace local changes to the listed generated files with their committed versions, then run `git pull --ff-only origin main`. Continue in the current checkout. Being behind only on automatic output updates is a normal sync case and does not justify a temporary worktree.
  - If local-only commits change only the listed generated files, `brolist.txt` matches `origin/main`, and there are no pending changes outside those outputs, preserve the old HEAD on a named backup branch, then align `main` to `origin/main`. These output-only changes may be replaced without another confirmation. Never force-push them or publish them as part of the service addition.
  - If `brolist.txt` or other source files have local work, or another branch is checked out, preserve that work and use a clean temporary worktree based on `origin/main`. Inspect local `brolist.txt` changes for overlap with the proposed entries; report any unresolved source divergence. Do not automatically discard, stash, merge, rebase, or publish unrelated source work.
  - Skill invocation authorizes this preparatory synchronization of replaceable outputs. Confirmation is required for the proposed service entries, not for bringing an otherwise compatible local `main` up to date.
- In this skill, confirmation of the final list (including “добавляй”) authorizes editing, validation, committing, and pushing that list to `main`. Continue through all these steps without requesting the same approval again, unless the user explicitly limited the request to local changes or a draft.
- Push only the approved service change directly to `main`; unrelated commits must not be included.
- Do not manually author or commit generated outputs unless explicitly requested. Replacing their local changes during the synchronization described above is permitted:
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

Before editing `brolist.txt`, present exactly this format and wait for user confirmation:

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

- Re-check sync state if meaningful time has passed or new local changes appeared; use the isolation rule above when needed.
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
git push origin HEAD:main
```

Before committing, inspect the staged diff and ensure it contains only the approved source changes. In an isolated worktree, commit there and push `HEAD:main` so an old local `main` is not accidentally published.

If a normal push is rejected because GitHub Actions advanced `main`, fetch again and rebase only the current task's commits onto `origin/main`, then retry the normal push up to three times. Review the source diff after rebasing; rerun validation if the source list or resolver changed. Never force-push. Stop and explain a source conflict or repeated push failure rather than broadening the approved scope.

After pushing, fetch and verify the published commit is an ancestor of `origin/main`. Synchronize the original local `main` using the same source/output rules above, so automatic output changes do not leave it unnecessarily behind. If unrelated source work prevents synchronization, preserve it and report the remaining divergence. Remove the temporary worktree when it is no longer needed.

If validation fails, do not commit or push. Explain the failure and the safest next step.

## Final Response

Report:

- The section used or created.
- The entries added.
- Whether `scripts/resolve.py` passed.
- The commit hash if pushed.
- Any generated files that changed locally but were intentionally not committed.
