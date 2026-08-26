#!/usr/bin/env python3
"""Fetch the model catalog and save the response for tools/generate_pricing.py.

    TRISTACK_API_KEY=... python tools/fetch_catalog.py --out data/models.json

The body is validated as the endpoint returned it, then reduced to the fields the
pages publish. Rates are carried across as written, so one that arrives as `45.00` is
stored as `45.00` rather than round-tripped into `45.0`.

The payload is validated before anything is written. An error page, a truncated body
or a catalog with no models must never overwrite a good capture, because the published
prices are generated from whatever this file holds.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_URL = "https://api.tristack.tech/v1/manifold/models"
DEFAULT_OUT = ROOT / "data" / "models.json"

# The fields tools/generate_pricing.py reads. A response missing any of them is a
# response the generator cannot turn into a table, so it is rejected here instead.
REQUIRED_RATES = (
    "paisePer1KTokensIn",
    "paisePer1KTokensOut",
)


def fetch(url: str, key: str, timeout: float) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "User-Agent": "tristack-docs catalog refresh",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        detail = error.read()[:400].decode("utf-8", "replace").strip()
        raise SystemExit(
            f"{url} answered {error.code} {error.reason}"
            + (f": {detail}" if detail else "")
        ) from None
    except urllib.error.URLError as error:
        raise SystemExit(f"{url} could not be reached: {error.reason}") from None


def validate(raw: bytes) -> int:
    """Reject anything the generator could not safely publish. Returns the model count."""
    if not raw.strip():
        raise SystemExit("The catalog response was empty")

    try:
        payload = json.loads(raw, parse_float=Decimal, parse_int=Decimal)
    except json.JSONDecodeError as error:
        head = raw[:200].decode("utf-8", "replace").strip()
        raise SystemExit(f"The catalog response is not JSON ({error}): {head}") from None

    if not isinstance(payload, dict):
        raise SystemExit("The catalog response is not a JSON object")

    models = payload.get("models")
    if not isinstance(models, list) or not models:
        raise SystemExit("The catalog response carries no models")

    seen: set[str] = set()
    for index, model in enumerate(models):
        where = f"models[{index}]"
        if not isinstance(model, dict):
            raise SystemExit(f"{where} is not an object")

        alias = model.get("alias")
        if not isinstance(alias, str) or not alias:
            raise SystemExit(f"{where}.alias is missing or empty")
        if alias in seen:
            raise SystemExit(f"{alias} appears twice in the catalog")
        seen.add(alias)

        name = model.get("displayName")
        if not isinstance(name, str) or not name:
            raise SystemExit(f"{alias}.displayName is missing or empty")

        for field in REQUIRED_RATES:
            rate = model.get(field)
            if not isinstance(rate, Decimal) or rate < 0:
                raise SystemExit(f"{alias}.{field} is missing or not a rate: {rate!r}")

    return len(models)


# The response is captured into a public repository, so only the fields the pages
# actually publish are kept. Anything the endpoint may grow later stays out by default
# rather than being reviewed for disclosure after it has already been committed.
PUBLISHED_FIELDS = ("alias", "displayName", "paisePer1KTokensIn", "paisePer1KTokensOut")
TEXT_FIELDS = frozenset({"alias", "displayName"})


def publishable(raw: bytes) -> bytes:
    """The captured response reduced to the published fields, rates unchanged.

    Rates are re-emitted as the endpoint wrote them rather than round-tripped through a
    float, so a rate that arrived as `45.00` is stored as `45.00`. That is why the rows
    are assembled here instead of handed to json.dumps, which has no way to write a
    Decimal as a JSON number.
    """
    payload = json.loads(raw, parse_float=str, parse_int=str)
    rows = [
        "{"
        + ", ".join(
            f"{json.dumps(field)}: "
            + (json.dumps(model[field]) if field in TEXT_FIELDS else model[field])
            for field in PUBLISHED_FIELDS
        )
        + "}"
        for model in payload["models"]
    ]
    return ('{"models": [' + ", ".join(rows) + "]}").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default=DEFAULT_URL, help=f"default {DEFAULT_URL}")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    key = os.environ.get("TRISTACK_API_KEY", "").strip()
    if not key:
        raise SystemExit(
            "TRISTACK_API_KEY is not set. Locally, export a key from the dashboard; "
            "in CI it comes from the TRISTACK_CATALOG_API_KEY repository secret."
        )

    raw = fetch(args.url, key, args.timeout)
    count = validate(raw)
    raw = publishable(raw)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(raw)
    print(f"{count} models captured into {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
