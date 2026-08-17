---
title: Create a message
description: POST /v1/manifold/messages, every parameter, every response field and every error it can return.
---

# Create a message

<span class="ts-method">POST</span> `/v1/manifold/messages`

Sends a conversation to a model and returns its reply, either as one JSON body or as a
[stream of events](../guides/streaming.md).

- **Auth:** API key, as `Authorization: Bearer tsk_live_...` or `X-Api-Key`.
- **Content type:** `application/json`, with `snake_case` field names.

## Request

```json
{
  "model": "nova-micro",
  "system": "You answer in one sentence.",
  "messages": [
    { "role": "user", "content": "Say hello from TriStack." }
  ],
  "max_tokens": 1024,
  "temperature": 0.7,
  "top_p": 0.9,
  "stop_sequences": ["\n\n"],
  "stream": false
}
```

### Parameters

| Field | Type | Required | Default | Notes |
|---|---|:--:|---|---|
| `model` | string | yes | none | An alias from [`GET /v1/manifold/models`](models.md), for example `nova-micro`. Unknown values answer `400 unknown_model`. |
| `messages` | array | yes | none | The conversation, oldest first. Must contain at least one entry. |
| `max_tokens` | integer | no | `4096` | Upper bound on generated tokens. Must be positive. Values above the cap of `65536` are clamped to it rather than rejected. |
| `system` | string | no | none | System prompt. Sent outside the message list, as the model expects. |
| `temperature` | number | no | model default | Passed through untouched. Omit it to keep the model's own default. |
| `top_p` | number | no | model default | Passed through untouched. |
| `stop_sequences` | array of strings | no | none | Generation stops as soon as one of these is produced, and `stop_reason` comes back as `stop_sequence`. |
| `stream` | boolean | no | `false` | `true` switches the response to server-sent events. See [streaming](../guides/streaming.md). |

`temperature` and `top_p` ranges differ between models, and the API does not narrow them.
A value the model refuses comes back as `400 provider_rejected` with the model's own
complaint in `error`.

### The `messages` array

| Field | Type | Notes |
|---|---|---|
| `role` | string | `user` or `assistant`. Any other value answers `400 invalid_request`. |
| `content` | string or array | The message body. A bare string is shorthand for a single text block. |

There is no `system` role: use the top-level `system` parameter.

The conversation is stateless. Manifold stores no history, so a multi-turn chat means
sending the previous turns yourself:

```json
{
  "model": "llama-3-3-70b",
  "max_tokens": 512,
  "messages": [
    { "role": "user", "content": "Name a prime between 10 and 20." },
    { "role": "assistant", "content": "13." },
    { "role": "user", "content": "And the next one after that?" }
  ]
}
```

### Content blocks

When `content` is an array, each entry is a typed block.

=== "Text block"

    ```json
    { "type": "text", "text": "What is written on this sign?" }
    ```

    | Field | Type | Required | Notes |
    |---|---|:--:|---|
    | `type` | string | yes | `"text"` |
    | `text` | string | yes | The text. May be empty, but the field must be present. |

=== "Image block"

    ```json
    {
      "type": "image",
      "source": {
        "media_type": "image/png",
        "data": "iVBORw0KGgoAAAANSUhEUgAA..."
      }
    }
    ```

    | Field | Type | Required | Notes |
    |---|---|:--:|---|
    | `type` | string | yes | `"image"` |
    | `source.media_type` | string | yes | `image/png`, `image/jpeg`, `image/jpg`, `image/gif` or `image/webp`. |
    | `source.data` | string | yes | Raw base64. No `data:` URI prefix, no newlines needed. |
    | `source.type` | string | no | Accepted and ignored. The bytes are always read from `source.data` as raw base64, so a non-base64 source is rejected as `400 invalid_request` on `source.data`. |

    Only vision-capable models accept image blocks. See
    [vision and images](../guides/vision.md).

Any other `type` value answers `400 invalid_request`.

## Response

```json
{
  "id": "mfr_9f7922159e6dab6a72166e1f",
  "model": "nova-micro",
  "role": "assistant",
  "content": [{ "type": "text", "text": "Hello from TriStack!" }],
  "stop_reason": "end_turn",
  "usage": { "input_tokens": 10, "output_tokens": 6 },
  "cost": { "paise": 1 }
}
```

| Field | Type | Notes |
|---|---|---|
| `id` | string | `mfr_` plus 24 hex characters. Matches the ledger entry and the usage row. |
| `model` | string | The alias you sent, echoed back. |
| `role` | string | Always `assistant`. |
| `content` | array | Text blocks, in order. Concatenate `text` across them for the full reply. |
| `stop_reason` | string | Why generation ended. See below. |
| `usage.input_tokens` | integer | Tokens the model counted for the prompt. |
| `usage.output_tokens` | integer | Tokens generated. |
| `cost.paise` | integer | What this call actually cost, already settled against the wallet. |

