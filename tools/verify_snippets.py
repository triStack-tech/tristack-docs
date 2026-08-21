#!/usr/bin/env python3
"""Check the generated Mintlify snippets against data/models.json, and against the pages.

    python tools/verify_snippets.py            # both checks
    python tools/verify_snippets.py --tables   # only the numbers
    python tools/verify_snippets.py --imports  # only the wiring

This is what replaces `mkdocs build --strict` plus `tools/verify_tables.py` for the
Mintlify site. Mintlify renders on Mintlify's servers, so there is no local build whose
HTML can be parsed back; the generated markdown is the last artefact this repo owns, so it
is the artefact that gets checked.

Two separate things are checked, because they fail for different reasons and deserve
different answers:

  --tables   Every number in snippets/*.mdx matches the captured catalog, and the file is
             MDX the renderer can actually parse. A failure here means a wrong price would
             be published: it must stop the run.

  --imports  The pages import the snippets, and every import resolves. A page importing a
             snippet that is not there, or importing one and never rendering it, is broken
             and fails. A snippet that no page imports is only reported: whether the tables
             belong on a page is an editorial decision, not a defect this script can settle.

The rendering rules are imported from tools/generate_pricing.py, never re-implemented. A
second copy of them would compare the generator against itself and agree by construction,
which is not verification.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from generate_pricing import (  # noqa: E402
    FAMILIES,
    PENDING_ALIASES,
    SNIPPETS,
    VISION_ALIASES,
    Mintlify,
    paise,
    servable,
    usd,
)

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "models.json"

CATALOG = SNIPPETS / "model-catalog.mdx"
SUMMARY = SNIPPETS / "catalog-summary.mdx"
VISION = SNIPPETS / "model-vision.mdx"
BUDGET = SNIPPETS / "model-budget.mdx"
GENERATED = (CATALOG, SUMMARY, VISION, BUDGET)

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

# Directories that hold no published page: the MkDocs site that is still being served, its
# build output, the generated snippets themselves, and the usual local clutter.
NOT_PAGES = {".git", ".github", ".venv", "docs", "site", "snippets", "node_modules"}

# `import Thing from '/snippets/thing.mdx'`, and the named form Mintlify uses for snippets
# that export variables rather than content.
IMPORT = re.compile(
    r"""^import\s+(?P<what>[^'"]+?)\s+from\s+['"](?P<path>/snippets/[^'"]+)['"]""",
    re.MULTILINE,
)
WARNINGS = re.compile(r"<Warning>(.*?)</Warning>", re.DOTALL)
ALIAS_IN_TEXT = re.compile(r"`([a-z0-9.-]+)`")


def pages() -> list[Path]:
    """Every .mdx file that is a page: the whole repo minus the directories above."""
    return sorted(
        path
        for path in ROOT.rglob("*.mdx")
        if not NOT_PAGES & set(path.relative_to(ROOT).parts)
    )


def tables(text: str) -> list[list[list[str]]]:
    """Every markdown table in a file, as rows of cell text, alignment row dropped."""
    found: list[list[list[str]]] = []
    current: list[list[str]] | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|"):
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if all(set(cell) <= set("-: ") and cell for cell in cells):
                continue  # the |---|---| alignment row
            current = current if current is not None else []
            current.append(cells)
        elif current is not None:
            found.append(current)
            current = None
    if current is not None:
        found.append(current)
    return found


def cell(value: str) -> str:
    return value.strip().strip("`")


def check_mdx(problems: list[str]) -> dict[Path, str]:
    """
    MDX is stricter than the markdown MkDocs took, and it fails at publish time rather than
    here. An HTML comment, a `!!!` admonition or a stray brace left over from the MkDocs
    rendering would take a page down, so they are caught while they are still local.
    """
    text: dict[Path, str] = {}
    for path in GENERATED:
        if not path.exists():
            problems.append(f"{path.relative_to(ROOT)} is missing: run tools/generate_pricing.py")
            continue
        body = path.read_text()
        text[path] = body
        where = path.relative_to(ROOT)
        lines = body.splitlines()
        if not lines or lines[0] != Mintlify.banner:
            problems.append(f"{where}: the first line is not the do-not-edit banner")
        if "<!--" in body:
            problems.append(f"{where}: an HTML comment is a parse error in MDX")
        if "!!!" in body:
            problems.append(f"{where}: a MkDocs admonition survived; MDX needs <Warning>")
        if "--8<--" in body:
            problems.append(f"{where}: a MkDocs snippet include survived")
        for number, line in enumerate(lines[1:], start=2):
            if "{" in line or "}" in line:
                problems.append(f"{where}:{number}: a bare brace opens an MDX expression")
    return text


