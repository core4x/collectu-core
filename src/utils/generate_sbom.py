"""
generate_sbom.py – CycloneDX 1.4 SBOM generator for collectu-core.

Reads all requirements files, fetches metadata from PyPI and checks
known vulnerabilities via the OSV API, then writes a CycloneDX 1.4
JSON SBOM to collectu-core-sbom.cdx.json.

Usage:
    python generate_sbom.py [--output <path>] [--no-vuln-check]

Dependencies: none (stdlib only – urllib, json, uuid, datetime, pathlib)
"""
import argparse
import json
import re
import sys
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent.parent.parent

REQUIREMENTS_FILES = [
    ("core", SCRIPT_DIR / "src" / "requirements.txt"),
    ("interface", SCRIPT_DIR / "src" / "interface" / "requirements.txt"),
    ("interface-mcp", SCRIPT_DIR / "src" / "interface" / "requirements-mcp.txt"),
]

# Docker base image (from Dockerfile)
BASE_IMAGE_NAME = "python"
BASE_IMAGE_VERSION = "3.14.3"

COMPONENT_NAME = "collectu-core"
COMPONENT_VERSION = "latest"
COMPONENT_DESCRIPTION = "Collectu Core"
COMPONENT_AUTHOR = "Collectu GmbH"
COMPONENT_HOMEPAGE = "https://github.com/core4x/collectu-core"

PYPI_API = "https://pypi.org/pypi/{name}/{version}/json"
OSV_API = "https://api.osv.dev/v1/query"

REQUEST_TIMEOUT = 10


def parse_requirements(path: Path) -> list[dict]:
    """
    Return list of {name, version, source} dicts from a requirements.txt.
    """
    packages = []
    if not path.exists():
        print(f"  [WARN] File not found: {path}", file=sys.stderr)
        return packages

    with path.open(encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            # Skip comments and blank lines
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            # Match "name==version" (pinned) or "name>=version" etc.
            m = re.match(r"^([A-Za-z0-9_\-\.]+)\s*([=<>!~]{1,2})\s*([^\s;]+)", line)
            if m:
                packages.append({
                    "name": m.group(1),
                    "specifier": m.group(2),
                    "version": m.group(3),
                    "source": str(path.relative_to(SCRIPT_DIR)),
                })
            else:
                # Package without version pin
                name = re.match(r"^([A-Za-z0-9_\-\.]+)", line)
                if name:
                    packages.append({
                        "name": name.group(1),
                        "specifier": "",
                        "version": "",
                        "source": str(path.relative_to(SCRIPT_DIR)),
                    })
    return packages


def fetch_pypi(name: str, version: str) -> dict:
    """
    Fetch package metadata from PyPI. Returns {} on error.
    """
    url = PYPI_API.format(name=name, version=version) if version else \
          f"https://pypi.org/pypi/{name}/json"
    try:
        with urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read())
        info = data.get("info", {})
        # Resolve license
        license_name = info.get("license") or ""
        if not license_name and info.get("classifiers"):
            for clf in info["classifiers"]:
                if clf.startswith("License ::"):
                    parts = clf.split(" :: ")
                    license_name = parts[-1]
                    break
        return {
            "description": info.get("summary", ""),
            "license": license_name.strip() or "UNKNOWN",
            "homepage": info.get("home_page") or info.get("project_url") or "",
            "author": info.get("author") or info.get("maintainer") or "",
            "requires_python": info.get("requires_python") or "",
        }
    except Exception as e:
        print(f"  [WARN] PyPI lookup failed for {name}=={version}: {e}", file=sys.stderr)
        return {}


def fetch_osv(name: str, version: str) -> list[dict]:
    """
    Query OSV for known vulnerabilities. Returns list of vuln dicts.
    """
    if not version:
        return []
    payload = json.dumps({
        "version": version,
        "package": {"name": name, "ecosystem": "PyPI"},
    }).encode()
    try:
        req = urllib.request.Request(
            OSV_API,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read())
        return data.get("vulns", [])
    except Exception as e:
        print(f"  [WARN] OSV lookup failed for {name}=={version}: {e}", file=sys.stderr)
        return []


def make_purl(name: str, version: str) -> str:
    # Normalise PyPI name (PEP 503)
    canonical = re.sub(r"[-_.]+", "-", name).lower()
    if version:
        return f"pkg:pypi/{canonical}@{version}"
    return f"pkg:pypi/{canonical}"


def build_component(pkg: dict, meta: dict, index: int) -> dict:
    """
    Build a CycloneDX component object for a Python package.
    """
    comp: dict = {
        "type": "library",
        "bom-ref": f"pkg:pypi/{pkg['name'].lower()}@{pkg['version']}-{index}",
        "name": pkg["name"],
        "version": pkg["version"] or "unknown",
        "purl": make_purl(pkg["name"], pkg["version"]),
        "properties": [
            {"name": "collectu:source", "value": pkg["source"]},
        ],
    }
    if meta.get("description"):
        comp["description"] = meta["description"]
    if meta.get("license"):
        comp["licenses"] = [{"license": {"name": meta["license"]}}]
    refs = []
    if meta.get("homepage"):
        refs.append({"type": "website", "url": meta["homepage"]})
    if refs:
        comp["externalReferences"] = refs
    return comp