`stop_reason` is passed through from the model. The common values:

| Value | Meaning |
|---|---|
| `end_turn` | The model finished on its own. |
| `max_tokens` | It hit your `max_tokens` cap. The reply is cut off: raise the cap and ask again if you need the rest. |
| `stop_sequence` | One of your `stop_sequences` was produced. |

Treat the list as open. A model can report a value of its own, so branch on the ones you
handle and pass the rest through.

## What it costs

An estimate is held against the wallet before the call, the real token usage is settled
after it, and the difference is returned, or the shortfall taken where the settled cost
came out above the estimate. `cost.paise` on the response is the settled amount, not the
estimate. A call that fails before producing output costs nothing.
[Pricing and billing](../pricing/billing.md) works an example through in full.

## Order of checks

Knowing the order tells you what a given error rules out.

1. **Key** resolved, project `Active`. Otherwise `401`.
2. **Manifold enabled** on the project. Otherwise `403 manifold_disabled`.
3. **Request shape** validated: roles, content blocks, base64, media types, positive
   `max_tokens`. Otherwise `400 invalid_request`.
4. **Model alias** resolved against the catalog. Otherwise `400 unknown_model`.
5. **Wallet hold** placed for the estimate. Otherwise `402 insufficient_balance`.
6. **The model is called.** Failures from here are `429`, `400 provider_rejected`,
   `403 model_access_denied` or `502 provider_error`, and the hold is released.

Steps 1 to 4 reject before any money moves, and those rejections are not recorded in your
usage figures. From step 5 onward the request exists in the ledger, even if it ends up
costing 0 paise.

## Errors

| Status | `code` | Cause | Fix |
|---|---|---|---|
| 401 | `invalid_api_key` | Missing, malformed, unknown or revoked key. | Check the header form and the key. |
| 401 | `project_archived` | The key's project is archived. | Unarchive it, or use a key from an active project. |
| 403 | `manifold_disabled` | Manifold is off for the project. | Enable it in the dashboard. |
| 400 | `invalid_request` | Shape or validation failure. `error` says which field. | Fix the body. |
| 400 | `unknown_model` | `model` is not an alias in this deployment. | Read [`GET /models`](models.md). |
| 402 | `insufficient_balance` | The balance cannot cover the estimate. `requiredPaise` is included. | Top up. |
| 429 | `provider_throttled` | The model is under load. | Retry with exponential backoff. |
| 400 | `provider_rejected` | The model refused the request: an unsupported parameter value, or an image sent to a text-only model. | Read `error` and adjust. |
| 403 | `model_access_denied` | The alias is in the catalog but not servable on this deployment yet. | Use another alias. Branch on `code`, not `error`: that sentence describes the deployment's configuration and is not actionable from a client. |
| 502 | `provider_error` | The call failed after being accepted. The hold is released. | Retry once, then fall back to another model. |

Full descriptions are on the [errors page](errors.md).

## Examples

### Minimal call

=== "curl"

    ```bash
    curl https://api.tristack.tech/v1/manifold/messages \
      -H "Authorization: Bearer $TRISTACK_API_KEY" \
      -H "Content-Type: application/json" \
      -d '{
        "model": "nova-micro",
        "max_tokens": 1024,
        "messages": [
          { "role": "user", "content": "Say hello from TriStack." }
        ]
      }'
    ```

=== "Python"

    ```python
    # pip install requests
    import os

    import requests

    API = "https://api.tristack.tech"
    KEY = os.environ["TRISTACK_API_KEY"]


    def ask(prompt: str, model: str = "nova-micro", max_tokens: int = 1024) -> str:
        response = requests.post(
            f"{API}/v1/manifold/messages",
            headers={"Authorization": f"Bearer {KEY}"},
            json={
                "model": model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=120,
        )
        if response.status_code != 200:
            failure = response.json()
            raise RuntimeError(f"{response.status_code} {failure['code']}: {failure['error']}")

        body = response.json()
        return "".join(block["text"] for block in body["content"])


    print(ask("Say hello from TriStack."))
    ```

