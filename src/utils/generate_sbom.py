"""
generate_sbom.py – CycloneDX 1.7 SBOM generator for collectu-core.

Reads all requirements files, fetches metadata from PyPI and checks
known vulnerabilities via the OSV API, then writes a CycloneDX 1.7
JSON SBOM to collectu-core-sbom.cdx.json.

Usage:
    python generate_sbom.py [--output <path>] [--no-vuln-check]

Dependencies: none (stdlib only – urllib, json, math, uuid, datetime, pathlib)
"""
import argparse
import json
import math
import re
import sys
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

CYCLONEDX_SPEC_VERSION = "1.7"
CYCLONEDX_SCHEMA = "http://cyclonedx.org/schema/bom-1.7.schema.json"

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


# ─────────────────────────────────────────────────────────────────────────────
# CVSS scoring (stdlib only)
#
# OSV reports the CVSS *vector* string in the "score" field of a severity entry.
# CycloneDX requires ratings[].score to be a *number* and ratings[].method to be
# one of a fixed enum, with the vector string living in ratings[].vector. These
# helpers turn an OSV severity entry into a schema-valid rating object.
# ─────────────────────────────────────────────────────────────────────────────

_CVSS3_AV = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.2}
_CVSS3_AC = {"L": 0.77, "H": 0.44}
_CVSS3_UI = {"N": 0.85, "R": 0.62}
_CVSS3_PR_U = {"N": 0.85, "L": 0.62, "H": 0.27}   # scope unchanged
_CVSS3_PR_C = {"N": 0.85, "L": 0.68, "H": 0.5}    # scope changed
_CVSS3_CIA = {"H": 0.56, "L": 0.22, "N": 0.0}

_CVSS2_AV = {"L": 0.395, "A": 0.646, "N": 1.0}
_CVSS2_AC = {"H": 0.35, "M": 0.61, "L": 0.71}
_CVSS2_AU = {"M": 0.45, "S": 0.56, "N": 0.704}
_CVSS2_CIA = {"N": 0.0, "P": 0.275, "C": 0.660}


def _parse_cvss_vector(vector: str) -> dict:
    """Split a CVSS vector string into a {metric: value} mapping."""
    metrics = {}
    for part in vector.split("/"):
        key, sep, value = part.partition(":")
        if sep:
            metrics[key.strip()] = value.strip()
    return metrics


def _roundup_31(value: float) -> float:
    """Official CVSS v3.1 Roundup (one decimal place)."""
    int_input = int(round(value * 100000))
    if int_input % 10000 == 0:
        return int_input / 100000.0
    return (math.floor(int_input / 10000) + 1) / 10.0


def _score_cvss3(metrics: dict, minor: str) -> float:
    """Compute the CVSS v3.0/v3.1 base score from a parsed vector."""
    scope_changed = metrics.get("S") == "C"
    av = _CVSS3_AV[metrics["AV"]]
    ac = _CVSS3_AC[metrics["AC"]]
    ui = _CVSS3_UI[metrics["UI"]]
    pr = (_CVSS3_PR_C if scope_changed else _CVSS3_PR_U)[metrics["PR"]]
    iss = 1 - (1 - _CVSS3_CIA[metrics["C"]]) * (1 - _CVSS3_CIA[metrics["I"]]) * (1 - _CVSS3_CIA[metrics["A"]])
    if scope_changed:
        impact = 7.52 * (iss - 0.029) - 3.25 * (iss - 0.02) ** 15
    else:
        impact = 6.42 * iss
    if impact <= 0:
        return 0.0
    exploitability = 8.22 * av * ac * pr * ui
    base = 1.08 * (impact + exploitability) if scope_changed else (impact + exploitability)
    base = min(base, 10.0)
    if minor == "3.0":
        return math.ceil(base * 10) / 10.0
    return _roundup_31(base)


def _score_cvss2(metrics: dict) -> float:
    """Compute the CVSS v2 base score from a parsed vector."""
    impact = 10.41 * (1 - (1 - _CVSS2_CIA[metrics["C"]]) *
                          (1 - _CVSS2_CIA[metrics["I"]]) *
                          (1 - _CVSS2_CIA[metrics["A"]]))
    exploitability = 20 * _CVSS2_AV[metrics["AV"]] * _CVSS2_AC[metrics["AC"]] * _CVSS2_AU[metrics["Au"]]
    f_impact = 0.0 if impact == 0 else 1.176
    return round(((0.6 * impact) + (0.4 * exploitability) - 1.5) * f_impact, 1)


def _severity_v3(score: float) -> str:
    if score == 0:
        return "none"
    if score < 4.0:
        return "low"
    if score < 7.0:
        return "medium"
    if score < 9.0:
        return "high"
    return "critical"


def _severity_v2(score: float) -> str:
    if score < 4.0:
        return "low"
    if score < 7.0:
        return "medium"
    return "high"