def build_vulnerability(vuln: dict, bom_ref: str) -> dict:
    """
    Map an OSV vuln to a CycloneDX vulnerability object.
    """
    aliases = vuln.get("aliases", [])
    cve_id = next((a for a in aliases if a.startswith("CVE-")), None)
    vid = cve_id or vuln.get("id", "UNKNOWN")

    ratings = []
    for sev in vuln.get("severity", []):
        score_type = sev.get("type", "")
        score_val = sev.get("score", "")
        if score_type and score_val:
            ratings.append({"method": score_type, "score": score_val})

    result: dict = {
        "bom-ref": f"vuln-{vid}",
        "id": vid,
        "source": {"name": "OSV", "url": f"https://osv.dev/vulnerability/{vuln.get('id', '')}"},
        "affects": [{"ref": bom_ref}],
    }
    if aliases:
        result["references"] = [{"id": a, "source": {"name": "OSV"}} for a in aliases]
    if ratings:
        result["ratings"] = ratings
    if vuln.get("summary"):
        result["description"] = vuln["summary"]
    if vuln.get("modified"):
        result["updated"] = vuln["modified"]
    return result


def main():
    parser = argparse.ArgumentParser(description="Generate CycloneDX 1.4 SBOM for collectu-core.")
    parser.add_argument("--output", default=str(SCRIPT_DIR / "collectu-core-sbom.cdx.json"),
                        help="Output file path (default: collectu-core-sbom.cdx.json)")
    parser.add_argument("--no-vuln-check", action="store_true",
                        help="Skip OSV vulnerability check (faster, offline-friendly)")
    args = parser.parse_args()

    #1. Collect all packages
    all_packages: list[dict] = []
    seen: set[str] = set()

    for label, req_file in REQUIREMENTS_FILES:
        print(f"\nParsing [{label}]: {req_file.relative_to(SCRIPT_DIR)}")
        pkgs = parse_requirements(req_file)
        for p in pkgs:
            key = p["name"].lower()
            if key not in seen:
                seen.add(key)
                all_packages.append(p)
                print(f"  + {p['name']}=={p['version']}  ({p['source']})")
            else:
                print(f"  ~ {p['name']}=={p['version']}  (duplicate, skipped)")

    print(f"\nTotal unique packages: {len(all_packages)}")

    # 2. Fetch metadata & build components
    print("\nFetching metadata from PyPI …")
    components: list[dict] = []
    vulnerabilities: list[dict] = []

    # Docker base image component
    components.append({
        "type": "container",
        "bom-ref": f"pkg:docker/{BASE_IMAGE_NAME}@{BASE_IMAGE_VERSION}",
        "name": BASE_IMAGE_NAME,
        "version": BASE_IMAGE_VERSION,
        "purl": f"pkg:docker/{BASE_IMAGE_NAME}@{BASE_IMAGE_VERSION}",
        "description": "Official Python base container image",
        "externalReferences": [
            {"type": "website", "url": f"https://hub.docker.com/_/{BASE_IMAGE_NAME}"},
        ],
        "properties": [
            {"name": "collectu:source", "value": "Dockerfile"},
        ],
    })

    for i, pkg in enumerate(all_packages):
        name = pkg["name"]
        version = pkg["version"]
        print(f"  [{i+1}/{len(all_packages)}] {name}=={version} … ", end="", flush=True)

        meta = fetch_pypi(name, version)
        comp = build_component(pkg, meta, i)
        components.append(comp)

        if not args.no_vuln_check:
            vulns = fetch_osv(name, version)
            for v in vulns:
                vulnerabilities.append(build_vulnerability(v, comp["bom-ref"]))
            status = f"OK  ({len(vulns)} vuln{'s' if len(vulns) != 1 else ''})"
        else:
            status = "OK  (vuln check skipped)"

        print(status)

    # 3. Build CycloneDX document
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.4",
        "version": 1,
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "metadata": {
            "timestamp": now,
            "tools": [
                {
                    "vendor": "Collectu GmbH",
                    "name": "generate_sbom.py",
                    "version": "1.0.0",
                    "externalReferences": [
                        {"type": "vcs", "url": COMPONENT_HOMEPAGE},
                    ],
                }
            ],
            "authors": [{"name": COMPONENT_AUTHOR}],
            "component": {
                "type": "application",
                "bom-ref": f"pkg:github/core4x/{COMPONENT_NAME}@{COMPONENT_VERSION}",
                "name": COMPONENT_NAME,
                "version": COMPONENT_VERSION,
                "description": COMPONENT_DESCRIPTION,
                "purl": f"pkg:github/core4x/{COMPONENT_NAME}@{COMPONENT_VERSION}",
                "externalReferences": [
                    {"type": "vcs", "url": COMPONENT_HOMEPAGE},
                    {"type": "website", "url": "https://collectu.de"},
                ],
            },
        },
        "components": components,
    }

    if vulnerabilities:
        sbom["vulnerabilities"] = vulnerabilities

    # 4. Write output
    output_path = Path(args.output)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(sbom, f, indent=2, ensure_ascii=False)

    vuln_count = len(vulnerabilities)
    comp_count = len(components)

    print(f"\n{'=' * 60}")
    print(f"  SBOM written to: {output_path}")
    print(f"  Components:      {comp_count}  ({comp_count - 1} Python packages + 1 base image)")
    if not args.no_vuln_check:
        if vuln_count:
            print(f"  Vulnerabilities: {vuln_count}  ← review recommended!")
        else:
            print(f"  Vulnerabilities: {vuln_count}  (none found)")
    print("=" * 60)

    return 1 if vuln_count else 0


if __name__ == "__main__":
    sys.exit(main())