def warned_about(body: str) -> set[str]:
    """The aliases named inside the <Warning> blocks of a snippet."""
    return {
        alias
        for block in WARNINGS.findall(body)
        for alias in ALIAS_IN_TEXT.findall(block)
    }


def check_catalog(body: str, models: dict[str, dict], problems: list[str]) -> None:
    seen: set[str] = set()
    for table in tables(body):
        if table[0] != CATALOG_HEADER:
            problems.append(f"model-catalog.mdx: unexpected table header {table[0]}")
            continue
        for row in table[1:]:
            alias = cell(row[0])
            model = models.get(alias)
            if model is None:
                problems.append(f"catalog: {alias} is not in the source JSON")
                continue
            seen.add(alias)
            # The catalog response carries no vision flag, so this column can only be
            # checked against the editorial list it was rendered from. That keeps the two
            # tables agreeing; it says nothing about whether the list itself is right.
            expected = [
                ("displayName", model["displayName"]),
                ("vision", "yes" if alias in VISION_ALIASES else ""),
                ("usdPerMTokIn", usd(model["usdPerMTokIn"])),
                ("usdPerMTokOut", usd(model["usdPerMTokOut"])),
                ("paisePer1KTokensIn", paise(model["paisePer1KTokensIn"])),
                ("paisePer1KTokensOut", paise(model["paisePer1KTokensOut"])),
            ]
            for (field, want), got in zip(expected, [cell(value) for value in row[1:]]):
                if got != want:
                    problems.append(f"catalog: {alias}.{field} is {got!r}, expected {want!r}")

    missing = sorted(set(models) - seen)
    if missing:
        problems.append(f"catalog: aliases missing from the snippet: {missing}")

    unwarned = sorted((seen & PENDING_ALIASES) - warned_about(body))
    if unwarned:
        problems.append(
            f"catalog: {unwarned} are priced with no 'not servable yet' warning above them"
        )


def check_budget(body: str, models: dict[str, dict], problems: list[str]) -> None:
    for table in tables(body):
        if table[0] != BUDGET_HEADER:
            problems.append(f"model-budget.mdx: unexpected table header {table[0]}")
            continue
        for row in table[1:]:
            alias, _name, rate_in, rate_out, total = [cell(value) for value in row]
            model = models.get(alias)
            if model is None:
                problems.append(f"budget: {alias} is not in the source JSON")
                continue
            if alias in PENDING_ALIASES:
                problems.append(f"budget: {alias} cannot be served, so it is not a cheap option")
            if rate_in != paise(model["paisePer1KTokensIn"]):
                problems.append(f"budget: {alias} input rate disagrees with the catalog")
            if rate_out != paise(model["paisePer1KTokensOut"]):
                problems.append(f"budget: {alias} output rate disagrees with the catalog")
            expected = paise(model["paisePer1KTokensIn"] + model["paisePer1KTokensOut"])
            if total != expected:
                problems.append(f"budget: {alias} total is {total}, expected {expected}")


def check_vision(body: str, models: dict[str, dict], problems: list[str]) -> int:
    rows = 0
    seen: set[str] = set()
    for table in tables(body):
        if table[0] != VISION_HEADER:
            problems.append(f"model-vision.mdx: unexpected table header {table[0]}")
            continue
        for row in table[1:]:
            alias, name, rate_in, rate_out = [cell(value) for value in row]
            rows += 1
            seen.add(alias)
            model = models.get(alias)
            if model is None:
                problems.append(f"vision: {alias} is not in the source JSON")
                continue
            if (
                name != model["displayName"]
                or rate_in != paise(model["paisePer1KTokensIn"])
                or rate_out != paise(model["paisePer1KTokensOut"])
            ):
                problems.append(f"vision: {alias} disagrees with the catalog")

    if seen != set(VISION_ALIASES):
        problems.append(
            "vision: the snippet lists "
            f"{sorted(seen ^ set(VISION_ALIASES))} differently from VISION_ALIASES"
        )
    return rows


