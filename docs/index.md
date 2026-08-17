---
title: Home
description: Developer documentation for Tristack products.
hide:
  - navigation
---

# Tristack Docs

Developer documentation for Tristack products. Manifold is documented here today, and the other products join it on this site as they ship.

## Tristack Manifold

One HTTP API for language models: send messages, name the model by alias, and read the answer back in a single JSON shape. Every call is metered in tokens and billed to a prepaid wallet in paise, and every response carries the exact cost of that call.

<div class="grid" markdown>

:material-server-outline: **Base URL** `https://api.tristack.tech`
{ .card }

:material-key-outline: **Auth** `Authorization: Bearer tsk_live_...`
{ .card }

:material-cube-outline: **Catalog** one alias per model, priced per token
{ .card }

:material-wallet-outline: **Billing** prepaid, per token, in paise
{ .card }

</div>

## Your first request

Set your key in the environment, then send a message. This runs as-is once your project
has Manifold enabled and the wallet has money in it.

```bash
export TRISTACK_API_KEY="tsk_live_your_key_here"

curl https://api.tristack.tech/v1/manifold/messages \
  -H "Authorization: Bearer $TRISTACK_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "nova-micro",
    "max_tokens": 1024,
    "messages": [
      { "role": "user", "content": "Say hello from Tristack." }
    ]
  }'
```

The answer:

```json
{
  "id": "mfr_9f7922159e6dab6a72166e1f",
  "model": "nova-micro",
  "role": "assistant",
  "content": [{ "type": "text", "text": "Hello from Tristack!" }],
  "stop_reason": "end_turn",
  "usage": { "input_tokens": 10, "output_tokens": 6 },
  "cost": { "paise": 1 }
}
```

That call cost 1 paise. The [pricing page](pricing/billing.md) shows where the number
comes from.

## Start here

<div class="grid cards" markdown>

-   :material-rocket-launch-outline: **Getting started**

    ---

    Account, project, key, wallet, first response. Six steps, with the error you hit
    if you skip one.

    [:octicons-arrow-right-24: Walkthrough](getting-started.md)

-   :material-key-chain: **Authentication**

    ---

    Both header forms, key prefixes, rotation, revocation, and where a key must never go.

    [:octicons-arrow-right-24: Keys and headers](guides/authentication.md)

-   :material-api: **API reference**

    ---

    Every parameter, every field, every error code, with curl, Python and Node examples.

    [:octicons-arrow-right-24: Reference](api/index.md)

-   :material-lightning-bolt-outline: **Streaming**

    ---

    The server-sent events contract, event by event, plus abort and billing semantics.

    [:octicons-arrow-right-24: Stream responses](guides/streaming.md)

-   :material-image-outline: **Vision and images**

    ---

    Image blocks, supported media types, base64 rules, and what images do to the cost
    estimate.

    [:octicons-arrow-right-24: Send an image](guides/vision.md)

-   :material-cube-outline: **Model catalog**

    ---

    Every alias with its price in USD per million tokens and paise per 1000 tokens.

    [:octicons-arrow-right-24: Browse models](pricing/models.md)

-   :material-wallet-outline: **Pricing and billing**

    ---

    How the hold-then-settle wallet works, worked from a real response, down to the paise.

    [:octicons-arrow-right-24: Understand the bill](pricing/billing.md)

-   :material-alert-circle-outline: **Errors**

    ---

    Every code, its HTTP status, what caused it, what to do next, and what it costs.

    [:octicons-arrow-right-24: Error reference](api/errors.md)

</div>

## What a request needs

1. An **account** on [tristack.tech](https://tristack.tech).
2. A **project** with Manifold enabled on it.
3. An **API key** minted in that project.
4. A **wallet** with enough balance to cover the estimated cost of the call.

Miss one and the API says exactly which one: `manifold_disabled` for the toggle,
`insufficient_balance` for the wallet, `invalid_api_key` for the key.

## Two surfaces, one host

| Surface | Path | Auth | Purpose |
|---|---|---|---|
| Manifold | `/v1/manifold/...` | API key | The product: model calls and the model catalog. |
| Dashboard API | `/api/v1/...` | JWT | What the dashboard does: projects, keys, wallet, usage. |

Most integrations only ever touch Manifold. The
[dashboard API page](api/dashboard.md) covers the rest, as far as automating key creation
and reading usage requires.
