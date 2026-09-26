#!/usr/bin/env python3
"""Check that the official regional sources still open.

    python3 tools/check_sources.py                 # links from data/regional_services.json
    python3 tools/check_sources.py --candidates    # unverified links from data/regional_candidates.json
    python3 tools/check_sources.py --candidates --promote
        # move candidates that answered 2xx/3xx into regional_services.json (checked_at = today)

Run it from a network in Russia: many regional sites do not answer foreign addresses.
Only the standard library is required. Trusted roots: the system store, certifi (if
installed) and the Russian Trusted CA bundle from backend/certs, used by many state sites.
With --no-verify a site with a broken certificate still counts as answering (marked OK*).
"""

import argparse
import json
import ssl
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "data" / "regional_services.json"
CANDIDATES = ROOT / "data" / "regional_candidates.json"
CA_BUNDLE = ROOT / "backend" / "certs" / "russian_trusted_ca.pem"
KINDS = ("mfc", "tfoms", "student_transport")


def ssl_context(verify: bool = True) -> ssl.SSLContext:
    if not verify:
        return ssl._create_unverified_context()  # reachability check only
    context = ssl.create_default_context()
    try:  # python.org builds on macOS ship without system roots
        import certifi

        context.load_verify_locations(certifi.where())
    except ImportError:
        pass
    if CA_BUNDLE.is_file():
        context.load_verify_locations(CA_BUNDLE)
    return context


def check(
    url: str, context: ssl.SSLContext, timeout: float, fallback: ssl.SSLContext | None
) -> tuple[bool, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 marshrut-check"})
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            return 200 <= response.status < 400, str(response.status)
    except urllib.error.URLError as error:
        if fallback is None or not isinstance(error.reason, ssl.SSLCertVerificationError):
            return _failure(error)
        ok, status = check(url, fallback, timeout, None)
        return ok, f"{status} (bad cert)" if ok else status
    except (TimeoutError, ssl.SSLError, OSError) as error:
        return _failure(error)


def _failure(error: Exception) -> tuple[bool, str]:
    if isinstance(error, urllib.error.HTTPError):
        return False, f"HTTP {error.code}"
    reason = getattr(error, "reason", error)
    return False, type(reason).__name__ + ": " + str(reason)[:80]


def entries(path: Path) -> list[tuple[str, str, dict[str, object]]]:
    regions = json.loads(path.read_text(encoding="utf-8"))["regions"]
    return [
        (code, kind, services[kind])
        for code, services in regions.items()
        for kind in KINDS
        if kind in services
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--candidates", action="store_true", help="check unverified candidates")
    parser.add_argument("--promote", action="store_true", help="move working candidates to pack")
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="count sites with an untrusted certificate as answering (marked OK*)",
    )
    args = parser.parse_args()
    if args.promote and not args.candidates:
        parser.error("--promote works together with --candidates")

    path = CANDIDATES if args.candidates else PACK
    items = entries(path)
    context = ssl_context()
    fallback = ssl_context(verify=False) if args.no_verify else None
    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(
            pool.map(
                lambda item: check(str(item[2]["url"]), context, args.timeout, fallback), items
            )
        )

    failed = 0
    working: list[tuple[str, str]] = []
    for (code, kind, entry), (ok, status) in zip(items, results, strict=True):
        mark = ("OK* " if "bad cert" in status else "OK  ") if ok else "FAIL"
        failed += not ok
        print(f"{mark} {code} {kind:<17} {status:<24} {entry['organization']} — {entry['url']}")
        if ok:
            working.append((code, kind))
    print(f"\n{len(items) - failed} of {len(items)} links answered ({path.name}).")

    if args.promote and working:
        pack = json.loads(PACK.read_text(encoding="utf-8"))
        candidates = json.loads(CANDIDATES.read_text(encoding="utf-8"))
        today = datetime.now(UTC).date().isoformat()
        for code, kind in working:
            entry = candidates["regions"][code].pop(kind)
            entry.pop("note", None)
            entry["checked_at"] = today
            pack["regions"].setdefault(code, {})[kind] = entry
            if not candidates["regions"][code]:
                del candidates["regions"][code]
        for path_, data in ((PACK, pack), (CANDIDATES, candidates)):
            path_.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Promoted {len(working)} link(s). Review the diff before committing:")
        print("  the organization must be the official one, not only a site that opens.")
    return 1 if failed and not args.candidates else 0


if __name__ == "__main__":
    sys.exit(main())
