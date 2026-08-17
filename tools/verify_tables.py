#!/usr/bin/env python3
"""Check the built HTML against data/models.json.

Run after `mkdocs build`. Parses the model tables out of the generated pages and compares
every cell with the captured catalog response, so a published price can never disagree
with the catalog it was generated from.

Exits non-zero, with the differences printed, if anything drifted.
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Imported, never re-implemented: a second copy of the rendering rules would compare the
# generator against itself and agree by construction, which is not verification.
from generate_pricing import VISION_ALIASES, paise, usd  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "models.json"
SITE = ROOT / "site"

CATALOG_HEADER = [
    "Alias",
    "Model",
    "Vision",
    "USD / MTok in",
    "USD / MTok out",
    "Paise / 1K in",
    "Paise / 1K out",
]
BUDGET_HEADER = [
    "Alias",
    "Model",
    "Paise / 1K in",
    "Paise / 1K out",
    "Paise for 1K in + 1K out",
]
VISION_HEADER = ["Alias", "Model", "Paise / 1K in", "Paise / 1K out"]

ENTITIES = {"amp": "&", "lt": "<", "gt": ">", "quot": '"', "nbsp": " "}


class TableParser(HTMLParser):
    """Collects every <table> on a page as a list of rows of cell text."""

    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag):
        if tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None
        elif tag == "tr" and self._row is not None:
            self._table.append(self._row)
            self._row = None
        elif tag in ("td", "th") and self._cell is not None:
            self._row.append("".join(self._cell).strip())
            self._cell = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def handle_entityref(self, name):
        if self._cell is not None:
            self._cell.append(ENTITIES.get(name, ""))


def tables_on(page: Path, header: list[str]) -> list[list[list[str]]]:
    parser = TableParser()
    parser.feed(page.read_text())
    return [table for table in parser.tables if table and table[0] == header]


def main() -> int:
    if not SITE.exists():
        print("site/ not found: run `mkdocs build` first", file=sys.stderr)
        return 2

    catalog = json.loads(SOURCE.read_text(), parse_float=Decimal, parse_int=Decimal)
    models = {model["alias"]: model for model in catalog["models"]}
    problems: list[str] = []
    seen: set[str] = set()

    for table in tables_on(SITE / "pricing" / "models" / "index.html", CATALOG_HEADER):
        for alias, name, vision, usd_in, usd_out, paise_in, paise_out in table[1:]:
            model = models.get(alias)
            if model is None:
                problems.append(f"catalog: {alias} is not in the source JSON")
                continue
            seen.add(alias)
            # The catalog response carries no vision flag, so this column can only be
            # checked against the editorial list it was rendered from. That keeps the two
            # tables agreeing; it says nothing about whether the list itself is right.
            expected_vision = "yes" if alias in VISION_ALIASES else ""
            if vision != expected_vision:
                problems.append(
                    f"catalog: {alias}.vision is {vision!r}, expected {expected_vision!r}"
                )
            for got, want, field in (
                (name, model["displayName"], "displayName"),
                (usd_in, usd(model["usdPerMTokIn"]), "usdPerMTokIn"),
                (usd_out, usd(model["usdPerMTokOut"]), "usdPerMTokOut"),
                (paise_in, paise(model["paisePer1KTokensIn"]), "paisePer1KTokensIn"),
                (paise_out, paise(model["paisePer1KTokensOut"]), "paisePer1KTokensOut"),
            ):
                if got != want:
                    problems.append(f"catalog: {alias}.{field} is {got!r}, expected {want!r}")

    missing = sorted(set(models) - seen)
    if missing:
        problems.append(f"catalog: aliases missing from the page: {missing}")

    for table in tables_on(SITE / "pricing" / "models" / "index.html", BUDGET_HEADER):
        for alias, _name, paise_in, paise_out, total in table[1:]:
            model = models[alias]
            expected = paise(model["paisePer1KTokensIn"] + model["paisePer1KTokensOut"])
            if total != expected:
                problems.append(f"budget: {alias} total is {total}, expected {expected}")
            if paise_in != paise(model["paisePer1KTokensIn"]):
                problems.append(f"budget: {alias} input rate disagrees with the catalog")
            if paise_out != paise(model["paisePer1KTokensOut"]):
                problems.append(f"budget: {alias} output rate disagrees with the catalog")

    vision_rows = 0
    vision_seen: set[str] = set()
    for table in tables_on(SITE / "guides" / "vision" / "index.html", VISION_HEADER):
        for alias, name, paise_in, paise_out in table[1:]:
            vision_rows += 1
            vision_seen.add(alias)
            model = models.get(alias)
            if model is None:
                problems.append(f"vision: {alias} is not in the source JSON")
                continue
            if (
                name != model["displayName"]
                or paise_in != paise(model["paisePer1KTokensIn"])
                or paise_out != paise(model["paisePer1KTokensOut"])
            ):
                problems.append(f"vision: {alias} disagrees with the catalog")

    if vision_seen != set(VISION_ALIASES):
        problems.append(
            "vision: the page lists "
            f"{sorted(vision_seen ^ set(VISION_ALIASES))} differently from VISION_ALIASES"
        )

    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        return 1

    print(
        f"OK: {len(seen)} catalog rows and {vision_rows} vision rows in the built site "
        f"match {SOURCE.relative_to(ROOT)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
