---
title: List models
description: GET /v1/manifold/models, the authoritative catalog of aliases and prices for a deployment.
---

# List models

<span class="ts-method ts-method--get">GET</span> `/v1/manifold/models`

Returns every model alias this deployment serves, with the price of each and the USD to
INR rate used to convert it.

- **Auth:** API key, as `Authorization: Bearer tsk_live_...` or `X-Api-Key`.
- **Parameters:** none.

!!! tip "This endpoint is authoritative"

    The [model catalog page](../pricing/models.md) is a snapshot for reading. This
    endpoint is the truth for the deployment you are calling: models get added, prices
    change, and the FX rate is configuration. Fetch it, cache it for a while, and never
    hardcode a price into a client.

Manifold does not have to be enabled on the project to read the catalog, so you can browse
prices with a key from a project that is not calling models yet.

## Response

```json
{
  "usdToInr": 90.0,
  "models": [
    {
      "alias": "nova-micro",
      "displayName": "Nova Micro",
      "usdPerMTokIn": 0.035,
      "usdPerMTokOut": 0.14,
      "paisePer1KTokensIn": 0.32,
      "paisePer1KTokensOut": 1.26
    }
  ]
}
```

| Field | Type | Notes |
|---|---|---|
| `usdToInr` | number | The conversion rate applied to the stored USD rates. |
| `models[].alias` | string | What you put in `model` on a request. |
| `models[].displayName` | string | The model's name, for showing to people. |
| `models[].usdPerMTokIn` | number | USD per million input tokens. |
| `models[].usdPerMTokOut` | number | USD per million output tokens. |
| `models[].paisePer1KTokensIn` | number | The same input rate in paise per 1000 tokens. |
| `models[].paisePer1KTokensOut` | number | The same output rate in paise per 1000 tokens. |

The paise columns are derived, not separately stored:

```text
paisePer1KTokens = round(usdPerMTok / 1000 * usdToInr * 100, 2)
```

The rounding to 2 decimal places is part of the conversion, and a half rounds to the even
digit. They are a readable form of the USD rates: price a call from `usdPerMTokIn` and
`usdPerMTokOut` rather than from these, as the formula below does.

Two things the response deliberately does not carry:

- **Which engine serves an alias.** Routing is internal. You address models by alias.
- **Whether an alias accepts images.** Multimodal support is not uniform across the
  catalog and is not reported here. The list is on the
  [vision page](../guides/vision.md).

## Errors

| Status | `code` | Cause |
|---|---|---|
| 401 | `invalid_api_key` | Missing, malformed, unknown or revoked key. |
| 401 | `project_archived` | The key's project is archived. |

An alias appearing here is not a guarantee that it is servable: a deployment can publish a
model it is not entitled to serve yet, and the call answers `403 model_access_denied`. The
[catalog page](../pricing/models.md) flags the aliases in that state today.

## Examples

=== "curl"

    ```bash
    curl -s https://api.tristack.tech/v1/manifold/models \
      -H "Authorization: Bearer $TRISTACK_API_KEY" | jq '.models[] | .alias'
    ```

=== "Python"

    ```python
    # pip install requests
    import os

    import requests

    response = requests.get(
        "https://api.tristack.tech/v1/manifold/models",
        headers={"Authorization": f"Bearer {os.environ['TRISTACK_API_KEY']}"},
        timeout=30,
    )
    response.raise_for_status()
    catalog = response.json()

    print(f"{len(catalog['models'])} models at {catalog['usdToInr']} INR per USD")
    for model in sorted(catalog["models"], key=lambda m: m["paisePer1KTokensOut"])[:5]:
        print(
            f"{model['alias']:<24} {model['displayName']:<32} "
            f"{model['paisePer1KTokensIn']:>6} in / {model['paisePer1KTokensOut']:>6} out"
        )
    ```

=== "Node"

    ```javascript
    // Node 18 or newer, no dependencies. ES modules: save as .mjs, or set
    // "type": "module" in package.json.
    const response = await fetch("https://api.tristack.tech/v1/manifold/models", {
      headers: { Authorization: `Bearer ${process.env.TRISTACK_API_KEY}` },
    });

    if (!response.ok) {
      const failure = await response.json();
      throw new Error(`${response.status} ${failure.code}: ${failure.error}`);
    }

    const catalog = await response.json();
    console.log(`${catalog.models.length} models at ${catalog.usdToInr} INR per USD`);

    for (const model of catalog.models) {
      console.log(model.alias, model.paisePer1KTokensIn, model.paisePer1KTokensOut);
    }
    ```

## Estimating a call before you make it

The catalog is enough to price a request yourself. Cost is linear in tokens:

```text
costPaise = ceil(
    (inputTokens * usdPerMTokIn + outputTokens * usdPerMTokOut)
    / 1e6 * usdToInr * 100
)
```

```python
from decimal import ROUND_CEILING, Decimal


def cost_paise(model: dict, input_tokens: int, output_tokens: int, usd_to_inr: float) -> int:
    """The server's own arithmetic, in exact decimal. Floats disagree by a paise."""
    usd_per_million = input_tokens * Decimal(str(model["usdPerMTokIn"])) + output_tokens * Decimal(
        str(model["usdPerMTokOut"])
    )
    paise = usd_per_million / 1_000_000 * Decimal(str(usd_to_inr)) * 100
    return int(paise.to_integral_value(rounding=ROUND_CEILING))
```

Use exact decimal arithmetic, not `float`. The server prices in decimal, so where the
product lands exactly on a whole paise, binary floating point puts it a hair above and the
ceiling adds one: the same call then reconciles a paise higher than `cost.paise` says. It
is the same reason money is integer paise everywhere in this API.

Rounding up to a whole paise happens once, at the end. Any call that used tokens therefore
costs at least 1 paise, however small the model.
[Pricing and billing](../pricing/billing.md) walks through a settled example.
