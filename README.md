<h1 style="text-align: center;">
  Collectu
</h1>

Collectu is an open and Python-based no-code platform for fast and flexible data collection, combination, processing, 
analysis, visualization, and storage. From various data sources to different target systems. 
Collectu ships with a lot of game-changing advantages and is based on a modular architecture, 
which makes it easily adjustable and extendable.

> Visit [collectu.de](https://collectu.de) for further information.

--------

## Quick Start Guide

Collectu can be run directly with Python or as a container.
Please check [collectu.de/docs](https://collectu.de/docs) for detailed information.

### Python Execution

**Prerequisites:** Python 3.11 or newer (installed with the PATH option) and Git.

1. Clone the repository:

   ```bash
   git clone https://github.com/core4x/collectu-core.git
   ```

2. Run the installation script:
   - **Windows:** double-click `bin\windows\install_local.bat`
   - **Linux:** `sudo chmod +x bin/linux/install_local.sh && sudo bin/linux/install_local.sh`

3. Sign in on [collectu.de](https://collectu.de), generate an API access token, and download it
   to the root directory (`/collectu-core`). If you have a subscription, also download your
   Git access token to the root directory.

4. Start the application:
   - **Windows:** double-click `bin\windows\start_local.bat`
   - **Linux:** `sudo chmod +x bin/linux/start_local.sh && sudo bin/linux/start_local.sh`

   > Closing the terminal stops the application. For background execution, use the
   > `start_local_background` scripts.

<details>
<summary>Manual installation (without the install scripts)</summary>

```bash
git clone https://github.com/core4x/collectu-core.git
cd collectu-core

# Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Linux

# Install dependencies
pip install -r src/requirements.txt
```

Sign in and save your API access token (and Git access token, if subscribed) to the root
directory. 
Then start the application:

```bash
python src/main.py
```

</details>

### Container Execution

**Prerequisites:** Docker (and Docker Compose) installed. Any OCI-compatible runtime
(e.g. Podman) works as well.

**Docker Compose (recommended):** create a `compose.yaml`:

```yaml
services:
  collectu:
    image: ghcr.io/core4x/collectu-core:latest
    container_name: collectu-core
    restart: unless-stopped
    ports:
      - "8181:8181"   # API
      - "8282:8282"   # Frontend
    environment:  # Overwrites the settings.ini variables.
      # - RUN_AS_ROOT=1  # Run as root instead of appuser. Useful when host device access (e.g. USB ports) is required.
      - APP_DESCRIPTION=My Machine  # The description of the app.
      - CONFIG=configuration.yml  # The filepath to the configuration file.
      - AUTO_START=1  # Load configuration file on start-up.
      - AUTO_INSTALL=1  # Automatically install third party requirements.
      - INITIAL_DOWNLOAD=1  # Automatically download modules from hub during first start.
      - AUTO_DOWNLOAD=1  # Automatically download modules if they do not exist locally.
      - API=1  # Start the api.
      - API_HOST=0.0.0.0  # Host address of the api.
      - API_PORT=8181  # Port of the api.
      - API_AUTHENTICATION=1  # Is authentication required for the local api and frontend.
      - LOCAL_ADMIN_USERNAME=admin  # The local admin username.
      # - LOCAL_ADMIN_PASSWORD=  # The local admin password, a default password is generated on start-up.
      - MCP=0  # Enable the MCP server - the API has to be enabled.
      - FRONTEND=1  # Start the frontend.
      - FRONTEND_HOST=0.0.0.0  # Host address of the frontend.
      - FRONTEND_PORT=8282  # Port of the frontend.
      - MOTHERSHIPS=[]  # The host addresses of the motherships to report to.
      # - HUB_API_ACCESS_TOKEN=<token>  # The api access token of the hub profile collectu.de.
      - REPORT_TO_HUB=1  # Shall this app report and receive tasks from the hub collectu.de.
      - GIT_DISCOVERY_ACROSS_FILESYSTEM=1  # Required by third party package (GitPython) to access the local repository.
    volumes:
      - './configuration:/collectu-core/configuration'
      - './logs:/collectu-core/logs'
      - './data:/collectu-core/data'
      - './modules/inputs:/collectu-core/src/modules/inputs'
      - './modules/outputs:/collectu-core/src/modules/outputs'
      - './modules/processors:/collectu-core/src/modules/processors'
      - './git_access_token.txt:/collectu-core/git_access_token.txt'  # Delete this, if not used.
      - './api_access_token.txt:/collectu-core/api_access_token.txt'  # Delete this, if specified as env var.
```

Generate an API access token in your user dashboard on [collectu.de](https://collectu.de),
enter it in the compose file (or mount it as a file, see below), and start:

```bash
docker compose up
```

### First Steps

Open the frontend at [http://localhost:8282](http://localhost:8282) and log in. 
Create your first pipeline by adding a `random_1` input module and a `logger_1`
output module, connecting them, and saving and executing the configuration — the generated
random data appears in the console. See
[First Steps](https://collectu.de/docs) in the documentation for details.

> **Security note:** before production use, follow the secure commissioning steps in the
> [Instructions for Secure Use](#instructions-for-secure-use) below.

## License

Collectu-core is licensed under the terms of the Sustainable Use License.

The collectu interfaces (frontend and api) are licensed under the terms of the Collectu Enterprise License.

--------

## Product Information (EU Cyber Resilience Act, Annex II)

### Manufacturer

| |                                                                |
|---|----------------------------------------------------------------|
| Manufacturer | Collectu GmbH                                                  |
| Postal address | Seidenstr. 36, 70174 Stuttgart, Germany                        |
| E-mail | security@collectu.de |
| Website | [https://collectu.de](https://collectu.de)                     |

### Product Identification

| | |
|---|---|
| Product name | Collectu Core (`collectu-core`) |
| Product type | Software – no-code data collection, processing, analysis, visualization, and storage platform |
| Version | See [CHANGELOG.md](CHANGELOG.md) and git tags of this repository. |
| Unique identification | Repository: [github.com/core4x/collectu-core](https://github.com/core4x/collectu-core); each installation has a persistent `app_id` (UUID) stored in `settings.ini`. |

### Single Point of Contact for Vulnerabilities

Vulnerabilities can be reported to **security@collectu.de**.
The coordinated vulnerability disclosure policy is described in [SECURITY.md](SECURITY.md).

### Intended Purpose, Main Functions and Security Environment

Collectu is intended to collect, combine, process, analyze, visualize, and store data
from various data sources (e.g. industrial devices, protocols, APIs, files, databases)
and forward it to different target systems. Its main functions are:

- Modular input, processing, and output modules configured via YAML or the no-code frontend
- A REST API (default port `8181`) and a web frontend (default port `8282`) for configuration and operation
- Optional connection to the Collectu Hub for downloading modules and reporting app status
- Optional remote control by "motherships" via a configurable command allowlist

**Intended security environment:** Collectu is intended to be operated inside a trusted,
access-controlled network (e.g. a company LAN, OT network segment, or behind a VPN/reverse proxy).
It is **not** intended to be exposed directly to the public internet without additional
protection (TLS termination, network-level access control, enabled authentication).

**Security properties:**

- Optional API/frontend authentication with local user management (`api_authentication` in `settings.ini`)
- Configurable allowlist of remotely executable commands (`allowed_commands` in `settings.ini`)
- Updates are only applied from the official git repository and are user-triggered (see below)
- A Software Bill of Materials (SBOM) can be generated for every installation (see below)

### Known or Foreseeable Circumstances Leading to Cybersecurity Risks

The following uses are foreseeable misuse or risk-relevant circumstances and must be avoided or consciously managed:

- **Operating the API/frontend without authentication** (`api_authentication = 0`) in a network
  that is not fully trusted. Enable authentication and change the default admin credentials before use.
- **Exposing the API or frontend directly to the internet.** By default both bind to `0.0.0.0`
  (all interfaces) without TLS. Use a reverse proxy with TLS and restrict the bind address or firewall the ports.
- **Automatic download and installation of modules and third-party requirements from the Collectu Hub**
  (`auto_install`, `auto_download`, `initial_download` in `settings.ini`). Downloaded modules are executable
  Python code. Only use modules from trusted sources, or disable these options in restricted environments.
- **Custom and user-provided modules** run with the privileges of the Collectu process. Review custom modules
  before deployment and run Collectu under a least-privilege account or container.
- **Remote commands from motherships/hub** (`allowed_commands`). Restrict this list to the minimum needed;
  an overly permissive list allows remote restart, reconfiguration, or updates of the application.
- **Storing secrets in configuration files.** `settings.ini` and `configuration.yml` may contain credentials
  and tokens; protect them with file-system permissions and keep them out of backups accessible to third parties.

### EU Declaration of Conformity

Please request via security@collectu.de

### Technical Security Support and Support Period

Security support (vulnerability handling and security updates) is provided by Collectu GmbH
via the update mechanism described in [SECURITY.md](SECURITY.md). Security fixes are delivered
for the latest released version on the `main` branch of this repository.

End date of the security support period: At least 5 years from now on

### Instructions for Secure Use

Detailed instructions are available at [collectu.de/docs](https://collectu.de/docs). In summary:

**Secure commissioning (initial start-up):**

1. Change the default local admin credentials (`local_admin_username` / `local_admin_password` in `settings.ini`).
2. Enable authentication: set `api_authentication = 1`.
3. Restrict network exposure: set `api_host` / `frontend_host` to a specific interface or firewall
   ports `8181` and `8282`; place a TLS-terminating reverse proxy in front for remote access.
4. Reduce `allowed_commands` to the minimum required set.
5. In restricted environments, disable automatic module/requirement downloads
   (`auto_install = 0`, `auto_download = 0`, `initial_download = 0`).
6. Restrict file-system permissions on `settings.ini`, `configuration.yml`, and API token files.

**How changes to the product can affect data security:** Installing or updating modules,
changing `settings.ini` (especially authentication, bind addresses, and command allowlists),
and loading configurations from the hub change the code that is executed and the data that is
processed or transmitted. Review such changes before applying them in production.

**Installing security updates:** Updates (including security updates) are obtained from this
git repository. Trigger an update via the frontend/API `update` command or by running
`git pull` in the installation directory; the application restarts automatically after an
update. Docker users pull the latest image and recreate the container. See [SECURITY.md](SECURITY.md).

**Automatic security updates:** Collectu does **not** install product updates automatically;
updates are user-triggered, so no opt-out from automatic update installation is required.
The automatic download of *modules and third-party requirements* from the hub can be disabled
with `auto_install = 0`, `auto_download = 0`, and `initial_download = 0` in `settings.ini`.

**Secure decommissioning and removal of user data:**

1. Stop the application (or stop and remove the Docker container).
2. Revoke/delete API access tokens from the Collectu Hub associated with the installation.
3. Delete the installation directory, including `settings.ini`, `configuration.yml`,
   log files, and any locally stored data/reports (for Docker: remove the associated volumes).
4. Remove any data written by output modules to external target systems according to the
   policies of those systems.

### Information for Integrators

If Collectu is integrated into another product with digital elements, the integrator can use
the following to fulfil the essential requirements of CRA Annex I and the technical
documentation requirements of Annex VII:

- This section and [SECURITY.md](SECURITY.md) (vulnerability handling, support, secure configuration)
- The SBOM (see below) for the software composition of the product
- The source code and [CHANGELOG.md](CHANGELOG.md) in this repository for change tracking

### Software Bill of Materials (SBOM)

An SBOM in CycloneDX (JSON) format can be generated for any installation with:

```bash
python src/utils/generate_sbom.py
```

This produces `collectu-core-sbom.cdx.json`, covering all Python dependencies of the core
and interface components including known-vulnerability information from the OSV database.
