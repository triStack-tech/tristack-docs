---
title: Model catalog
description: Every Tristack alias with its price in USD per million tokens and in paise per 1000 tokens.
---

# Model catalog

--8<-- "catalog-summary.md"

You address a model by its **alias**, the short lowercase string in the first column:

```json
{ "model": "nova-micro", "max_tokens": 1024, "messages": [ ... ] }
```

!!! tip "The endpoint is authoritative"

    This page is a snapshot, correct on 2026-08-17. Models are added and retired, prices
    move, and the FX rate is configuration.
    [`GET /v1/manifold/models`](../api/models.md) is the truth for the deployment you are
    calling. Read it at start-up, cache it, and never hardcode a price.

## Reading the table

| Column | Meaning |
|---|---|
| Alias | The value you put in `model`. |
| Model | The model's name. |
| Vision | Whether the alias accepts [image blocks](../guides/vision.md). |
| USD / MTok in, out | The stored rate, per million tokens. |
| Paise / 1K in, out | The same rate in paise per 1000 tokens, converted at the FX rate above. |

The paise columns are derived from the USD ones, not stored separately:

```text
paisePer1KTokens = round(usdPerMTok / 1000 * usdToInr * 100, 2)
```

The rounding to 2 decimal places is part of the conversion, and a half rounds to the even
digit: `nova-micro` at 0.035 USD per million input tokens converts to exactly 0.315 paise
per 1000 and publishes as **0.32**. These columns are for reading. The money a call costs
is computed from the USD rates, not from these, and rounds up to a whole paise once at the
end: see [the price of a call](billing.md#the-price-of-a-call).

Several models price input and output the same (`llama-3-1-8b`, `llama-3-1-70b`,
`llama-3-3-70b`, the three `ministral-*` sizes, `voxtral-mini`). That is the published
rate, not a typo.

## Choosing a model

There is no ranking here, because there is no measurement here. The honest advice is
short:

**Start at the cheap end and only move up when your own task shows you need to.** The
dearest row in this catalog costs more than a hundred times the cheapest per token, so the
model you pick matters far more to your bill than any optimisation you make afterwards.

**Test on your own prompts.** Published leaderboards measure someone else's task. A
30-minute evaluation on 20 of your real inputs will tell you more than any table.

**Use two tiers.** Route the easy majority of requests to a small model and escalate the
hard ones. The escalation rule can be as crude as a length threshold or a confidence
phrase in the reply, and it usually saves more than picking a marginally cheaper model
for everything.

**Match the shape of the work.** Output tokens usually cost several times what input
tokens cost, so a summarisation workload (long input, short output) and a generation
workload (short input, long output) land in different places on the same table. Price your
actual ratio, not the headline number.

**For images**, you are choosing from the vision-capable rows only, listed on the
[vision page](../guides/vision.md#models-that-accept-images).

### The cheapest servable models

Ten lowest, ranked by what 1000 input tokens plus 1000 output tokens would cost:

--8<-- "model-budget.md"

At those rates a request that reads 1000 tokens and writes 1000 tokens costs between
1 and 4 paise. Rounding up to a whole paise happens once, at the end of each call, so very
small calls are dominated by that rounding.

## Availability

An alias in the catalog is not always servable. A deployment can publish a model whose
account entitlement has not cleared, and a call to it answers `403 model_access_denied`.
The affected rows are flagged in the tables below.

## The catalog

--8<-- "model-catalog.md"

## Keeping this in sync

The tables on this page are generated from a captured `GET /v1/manifold/models` response
that ships with the documentation source, so they cannot drift from the catalog they were
captured from.

That capture is refreshed on a schedule rather than by hand, and every change to it lands
as a reviewed commit, so a price shown here is one that was checked against the catalog
before it was published. If a rate on this page disagrees with what a response charges you,
the response is right and the page is stale: please [tell us](../support.md).
