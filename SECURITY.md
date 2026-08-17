# Security Policy

Collectu takes the security of our software products and services seriously, 
which includes all source code repositories managed through our GitHub organizations.

If you believe you have found a security vulnerability in any Collectu-owned repository, 
please report it to us as described below.

The machine-readable version of this policy is served at
[`/.well-known/security.txt`](https://collectu.de/.well-known/security.txt) (RFC 9116), and its
full text at [`/.well-known/security-policy`](https://collectu.de/.well-known/security-policy).
A running Collectu Core also serves its own `security.txt` at
`http://<host>:8181/.well-known/security.txt`, pointing at the same contact.

## Single Point of Contact / Reporting Security Issues

*Please do not report security vulnerabilities through public GitHub issues.*

Instead, please report them to the Security Team at **security@collectu.de**.
This address is the single point of contact for receiving vulnerability reports for all Collectu products.

Please include, where possible:

- The product and version affected (see [CHANGELOG.md](CHANGELOG.md) / git tag)
- A description of the vulnerability and its potential impact
- Steps to reproduce, proof-of-concept code, or configuration needed to reproduce

You should receive a response within 24 hours. 
If for some reason you do not, please follow up via email to ensure we received your original message.

## Coordinated Vulnerability Disclosure

Collectu follows the principle of Coordinated Vulnerability Disclosure:

1. **Acknowledgement:** We confirm receipt of your report within 24 hours.
2. **Assessment:** We analyze and validate the report and keep you informed about the status.
3. **Remediation:** We develop and test a fix and release it as a security update via this repository.
4. **Disclosure:** We coordinate the publication of the vulnerability with the reporter.
   Please do not disclose the vulnerability publicly before a fix is available and a
   disclosure date has been agreed.

We will credit reporters in the release notes unless they prefer to remain anonymous.

## Safe Harbour

We will not pursue or support legal action against anyone who reports a vulnerability in good
faith under this policy, provided that you:

- Only test against installations and data you own or have explicit permission to test.
- Do not access, modify, delete, or exfiltrate other users' data.
- Do not degrade, disrupt, or overload our services — no denial-of-service, no spam, and no
  automated scanning that materially affects availability.
- Do not use social engineering, physical attacks, or attacks against our employees.
- Give us reasonable time to remediate before disclosing.

## Scope

**In scope**

- Collectu Core: the data engine, its API and user interface, the updater, and the hub
  communication (reporting, task execution, module download).
- The official modules shipped in `src/modules`.

**Out of scope**

- Findings that only apply to a deployment configured against the guidance in
  [Secure Configuration](#secure-configuration) — for example an unauthenticated API exposed
  directly to the internet.
- Third-party packages pulled in as module requirements. Report these to their maintainers;
  tell us as well if a Collectu module is the reason they are installed, and we will look at
  the requirement. The dependencies themselves are listed in the published SBOMs
  (see [below](#software-bill-of-materials-sbom)).
- Community-contributed modules published by third parties on the Collectu Hub. Report them to
  us anyway — we unpublish malicious modules — but they are not Collectu products.
- Missing hardening headers or raw scanner output, without a demonstrated impact.

## Security Updates and Support Period

- Security fixes are provided for the **latest released version** on the `main` branch of
  [github.com/core4x/collectu-core](https://github.com/core4x/collectu-core).
  Users are expected to stay on the latest version.
- Security-relevant releases are documented in [CHANGELOG.md](CHANGELOG.md).
- End date of the security support period: At least 5 years from now on.

### Installing security updates

Updates are distributed through this git repository and are user-triggered (Collectu does not install product updates automatically):

- **Frontend/API:** trigger the `update` command (requires `update` to be present in `allowed_commands` in `settings.ini`). The application pulls the latest version from the official repository and restarts automatically.
- **Manual:** run `git pull` in the installation directory and restart the application.
- **Docker:** pull the latest image and recreate the container.

## Secure Configuration

Collectu is intended to be operated in a trusted, access-controlled network. Before production use:

- Change the admin credentials and set `api_authentication = 1` in `settings.ini`.
- Do not expose the API and user interface (port `8181`) directly to the internet;
  use a TLS-terminating reverse proxy and restrict the bind address (`api_host`).
- Restrict `allowed_commands` to the minimum required set.
- Consider disabling automatic module and requirement downloads from the hub
  (`auto_install = 0`, `auto_download = 0`, `initial_download = 0`), since downloaded modules are executable code.
- Protect `settings.ini`, `configuration.yml`, and token files with restrictive file-system permissions.

See the "Product Information (EU Cyber Resilience Act)" section of the [README](README.md) for
full instructions on secure commissioning, updates, and secure decommissioning.

## Software Bill of Materials (SBOM)

SBOMs are produced by the release workflow
([`.github/workflows/main.yml`](.github/workflows/main.yml)) in CycloneDX (JSON) format and
published with every release, so there is nothing to generate on an installation:

| Document | Where to find it | What it covers |
|---|---|---|
| `sbom.cdx.json` | Committed in this repository, so it ships with the source and inside the container image | What Collectu Core declares: the requirements in `src/requirements.txt` |
| `src/interface/sbom.cdx.json` | Committed in the `src/interface` submodule, which is its own repository | What the API and user interface declare |
| `sbom.container.cdx.json` | Attached to each [GitHub release](https://github.com/core4x/collectu-core/releases) | The published container image as built, including its operating system packages (openssl, glibc, …) |

The published image additionally carries an SPDX SBOM and a provenance attestation on its
manifest, readable without pulling the image:

```bash
docker buildx imagetools inspect ghcr.io/core4x/collectu-core:latest --format "{{ json .SBOM }}"
```

The documents list dependencies, not vulnerabilities, and deliberately so: a scan result frozen
into a released file is out of date as soon as the next advisory is published. Match them
against an advisory database of your choice — `grype sbom:sbom.cdx.json`, for example.

The committed document covers the packages Collectu Core itself declares. Modules install their
own third-party requirements at runtime, so what is *actually* installed on a given device can
differ — a module requirement without a pinned version resolves to whatever was current at
install time. A Core that reports to the Collectu Hub therefore also sends the list of
distributions installed in its Python environment. 
Set `report_to_hub = 0` in `settings.ini` to opt out of all reporting.

## Integrity of Downloaded Modules

Modules downloaded from the Collectu Hub are executable code. Each module version is stored on
the Hub with the SHA-256 of its code, so a downloaded version can be checked against the one
that was reviewed. Commands pushed from the Hub (`restart`, `update`, `load`, …) carry an ES256
signature that Collectu Core verifies against the Hub's published keys
([`/.well-known/jwks.json`](https://api.collectu.de/.well-known/jwks.json)) before executing.
Verification is on by default; do not set the `VERIFY_TASK_SIGNATURE` environment variable to
`0` outside of development.

## Manufacturer Contact

| | |
|---|---|
| Manufacturer | Collectu GmbH |
| Postal address | Seidenstr. 36, 70174 Stuttgart, Germany |
| Security contact | security@collectu.de |
| Website | [https://collectu.de](https://collectu.de) |
