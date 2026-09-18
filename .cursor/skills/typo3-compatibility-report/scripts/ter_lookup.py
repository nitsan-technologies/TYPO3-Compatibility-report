#!/usr/bin/env python3
"""Look up TYPO3 extension latest version and major-version compatibility on TER.

Usage:
  python3 ter_lookup.py --majors 12,13 news seo my_ext
  python3 ter_lookup.py --majors 12,13 < keys.json

JSON stdin:
  {"keys": ["news", "seo"], "majors": [12, 13]}
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

API_BASE = "https://extensions.typo3.org/api/v1"
USER_AGENT = "TYPO3 13.4.0"
REQUEST_PAUSE_S = 0.15
TIMEOUT_S = 30
ABANDONED_OWNER = "abandoned_extensions"
GIT_BRANCHES = ("main", "master")
GITHUB_REPO = re.compile(
    r"^https?://(?:www\.)?github\.com/([^/]+)/([^/#?]+)",
    re.IGNORECASE,
)
GITLAB_REPO = re.compile(
    r"^https?://(?:www\.)?gitlab\.com/(.+?)/?$",
    re.IGNORECASE,
)
TYPO3_MAJOR_IN_CONSTRAINT = re.compile(r"(?<![\d.])(\d{1,2})(?:\.\d+)*")
EAP_EXTENSIONS_PATH = Path(__file__).resolve().parent / "eap_extensions.json"
_EAP_URLS: dict[str, str] | None = None


def load_eap_urls() -> dict[str, str]:
    global _EAP_URLS
    if _EAP_URLS is not None:
        return _EAP_URLS
    urls: dict[str, str] = {}
    if EAP_EXTENSIONS_PATH.is_file():
        data = json.loads(EAP_EXTENSIONS_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            for key, url in data.items():
                if not key or not url:
                    continue
                urls[str(key).strip().lower()] = str(url).strip()
    _EAP_URLS = urls
    return _EAP_URLS


def eap_url_for(key: str) -> str | None:
    return load_eap_urls().get(key.strip().lower()) or None


def version_sort_key(number: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", number or "")
    return tuple(int(p) for p in parts) if parts else (0,)


def unwrap(data: Any) -> Any:
    """TER wraps some payloads as [{...}] or [[{...}, {...}]]."""
    if isinstance(data, list) and data and isinstance(data[0], list):
        return data[0]
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0] if "key" in data[0] and len(data) == 1 else data
    return data


def request_url(url: str, accept: str = "*/*") -> tuple[int, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": accept,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as response:
            body = response.read().decode("utf-8", errors="replace")
            return response.status, body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, body
    except urllib.error.URLError as exc:
        raise SystemExit(f"Request failed for {url}: {exc}") from exc


def request_json(path: str) -> tuple[int, Any]:
    status, body = request_url(API_BASE + path, accept="application/json")
    if not body:
        return status, None
    try:
        return status, json.loads(body)
    except json.JSONDecodeError:
        return status, {"error": body}


def empty_result(
    majors: list[int],
    found: bool,
    latest: str | None = None,
    key: str = "",
) -> dict[str, Any]:
    return {
        "found": found,
        "latest": latest,
        "compatibility": {str(major): False for major in majors},
        "abandoned": False,
        "repository_url": None,
        "git_compatibility": {str(major): False for major in majors},
        "eap_url": eap_url_for(key) if key else None,
    }


def compatibility_from_versions(versions: list[dict[str, Any]], majors: list[int]) -> dict[str, bool]:
    supported: set[int] = set()
    for version in versions:
        for major in version.get("typo3_versions") or []:
            try:
                supported.add(int(major))
            except (TypeError, ValueError):
                continue
    return {str(major): major in supported for major in majors}


def latest_from_versions(versions: list[dict[str, Any]]) -> str | None:
    numbers = [
        str(version.get("number"))
        for version in versions
        if version.get("number")
    ]
    if not numbers:
        return None
    return max(numbers, key=version_sort_key)


def normalize_repo_url(url: str | None) -> str | None:
    if not url:
        return None
    cleaned = url.strip().rstrip("/")
    if not cleaned:
        return None
    if cleaned.startswith("http://"):
        cleaned = "https://" + cleaned[len("http://") :]
    if cleaned.endswith(".git"):
        cleaned = cleaned[:-4]
    return cleaned or None


def composer_json_urls(repo_url: str) -> list[str]:
    github = GITHUB_REPO.match(repo_url)
    if github:
        owner, repo = github.group(1), github.group(2)
        repo = repo.removesuffix(".git")
        return [
            f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/composer.json"
            for branch in GIT_BRANCHES
        ]
    gitlab = GITLAB_REPO.match(repo_url)
    if gitlab:
        path = gitlab.group(1).removesuffix(".git").rstrip("/")
        path = path.split("/-/")[0]
        return [
            f"https://gitlab.com/{path}/-/raw/{branch}/composer.json"
            for branch in GIT_BRANCHES
        ]
    return []


def majors_from_constraint(constraint: str) -> set[int]:
    majors: set[int] = set()
    for match in TYPO3_MAJOR_IN_CONSTRAINT.finditer(constraint or ""):
        major = int(match.group(1))
        if 6 <= major <= 20:
            majors.add(major)
    return majors


def git_typo3_majors(repo_url: str) -> set[int]:
    for url in composer_json_urls(repo_url):
        status, body = request_url(url, accept="application/json")
        time.sleep(REQUEST_PAUSE_S)
        if status != 200 or not body.strip():
            continue
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        require = data.get("require") if isinstance(data.get("require"), dict) else {}
        constraint = str(require.get("typo3/cms-core") or require.get("typo3/cms") or "")
        return majors_from_constraint(constraint)
    return set()


def as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return value[0]
    return {}


def lookup_key(key: str, majors: list[int]) -> dict[str, Any]:
    encoded = urllib.parse.quote(key.lower(), safe="")
    status, payload = request_json(f"/extension/{encoded}")
    time.sleep(REQUEST_PAUSE_S)

    if status == 404:
        return empty_result(majors, found=False, key=key)
    if status != 200:
        raise SystemExit(f"TER lookup failed for '{key}' (HTTP {status}): {payload}")

    extension = as_dict(unwrap(payload))
    owner = str(extension.get("owner") or "")
    meta = as_dict(extension.get("meta"))
    repo = normalize_repo_url(str(meta.get("repository_url") or "") or None)
    abandoned = owner == ABANDONED_OWNER

    vstatus, vpayload = request_json(f"/extension/{encoded}/versions")
    time.sleep(REQUEST_PAUSE_S)
    if vstatus == 200:
        versions = unwrap(vpayload)
        if not isinstance(versions, list):
            versions = [versions] if versions else []
        versions = [v for v in versions if isinstance(v, dict)]
        latest = latest_from_versions(versions)
        compat = compatibility_from_versions(versions, majors)
    else:
        current = as_dict(extension.get("current_version"))
        latest = str(current.get("number")) if current.get("number") else None
        compat = empty_result(majors, found=True, key=key)["compatibility"]
        if current.get("typo3_versions"):
            compat = compatibility_from_versions([current], majors)

    result = {
        "found": True,
        "latest": latest,
        "compatibility": compat,
        "abandoned": abandoned,
        "repository_url": repo,
        "git_compatibility": {str(major): False for major in majors},
        "eap_url": eap_url_for(key),
    }

    if repo and any(not compat.get(str(major), False) for major in majors):
        git_majors = git_typo3_majors(repo)
        result["git_compatibility"] = {str(major): major in git_majors for major in majors}

    return result


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Look up latest TER version and TYPO3 major compatibility for extension keys."
    )
    parser.add_argument(
        "--majors",
        help="Comma-separated TYPO3 major versions, e.g. 12,13. Optional if JSON stdin includes majors.",
    )
    parser.add_argument(
        "keys",
        nargs="*",
        help="Extension keys. Optional if JSON stdin includes keys.",
    )
    return parser.parse_args(argv)


def load_stdin_payload() -> dict[str, Any] | None:
    if sys.stdin.isatty():
        return None
    raw = sys.stdin.read().strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON on stdin: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit("JSON stdin must be an object with keys and majors.")
    return data


def parse_majors(value: Any) -> list[int]:
    if value is None:
        raise SystemExit("Provide --majors or JSON stdin with majors.")
    if isinstance(value, list):
        parts = value
    else:
        parts = str(value).split(",")
    majors: list[int] = []
    for part in parts:
        part = str(part).strip()
        if not part:
            continue
        try:
            majors.append(int(part))
        except ValueError as exc:
            raise SystemExit(f"Invalid TYPO3 major version: {part}") from exc
    if not majors:
        raise SystemExit("At least one TYPO3 major version is required.")
    return majors


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    payload = load_stdin_payload()

    keys = list(args.keys)
    majors_value = args.majors
    if payload:
        if not keys:
            keys = [str(k) for k in payload.get("keys") or []]
        if majors_value is None:
            majors_value = payload.get("majors")

    keys = [k.strip() for k in keys if str(k).strip()]
    if not keys:
        raise SystemExit("Provide extension keys as arguments or JSON stdin.")

    majors = parse_majors(majors_value)
    results = {key: lookup_key(key, majors) for key in keys}
    json.dump(results, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
