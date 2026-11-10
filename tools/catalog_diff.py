#!/usr/bin/env python3
"""Say what moved between two captured catalog responses.

    python tools/catalog_diff.py before.json data/models.json

Prints a markdown summary: models added, removed, renamed or reprised. The refresh
workflow writes that summary into the pull request it opens, so a reviewer reads what
changed instead of diffing a single line of minified JSON by eye.

Rates are rendered with the same functions that render the published tables, never a
second copy of them: the numbers quoted in the pull request are the numbers the pages
will carry once it merges.

Inside a workflow, `changed`, `title` and `body` are written to $GITHUB_OUTPUT and the
summary is appended to $GITHUB_STEP_SUMMARY.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from generate_pricing import paise, unit_paise  # noqa: E402

# Every rate on the pricing pages, with the column head and renderer each one uses.
#
# The per-unit rates are here as well as the token ones. An image model is priced on
# paisePerImage alone, so with only the token rates listed a new image model was summarised
# as 0.00 in and 0.00 out, and a change to its price moved the published table while this
# summary said nothing had moved, which the refresh workflow treats as a failure. The same
# held for an embedding model's per-image, per-second and per-request rates.
RATES = (
    ("paisePer1KTokensIn", "Paise / 1K in", paise),
    ("paisePer1KTokensOut", "Paise / 1K out", paise),
    ("paisePerImage", "Paise / image", unit_paise),
    ("paisePerVideoSecond", "Paise / video sec", unit_paise),
    ("paisePerAudioSecond", "Paise / audio sec", unit_paise),
    ("paisePerRequest", "Paise / request", unit_paise),
)
ZERO = Decimal(0)


def rate(model: dict, field: str) -> Decimal:
    # A capture taken before the per-unit rates were carried across has no such fields.
    return model.get(field, ZERO)


def load(path: Path) -> dict[str, dict]:
    payload = json.loads(path.read_text(), parse_float=Decimal, parse_int=Decimal)
    return {model["alias"]: model for model in payload["models"]}


def rate_table(models: list[dict]) -> list[str]:
    """The models with their rates, carrying only the columns some listed model prices, so
    an added image model is not shown beside two token columns of zeros."""
    used = [
        (field, head, render)
        for field, head, render in RATES
        if any(rate(model, field) != 0 for model in models)
    ]
    heads = " | ".join(head for _, head, _ in used)
    return [
        f"| Alias | Model | {heads} |",
        "|---|---|" + "|".join("---:" for _ in used) + "|",
        *(
            f"| `{model['alias']}` | {model['displayName']} | "
            + " | ".join(render(rate(model, field)) for field, _, render in used)
            + " |"
            for model in models
        ),
    ]


def moved_rates(before: dict, after: dict) -> list[tuple[str, str, str]]:
    """The rates that differ, as (column head, before, after). Compared as numbers, so
    a catalog that starts writing 45.0 where it wrote 45.00 is not reported as a rise."""
    return [
        (head, render(rate(before, field)), render(rate(after, field)))
        for field, head, render in RATES
        if rate(before, field) != rate(after, field)
    ]


def phrase(parts: list[str]) -> str:
    if len(parts) == 1:
        return parts[0]
    return f"{', '.join(parts[:-1])} and {parts[-1]}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    args = parser.parse_args()

    old = load(args.before)
    new = load(args.after)

    added = [model for alias, model in new.items() if alias not in old]
    removed = [model for alias, model in old.items() if alias not in new]
    renamed = [
        (old[alias], model)
        for alias, model in new.items()
        if alias in old and old[alias]["displayName"] != model["displayName"]
    ]
    reprised = [
        (model, moved_rates(old[alias], model))
        for alias, model in new.items()
        if alias in old and moved_rates(old[alias], model)
    ]

    counts = []
    if added:
        counts.append(f"{len(added)} added")
    if removed:
        counts.append(f"{len(removed)} removed")
    if reprised:
        counts.append(f"{len(reprised)} reprised")
    if renamed:
        counts.append(f"{len(renamed)} renamed")

    body: list[str] = []
    if counts:
        headline = f"{phrase(counts)}."
    else:
        headline = "No model was added, removed, renamed or reprised."

    title = "Refresh the model catalog: " + (phrase(counts) if counts else "no change")

    body.append(headline)
    body.append("")
    body.append(
        f"The catalog now holds {len(new)} models, up from {len(old)}."
        if len(new) > len(old)
        else f"The catalog now holds {len(new)} models, down from {len(old)}."
        if len(new) < len(old)
        else f"The catalog holds {len(new)} models, as before."
    )
    body.append("")

    if added:
        body += ["### Added", "", *rate_table(added), ""]
    if removed:
        body += ["### Removed", "", *rate_table(removed), ""]
    if reprised:
        body += [
            "### Reprised",
            "",
            "| Alias | Model | Rate | Before | After |",
            "|---|---|---|---:|---:|",
            *(
                f"| `{model['alias']}` | {model['displayName']} | {head} | {was} | {now} |"
                for model, moves in reprised
                for head, was, now in moves
            ),
            "",
        ]
    if renamed:
        body += [
            "### Renamed",
            "",
            "| Alias | Before | After |",
            "|---|---|---|",
            *(
                f"| `{after['alias']}` | {before['displayName']} | {after['displayName']} |"
                for before, after in renamed
            ),
            "",
        ]

    changed = bool(counts)
    body.append(
        "`data/models.json` is the captured response and `snippets/` is generated from "
        "it by `tools/generate_pricing.py`. Neither was edited by hand."
        if changed
        else "The published tables already match the catalog."
    )

    rendered = "\n".join(body)
    print(rendered)

    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        # A delimiter no catalog response can collide with, per the multiline output rules.
        mark = f"body-{uuid.uuid4()}"
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"changed={'true' if changed else 'false'}\n")
            handle.write(f"title={title if changed else ''}\n")
            handle.write(f"body<<{mark}\n{rendered}\n{mark}\n")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(f"{rendered}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
