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

- The product and version affected (see the [GitHub releases](https://github.com/core4x/collectu-core/releases) / git tag)
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
- Security-relevant releases are documented in the
  [release notes](https://github.com/core4x/collectu-core/releases).
- End date of the security support period: At least 5 years from now on.

### Installing security updates

Updates are distributed through this git repository. They are installed when a user triggers them, or automatically
for an app whose owner switched on automatic updates in the Collectu Hub:

- **Automatic (opt-in, off by default):** with `Auto-update` switched on in the app's settings on the Collectu Hub
  (`Account` → `Apps`), the Hub sends the app an `update` command on every push to the Collectu Core repository.
  The app installs the newest signed release, if it does not run it yet, and restarts; a push without a new release
  changes nothing. To opt out, switch `Auto-update` off for the app, or remove `update` from `allowed_commands` in
  `settings.ini` - the app then refuses every remote update, automatic or not.
- **Frontend/API:** trigger the `update` command (requires `update` to be present in `allowed_commands` in `settings.ini`). The application installs the newest release whose signature it could verify (see [Integrity of Updates](#integrity-of-updates)) and restarts automatically.
- **Manual:** run `python src/main.py --update` in the installation directory, which makes the same check. A plain `git pull` installs whatever the branch points to, without it.
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
| `sbom.cdx.json` | Attached to each [GitHub release](https://github.com/core4x/collectu-core/releases) | What Collectu Core declares: the requirements in `src/requirements.txt` |
| `src/interface/sbom.cdx.json` | Committed in the `src/interface` submodule, which is its own repository | What the API declares: the requirements in its `requirements*.txt` |
| `src/interface/sbom.frontend.cdx.json` | Committed in the `src/interface` submodule next to the user interface bundle, by the workflow that publishes the bundle | The npm packages the user interface is built from, production dependencies only. A superset of what the bundle contains |
| `sbom.container.cdx.json` | Attached to each [GitHub release](https://github.com/core4x/collectu-core/releases) | The published container image as built, including its operating system packages (openssl, glibc, …) |

The published image additionally carries an SPDX SBOM and a provenance attestation on its
manifest, readable without pulling the image:

```bash
docker buildx imagetools inspect ghcr.io/core4x/collectu-core:latest --format "{{ json .SBOM }}"
```

The documents list dependencies, not vulnerabilities, and deliberately so: a scan result frozen
into a released file is out of date as soon as the next advisory is published. Match them
against an advisory database of your choice — `grype sbom:sbom.cdx.json`, for example.

The declared documents cover the packages Collectu Core and its interface declare. Modules
install their own third-party requirements at runtime, so what is *actually* installed on a given
device can differ — a module requirement without a pinned version resolves to whatever was current at
install time. A Core that reports to the Collectu Hub therefore also sends the list of
distributions installed in its Python environment. 
Set `report_to_hub = 0` in `settings.ini` to opt out of all reporting.

## Integrity of Updates

Collectu Core updates itself from this git repository, and it installs only **releases signed by Collectu**. Every
release tag is signed with an ed25519 ssh key by the release workflow
([`.github/workflows/main.yml`](.github/workflows/main.yml)). Before an update, Collectu Core checks
([`src/utils/signed_releases.py`](src/utils/signed_releases.py)) that a release tag (`vX.Y.Z`):

- carries a valid ssh signature, made for git, by a key in [`security/allowed_signers`](security/allowed_signers);
- names itself as the tag it was found under, so a ref pointing at the signed tag of an older release is refused.

It walks through the releases it does not have yet, **oldest first**, and carries trust along
([`src/utils/updater.py`](src/utils/updater.py)):

- The first release is checked against the `allowed_signers` of the **version already installed**, never against the
  file of the release itself, so a release cannot vouch for its own key.
- Each release that passes hands its own `allowed_signers` on to the next one.
- A release that fails is skipped, and the walk goes on with the trust it had.
- The newest release that passes is installed, by the id of the commit its tag names.

That commit also fixes the commit of the `src/interface` submodule, so the one signature covers the API and user
interface as well. Commits on `main` after the newest release are not installed, and a tag on a commit the installation
already contains, whatever its number, is no release ahead of it.

Every release that fails a check is logged as an error. Please report such an error to security@collectu.de. If no
release ahead passes, nothing is installed and the update reports `Update refused: …`. A skipped release does not hold
back the newer ones: an unsigned `v99.0.0` that anybody with push access could create would otherwise keep every Core
on its version for good.

The check runs in Python with the `cryptography` package, so it works on hosts whose git is too old to verify ssh
signatures itself. To verify a release by hand with git 2.34 or later:

```bash
git fetch --tags
git -c gpg.format=ssh -c gpg.ssh.allowedSignersFile=security/allowed_signers verify-tag v2.3.1
```

The `src/interface` submodule is cloned and updated over ssh with GitHub's published host keys
([`security/github_known_hosts`](security/github_known_hosts)) as the only known hosts. Where port 22 is blocked, the
updater retries on GitHub's ssh service on port 443 (`ssh.github.com`), which has the same host keys.

`VERIFY_UPDATE_SIGNATURE=0` switches the check off. The updater then follows the branch of the checkout without
verifying anything, as it did before releases were signed. Set it for development only.

### Release key handling

The private key is the secret `RELEASE_SIGNING_KEY` of the GitHub environment `release`, whose required reviewers have
to approve a release before it can be signed. Without reviewers, anybody who can push to `main` gets a release signed.
Set "Prevent self-review", switch "Allow administrators to bypass" off, and allow deployments from `main` only. The
workflow refuses to tag with a key that is not in `security/allowed_signers`.

Keep a second, offline **recovery key** in `security/allowed_signers` as well, on a hardware token or in a safe, and
never in CI. It is what signs the rotation if the release key is lost or leaked. A Core trusts only the keys of the
version it runs, so without a second key, a lost release key means updating every Core by hand.

Publish the fingerprints of the trusted keys somewhere independent of GitHub, for example on collectu.de, so a release
can be checked by hand even when the repository itself is in doubt (`ssh-keygen -lf <key>.pub`).

**Planned rotation:**

1. Generate the new key: `ssh-keygen -t ed25519 -C "collectu-core release signing <year>" -f <name> -N ""`.
2. Add it to `security/allowed_signers` next to the old one, and release. The commit needs a type that makes a release
   (`fix:`, `feat:`). That release is signed with the old key.
3. Switch `RELEASE_SIGNING_KEY` to the new key. From the next release on, the new key signs.
4. Remove the old key from `security/allowed_signers` in a release signed with the new one, and destroy the old key.

There is no need to wait for the fleet in between. A Core that missed step 2 passes that release on its way to the
newest one and picks up the new key there.

**Lost release key:** sign a release with the recovery key that replaces the lost key with a new one, then continue
from step 3.

**Leaked release key:** whoever has it can sign releases that every Core still trusting the key accepts, so act at
once.

1. Sign a release with the recovery key, or with the leaked key if there is no recovery key, that removes the leaked
   key and adds a new one. Every Core that has passed this release refuses the leaked key from then on, even in the
   same update that installs a later release.
2. Switch `RELEASE_SIGNING_KEY` to the new key, and check GitHub's audit log and the releases for any you did not make.
3. A Core that installed a release you did not make has to be reinstalled by hand: clone it again, and verify the
   release tag with `git verify-tag` against fingerprints obtained independently of GitHub.

A Core that has not reached the revoking release yet still trusts the leaked key, and the walk cannot change that. A
release signed with it that is numbered *after* the revocation is refused on the way. One numbered *before* it is
accepted, like any release a Core trusts.

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
