# Security Policy

Collectu takes the security of our software products and services seriously, 
which includes all source code repositories managed through our GitHub organizations.

If you believe you have found a security vulnerability in any Collectu-owned repository, 
please report it to us as described below.

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

## Security Updates and Support Period

- Security fixes are provided for the **latest released version** on the `main` branch of
  [github.com/core4x/collectu-core](https://github.com/core4x/collectu-core).
  Users are expected to stay on the latest version.
- Security-relevant releases are documented in [CHANGELOG.md](CHANGELOG.md).
- End date of the security support period: At least 5 years from now on

### Installing security updates

Updates are distributed through this git repository and are user-triggered (Collectu does not install product updates automatically):

- **Frontend/API:** trigger the `update` command (requires `update` to be present in `allowed_commands` in `settings.ini`). The application pulls the latest version from the official repository and restarts automatically.
- **Manual:** run `git pull` in the installation directory and restart the application.
- **Docker:** pull the latest image and recreate the container.

## Secure Configuration

Collectu is intended to be operated in a trusted, access-controlled network. Before production use:

- Change the admin credentials and set `api_authentication = 1` in `settings.ini`.
- Do not expose the API (port `8181`) or frontend (port `8282`) directly to the internet;
  use a TLS-terminating reverse proxy and restrict the bind addresses (`api_host`, `frontend_host`).
- Restrict `allowed_commands` to the minimum required set.
- Consider disabling automatic module and requirement downloads from the hub
  (`auto_install = 0`, `auto_download = 0`, `initial_download = 0`), since downloaded modules are executable code.
- Protect `settings.ini`, `configuration.yml`, and token files with restrictive file-system permissions.

See the "Product Information (EU Cyber Resilience Act)" section of the [README](README.md) for
full instructions on secure commissioning, updates, and secure decommissioning.

## Software Bill of Materials (SBOM)

An SBOM in CycloneDX (JSON) format, including known-vulnerability information from the OSV
database, can be generated for any installation with:

```bash
python src/utils/generate_sbom.py
```

The output is written to `collectu-core-sbom.cdx.json`.

## Manufacturer Contact

| | |
|---|---|
| Manufacturer | Collectu GmbH |
| Postal address | Seidenstr. 36, 70174 Stuttgart, Germany |
| Security contact | security@collectu.de |
| Website | [https://collectu.de](https://collectu.de) |