def build_rating(sev: dict) -> dict | None:
    """
    Turn an OSV severity entry into a schema-valid CycloneDX rating.

    OSV puts the CVSS vector in sev["score"]; we route it to "vector" and,
    where possible, compute a numeric "score" and qualitative "severity".
    """
    osv_type = sev.get("type", "")
    vector = sev.get("score", "")
    if not vector:
        return None

    rating: dict = {"source": {"name": "OSV"}, "vector": vector}
    metrics = _parse_cvss_vector(vector)
    try:
        if osv_type == "CVSS_V2":
            rating["method"] = "CVSSv2"
            score = _score_cvss2(metrics)
            rating["score"] = score
            rating["severity"] = _severity_v2(score)
        elif osv_type == "CVSS_V3":
            minor = metrics.get("CVSS", "3.1")
            rating["method"] = "CVSSv31" if minor == "3.1" else "CVSSv3"
            score = _score_cvss3(metrics, minor)
            rating["score"] = score
            rating["severity"] = _severity_v3(score)
        elif osv_type == "CVSS_V4":
            # No stdlib-only CVSS v4 calculator; keep the vector + method only.
            rating["method"] = "CVSSv4"
        else:
            rating["method"] = "other"
    except (KeyError, ValueError):
        # Malformed / incomplete vector: keep vector + method, drop numeric score.
        rating.pop("score", None)
        rating.pop("severity", None)
        rating.setdefault("method", "other")
    return rating


def build_vulnerability(vuln: dict, bom_ref: str) -> tuple[str, dict]:
    """
    Map an OSV vuln to a CycloneDX vulnerability object.

    Returns (vid, vulnerability) where ``vid`` is the de-duplication key
    (the CVE id when available, otherwise the OSV id).
    """
    aliases = vuln.get("aliases", [])
    osv_id = vuln.get("id", "")
    cve_id = next((a for a in aliases if a.startswith("CVE-")), None)
    vid = cve_id or osv_id or "UNKNOWN"

    ratings = []
    for sev in vuln.get("severity", []):
        rating = build_rating(sev)
        if rating:
            ratings.append(rating)

    # Every identifier except the primary vid becomes a related reference.
    ref_ids: list[str] = []
    for ident in [osv_id, *aliases]:
        if ident and ident != vid and ident not in ref_ids:
            ref_ids.append(ident)

    result: dict = {
        "bom-ref": f"vuln-{vid}",
        "id": vid,
        "source": {"name": "OSV", "url": f"https://osv.dev/vulnerability/{osv_id}"},
        "affects": [{"ref": bom_ref}],
    }
    if ref_ids:
        result["references"] = [{"id": r, "source": {"name": "OSV"}} for r in ref_ids]
    if ratings:
        result["ratings"] = ratings
    if vuln.get("summary"):
        result["description"] = vuln["summary"]
    if vuln.get("published"):
        result["published"] = vuln["published"]
    if vuln.get("modified"):
        result["updated"] = vuln["modified"]
    return vid, result


def merge_vulnerability(existing: dict, new: dict) -> None:
    """
    Merge a duplicate vulnerability (same vid) into an existing entry so that
    each CVE appears once with a unique bom-ref, unioning affects & references.
    """
    existing_refs = {a["ref"] for a in existing["affects"]}
    for affected in new.get("affects", []):
        if affected["ref"] not in existing_refs:
            existing["affects"].append(affected)
            existing_refs.add(affected["ref"])

    references = existing.get("references", [])
    seen_ids = {r["id"] for r in references}
    for ref in new.get("references", []):
        if ref["id"] not in seen_ids:
            references.append(ref)
            seen_ids.add(ref["id"])
    # Also fold in the other record's own OSV id (from its source URL).
    if references:
        existing["references"] = references

    if "ratings" not in existing and "ratings" in new:
        existing["ratings"] = new["ratings"]
    if new.get("updated") and new["updated"] > existing.get("updated", ""):
        existing["updated"] = new["updated"]


def main():
    parser = argparse.ArgumentParser(description="Generate CycloneDX 1.7 SBOM for collectu-core.")
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
    print("\nFetching metadata from PyPI ...")
    components: list[dict] = []
    # Keyed by vid (CVE id when available) so each vulnerability appears once
    # with a unique bom-ref; duplicates from OSV aliases are merged.
    vuln_map: dict[str, dict] = {}
    advisory_count = 0  # raw OSV advisories, before de-duplication by CVE

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
        print(f"  [{i+1}/{len(all_packages)}] {name}=={version} ... ", end="", flush=True)

        meta = fetch_pypi(name, version)
        comp = build_component(pkg, meta, i)
        components.append(comp)

        if not args.no_vuln_check:
            vulns = fetch_osv(name, version)
            advisory_count += len(vulns)
            for v in vulns:
                vid, vobj = build_vulnerability(v, comp["bom-ref"])
                if vid in vuln_map:
                    merge_vulnerability(vuln_map[vid], vobj)
                else:
                    vuln_map[vid] = vobj
            status = f"OK  ({len(vulns)} advisor{'ies' if len(vulns) != 1 else 'y'})"
        else:
            status = "OK  (vuln check skipped)"

        print(status)

    vulnerabilities: list[dict] = list(vuln_map.values())

    # 3. Build CycloneDX document
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    sbom = {
        "$schema": CYCLONEDX_SCHEMA,
        "bomFormat": "CycloneDX",
        "specVersion": CYCLONEDX_SPEC_VERSION,
        "version": 1,
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "metadata": {
            "timestamp": now,
            "tools": {
                "components": [
                    {
                        "type": "application",
                        "name": "generate_sbom.py",
                        "version": "1.1.0",
                        "publisher": COMPONENT_AUTHOR,
                        "externalReferences": [
                            {"type": "vcs", "url": COMPONENT_HOMEPAGE},
                        ],
                    }
                ]
            },
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
            merged = advisory_count - vuln_count
            note = f" ({advisory_count} advisories, {merged} merged by CVE)" if merged else ""
            print(f"  Vulnerabilities: {vuln_count}{note}  <- review recommended!")
        else:
            print(f"  Vulnerabilities: {vuln_count}  (none found)")
    print("=" * 60)

    return 1 if vuln_count else 0


if __name__ == "__main__":
    sys.exit(main())
