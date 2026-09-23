"""Write the OpenAPI document of the running code to ``openapi.yaml`` in the repo root.

Usage: python scripts/export_openapi.py [--server https://example.org]
"""

import argparse
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", help="Public HTTPS base URL to put into servers[]")
    parser.add_argument("--output", type=Path, default=ROOT / "openapi.yaml")
    args = parser.parse_args()

    schema = app.openapi()
    if args.server:
        schema["servers"] = [{"url": args.server.rstrip("/")}]
    args.output.write_text(
        yaml.safe_dump(schema, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    print(f"OpenAPI {schema['openapi']} written to {args.output}")


if __name__ == "__main__":
    main()