def check_summary(body: str, fx: Decimal, models: dict[str, dict], problems: list[str]) -> None:
    """The one place the tables are described in prose. A count left behind by a refresh
    reads as authoritative, so it is checked like a rate."""
    counted = {
        "models": (r"\*\*(\d+) models\*\*", str(len(models))),
        "families": (r"\*\*(\d+) families\*\*", str(len(FAMILIES))),
        "servable": (r"of which \*\*(\d+)\*\*", str(len(servable(list(models.values()))))),
        "conversion rate": (r"\*\*([\d.]+) INR per USD\*\*", f"{fx:.1f}"),
    }
    for what, (pattern, want) in counted.items():
        found = re.search(pattern, body)
        if found is None:
            problems.append(f"summary: no {what} figure found in catalog-summary.mdx")
        elif found.group(1) != want:
            problems.append(f"summary: {what} says {found.group(1)}, expected {want}")


def check_tables(problems: list[str]) -> None:
    if not SOURCE.exists():
        problems.append(f"{SOURCE.relative_to(ROOT)} is missing: run tools/fetch_catalog.py")
        return

    catalog = json.loads(SOURCE.read_text(), parse_float=Decimal, parse_int=Decimal)
    models = {model["alias"]: model for model in catalog["models"]}

    text = check_mdx(problems)
    if len(text) != len(GENERATED):
        return

    check_catalog(text[CATALOG], models, problems)
    check_budget(text[BUDGET], models, problems)
    rows = check_vision(text[VISION], models, problems)
    check_summary(text[SUMMARY], catalog["usdToInr"], models, problems)
    if not problems:
        print(
            f"OK: {len(models)} catalog rows and {rows} vision rows in "
            f"{SNIPPETS.relative_to(ROOT)}/ match {SOURCE.relative_to(ROOT)}"
        )


def check_imports(problems: list[str], notes: list[str]) -> None:
    imported: set[Path] = set()
    for page in pages():
        body = page.read_text()
        where = page.relative_to(ROOT)
        for match in IMPORT.finditer(body):
            target = ROOT / match.group("path").lstrip("/")
            what = match.group("what").strip()
            if not target.exists():
                problems.append(f"{where} imports {match.group('path')}, which does not exist")
                continue
            imported.add(target)
            # A default import is the snippet's content and only appears once rendered.
            # A named import is a variable, used inline as {Name}, and is left alone.
            if not what.startswith("{") and not re.search(rf"<{re.escape(what)}\b", body):
                problems.append(
                    f"{where} imports {what} from {match.group('path')} but never "
                    f"renders <{what} />, so the table does not appear on the page"
                )

    unused = sorted(path.name for path in GENERATED if path not in imported)
    if unused:
        notes.append(
            "No page imports "
            + ", ".join(unused)
            + ". The tables are generated and committed but published nowhere. Import one "
            "into the page that should show it, for example:\n\n"
            "    import ModelCatalog from '/snippets/model-catalog.mdx';\n\n"
            "    <ModelCatalog />\n\n"
            "If the prices are meant to be read live from GET /v1/manifold/models instead, "
            "delete the generator and this check with it."
        )
    if not problems:
        print(f"OK: {len(imported)} snippet imports across {len(pages())} pages resolve")


def report(heading: str, lines: list[str]) -> None:
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary:
        return
    with open(summary, "a", encoding="utf-8") as handle:
        handle.write(f"### {heading}\n\n")
        for line in lines:
            handle.write(f"{line}\n\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tables", action="store_true", help="check the numbers")
    parser.add_argument("--imports", action="store_true", help="check the wiring")
    args = parser.parse_args()
    both = not (args.tables or args.imports)

    problems: list[str] = []
    notes: list[str] = []
    if both or args.tables:
        check_tables(problems)
    if both or args.imports:
        check_imports(problems, notes)

    for note in notes:
        print(f"note: {note}")
    if notes:
        report("The generated tables are not on any page", notes)

    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        report("The generated tables do not check out", problems)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
