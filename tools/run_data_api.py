"""Run the checks from DATA-API.yaml against a live API, like the automated review does.

Usage:
    python tools/run_data_api.py --base-url https://marshrut-tf5o.onrender.com --token <test token>

Supports the subset of DATA-API 1.0 used in this repository: roles public/user,
path/query/body/headers, dependsOn ordering, expected status/content type/required fields,
and extract with simple JSONPath ($.a.b, $.a[0].b).
"""

import argparse
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import yaml


def _ssl_context() -> ssl.SSLContext:
    """System roots plus certifi: python.org builds on macOS ship without system roots."""
    context = ssl.create_default_context()
    try:
        import certifi

        context.load_verify_locations(certifi.where())
    except ImportError:
        pass
    return context


SSL_CONTEXT = _ssl_context()

ROOT = Path(__file__).resolve().parents[1]


def jsonpath(data: Any, expression: str) -> Any:
    for key, index in re.findall(r"\.([^.\[]+)|\[(\d+)\]", expression.removeprefix("$")):
        data = data[int(index)] if index else data[key]
    return data


def substitute(value: Any, variables: dict[str, Any]) -> Any:
    if isinstance(value, str):
        return re.sub(r"\$\{(\w+)\}", lambda m: str(variables[m.group(1)]), value)
    if isinstance(value, dict):
        return {k: substitute(v, variables) for k, v in value.items()}
    if isinstance(value, list):
        return [substitute(v, variables) for v in value]
    return value


def run_check(check: dict[str, Any], base_url: str, token: str, defaults: dict[str, str],
              variables: dict[str, Any]) -> tuple[bool, str]:
    request = substitute(check.get("request", {}), variables)
    path = check["path"]
    for name, value in request.get("path", {}).items():
        path = path.replace("{" + name + "}", urllib.parse.quote(str(value)))
    url = base_url.rstrip("/") + path
    if request.get("query"):
        url += "?" + urllib.parse.urlencode(request["query"], doseq=True)

    headers = {**defaults, **request.get("headers", {})}
    if check["role"] != "public":
        headers["Authorization"] = f"Bearer {token}"
    body = request.get("body")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=check["method"], headers=headers)

    started = time.monotonic()
    try:
        with urllib.request.urlopen(
            req, timeout=check.get("timeoutMs", 5000) / 1000, context=SSL_CONTEXT
        ) as resp:
            status, content_type, raw = resp.status, resp.headers.get("Content-Type", ""), resp.read()
    except urllib.error.HTTPError as error:
        status, content_type, raw = error.code, error.headers.get("Content-Type", ""), error.read()
    except Exception as error:  # noqa: BLE001
        return False, f"request failed: {error}"
    elapsed = int((time.monotonic() - started) * 1000)

    expected = check["expected"]
    problems = []
    if status not in expected["statusCodes"]:
        problems.append(f"status {status} not in {expected['statusCodes']}")
    if "contentType" in expected and expected["contentType"] not in content_type:
        problems.append(f"content type {content_type!r}")
    payload: Any = None
    try:
        payload = json.loads(raw) if raw else None
    except ValueError:
        problems.append("body is not JSON")
    for field in expected.get("requiredFields", []):
        if not isinstance(payload, dict) or field not in payload:
            problems.append(f"missing field {field!r}")
    if not problems:
        for name, expression in check.get("extract", {}).items():
            try:
                variables[name] = jsonpath(payload, expression)
            except (KeyError, IndexError, TypeError):
                problems.append(f"cannot extract {name} from {expression}")
    return not problems, f"{status} in {elapsed} ms" + (": " + "; ".join(problems) if problems else "")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "DATA-API.yaml")
    parser.add_argument("--base-url")
    parser.add_argument("--token", required=True, help="Test access token for role 'user'")
    args = parser.parse_args()

    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    base_url = args.base_url or config["api"]["baseUrl"]
    defaults = config["api"].get("defaultHeaders", {})
    variables: dict[str, Any] = {}
    passed: set[str] = set()
    failed = 0
    for check in config["checks"]:
        missing = [dep for dep in check.get("dependsOn", []) if dep not in passed]
        if missing:
            print(f"SKIP  {check['id']}: depends on failed {', '.join(missing)}")
            failed += 1
            continue
        ok, detail = run_check(check, base_url, args.token, defaults, variables)
        print(f"{'OK  ' if ok else 'FAIL'}  {check['id']}: {detail}")
        if ok:
            passed.add(check["id"])
        else:
            failed += 1
    print(f"\n{len(passed)} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