=== "Node"

    ```javascript
    // Node 18 or newer, no dependencies. ES modules: save as .mjs, or set
    // "type": "module" in package.json.
    const API = "https://api.tristack.tech";
    const KEY = process.env.TRISTACK_API_KEY;

    async function ask(prompt, { model = "nova-micro", maxTokens = 1024 } = {}) {
      const response = await fetch(`${API}/v1/manifold/messages`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${KEY}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model,
          max_tokens: maxTokens,
          messages: [{ role: "user", content: prompt }],
        }),
      });

      const body = await response.json();
      if (!response.ok) {
        throw new Error(`${response.status} ${body.code}: ${body.error}`);
      }

      return body.content.map((block) => block.text).join("");
    }

    console.log(await ask("Say hello from TriStack."));
    ```

### System prompt, multi-turn, and stop sequences

=== "curl"

    ```bash
    curl https://api.tristack.tech/v1/manifold/messages \
      -H "Authorization: Bearer $TRISTACK_API_KEY" \
      -H "Content-Type: application/json" \
      -d '{
        "model": "llama-3-3-70b",
        "system": "You are a terse assistant. Answer in one line.",
        "max_tokens": 256,
        "temperature": 0.2,
        "stop_sequences": ["\n\n"],
        "messages": [
          { "role": "user", "content": "Name a prime between 10 and 20." },
          { "role": "assistant", "content": "13." },
          { "role": "user", "content": "And the next one after that?" }
        ]
      }'
    ```

=== "Python"

    ```python
    import os

    import requests

    response = requests.post(
        "https://api.tristack.tech/v1/manifold/messages",
        headers={"Authorization": f"Bearer {os.environ['TRISTACK_API_KEY']}"},
        json={
            "model": "llama-3-3-70b",
            "system": "You are a terse assistant. Answer in one line.",
            "max_tokens": 256,
            "temperature": 0.2,
            "stop_sequences": ["\n\n"],
            "messages": [
                {"role": "user", "content": "Name a prime between 10 and 20."},
                {"role": "assistant", "content": "13."},
                {"role": "user", "content": "And the next one after that?"},
            ],
        },
        timeout=120,
    )
    response.raise_for_status()
    print(response.json()["content"][0]["text"])
    ```

=== "Node"

    ```javascript
    // Node 18 or newer, no dependencies. ES modules: save as .mjs, or set
    // "type": "module" in package.json.
    const response = await fetch("https://api.tristack.tech/v1/manifold/messages", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${process.env.TRISTACK_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "llama-3-3-70b",
        system: "You are a terse assistant. Answer in one line.",
        max_tokens: 256,
        temperature: 0.2,
        stop_sequences: ["\n\n"],
        messages: [
          { role: "user", content: "Name a prime between 10 and 20." },
          { role: "assistant", content: "13." },
          { role: "user", content: "And the next one after that?" },
        ],
      }),
    });

    const body = await response.json();
    if (!response.ok) throw new Error(`${response.status} ${body.code}: ${body.error}`);
    console.log(body.content[0].text, body.stop_reason);
    ```

### Handling errors properly

=== "Python"

    ```python
    import os
    import random
    import time

    import requests

    RETRYABLE = {"provider_throttled", "provider_error"}


    def call_with_retry(payload: dict, attempts: int = 4) -> dict:
        headers = {"Authorization": f"Bearer {os.environ['TRISTACK_API_KEY']}"}
        for attempt in range(attempts):
            response = requests.post(
                "https://api.tristack.tech/v1/manifold/messages",
                headers=headers,
                json=payload,
                timeout=120,
            )
            if response.status_code == 200:
                return response.json()

            failure = response.json()
            code = failure.get("code", "")
            if code not in RETRYABLE or attempt == attempts - 1:
                raise RuntimeError(f"{response.status_code} {code}: {failure.get('error')}")

            # Exponential backoff with jitter. A throttled or failed call costs nothing,
            # so retrying is free apart from the latency.
            time.sleep((2**attempt) + random.random())

        raise AssertionError("unreachable")
    ```

=== "Node"

    ```javascript
    // Node 18 or newer, no dependencies. ES modules: save as .mjs, or set
    // "type": "module" in package.json.
    const RETRYABLE = new Set(["provider_throttled", "provider_error"]);
    const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

    export async function callWithRetry(payload, attempts = 4) {
      for (let attempt = 0; attempt < attempts; attempt += 1) {
        const response = await fetch("https://api.tristack.tech/v1/manifold/messages", {
          method: "POST",
          headers: {
            Authorization: `Bearer ${process.env.TRISTACK_API_KEY}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        });

        const body = await response.json();
        if (response.ok) return body;

        if (!RETRYABLE.has(body.code) || attempt === attempts - 1) {
          throw new Error(`${response.status} ${body.code}: ${body.error}`);
        }

        // Exponential backoff with jitter; a failed call is not billed.
        await sleep(2 ** attempt * 1000 + Math.random() * 1000);
      }
    }
    ```
