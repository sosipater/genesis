"""Simple LAN sync probe for desktop host diagnostics."""

from __future__ import annotations

import argparse
import json
from urllib.error import URLError
from urllib.request import urlopen


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="http://127.0.0.1:8765", help="Desktop sync host base URL")
    args = parser.parse_args()

    url = f"{args.host}/health"
    try:
        with urlopen(url, timeout=3) as response:
            body = response.read().decode("utf-8")
            print(f"Probe success: {response.status}")
            try:
                print(json.dumps(json.loads(body), indent=2))
            except json.JSONDecodeError:
                print(body)
            return 0
    except URLError as error:
        print(f"Probe failed for {url}: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

