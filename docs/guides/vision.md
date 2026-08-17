---
title: Vision and images
description: Image content blocks, supported media types, base64 rules, and what images do to the cost estimate.
---

# Vision and images

Some models read images. You send them as content blocks in the same
[`POST /v1/manifold/messages`](../api/messages.md) call, alongside your text.

## The block format

Replace the plain string `content` with an array of blocks:

```json
{
  "model": "nova-lite",
  "max_tokens": 1024,
  "messages": [
    {
      "role": "user",
      "content": [
        { "type": "text", "text": "What is written on this sign?" },
        {
          "type": "image",
          "source": {
            "media_type": "image/png",
            "data": "iVBORw0KGgoAAAANSUhEUgAA..."
          }
        }
      ]
    }
  ]
}
```

| Field | Required | Notes |
|---|:--:|---|
| `type` | yes | `"image"` |
| `source.media_type` | yes | One of the five types below. |
| `source.data` | yes | Raw base64 of the image bytes. |
| `source.type` | no | Accepted and ignored. The bytes are always read from `source.data` as raw base64, so a non-base64 source is rejected as `400 invalid_request` on `source.data`. |

### Supported media types

| `media_type` | Format |
|---|---|
| `image/png` | PNG |
| `image/jpeg` | JPEG |
| `image/jpg` | JPEG, the same thing under the name people actually type |
| `image/gif` | GIF |
| `image/webp` | WebP |

Anything else answers `400 invalid_request` and names the value it did not recognise.

### Base64 rules

- **Raw base64 only.** Strip the data URI prefix. `data:image/png;base64,iVBOR...` is
  rejected; `iVBOR...` is accepted.
- **Line breaks are unnecessary** but harmless. Prefer one unwrapped line.
- **The media type must match the bytes.** Labelling a JPEG as `image/png` gets past
  validation and is then refused further down as `400 provider_rejected`.
- **Invalid base64 is caught before any billing.** A malformed `data` field answers
  `400 invalid_request` and no hold is placed, so a mistake here is free.

### Several images

An image block is just a block. Put as many as you need in one message, in the order you
want them read, and interleave text around them:

```json
{
  "role": "user",
  "content": [
    { "type": "text", "text": "Two screenshots of the same page. What changed?" },
    { "type": "image", "source": { "media_type": "image/png", "data": "<before>" } },
    { "type": "image", "source": { "media_type": "image/png", "data": "<after>" } },
    { "type": "text", "text": "Answer as a bullet list." }
  ]
}
```

Every model has its own limit on how many images it will accept and how large they can be.
Past that limit the answer is `400 provider_rejected` with the model's own reason.

## Models that accept images

Multimodal support is not uniform, and
[`GET /v1/manifold/models`](../api/models.md) does not report it. These are the aliases
that take image blocks:

--8<-- "model-vision.md"

Sending an image to any other alias, `nova-micro` included, answers
`400 provider_rejected`.

!!! note "How this list is maintained"

    Because the catalog endpoint carries no vision flag, this list is kept by hand in the
    documentation source rather than read from the API. Every other number on this page is
    generated from a captured catalog response and checked against it after each build;
    this one column cannot be, so treat it as editorial. If an alias here refuses an image
    with `400 provider_rejected`, that is the list being wrong, and it is worth telling us
    about: see [support](../support.md).

## What images cost

Images are billed as input tokens, like text. There is no separate image fee. What differs
is the **pre-flight estimate**, and it is worth understanding, because an image can hold a
lot more of your balance than it eventually spends.

Before any call, Manifold places a wallet hold for an estimate. The input side of that
estimate counts characters and divides by 4, and an image block contributes the length of
its **base64 string**, which is 4 characters for every 3 bytes of image.

Worked through, for a 200 KiB PNG and a short question on `nova-lite`, with
`max_tokens: 1024`:

| Step | Value |
|---|---|
| Image bytes | 204800 |
| Base64 characters | 273068 |
| Question text | 29 characters |
| Estimated input tokens `(273068 + 29 + 3) / 4` | 68275 |
| Estimated input cost `68275 * 0.06 USD/MTok` | 0.0040965 USD |
| Estimated output cost `1024 * 0.24 USD/MTok` | 0.00024576 USD |
| Hold, converted at 90 INR per USD and rounded up | **40 paise** |

The model then counts the image in its own way, usually a few hundred to a few thousand
tokens rather than 68275, and the settlement uses those real numbers. A settled call for
that request might report 1600 input tokens and 48 output tokens, which is
`ceil((1600 * 0.06 + 48 * 0.24) / 1e6 * 90 * 100)` = **1 paise**, and the other 39 paise
go straight back to the wallet.

So: images make the hold large and the bill small. Two consequences:

- A wallet with a few paise in it can answer `402 insufficient_balance` for an image call
  that would have cost 1 paise. The `requiredPaise` field tells you the size of the hold,
  not the size of the bill.
- Sending many image requests at once holds money for all of them at once. Keep some
  headroom in the balance.

Keeping `max_tokens` tight lowers the hold too, and costs nothing: the settlement only
charges for tokens actually generated.

## Practical guidance

- **Downscale before sending.** Most questions about a screenshot are answerable at
  1000 to 1500 pixels on the long edge. Smaller images mean less base64, a smaller hold,
  and usually faster answers.
- **JPEG for photographs, PNG for screenshots and diagrams.** JPEG at quality 80 is a
  fraction of the bytes of a PNG of the same photograph.
- **One question per image, where you can.** It keeps the failure obvious when a model
  misreads one of several images.
- **Do not send images to a text-only model** as a fallback path. The refusal costs
  nothing, but it is an avoidable round trip: check the table above first.

## Complete examples

=== "Python"

    ```python
    # pip install requests
    import base64
    import os
    from pathlib import Path

    import requests

    image = Path("sign.png")
    encoded = base64.standard_b64encode(image.read_bytes()).decode("ascii")

    response = requests.post(
        "https://api.tristack.tech/v1/manifold/messages",
        headers={"Authorization": f"Bearer {os.environ['TRISTACK_API_KEY']}"},
        json={
            "model": "nova-lite",
            "max_tokens": 512,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What is written on this sign?"},
                        {
                            "type": "image",
                            "source": {"media_type": "image/png", "data": encoded},
                        },
                    ],
                }
            ],
        },
        timeout=120,
    )
    if response.status_code != 200:
        failure = response.json()
        raise RuntimeError(f"{response.status_code} {failure['code']}: {failure['error']}")

    body = response.json()
    print(body["content"][0]["text"])
    print("cost:", body["cost"]["paise"], "paise")
    ```

=== "Node"

    ```javascript
    // Node 18 or newer, no dependencies. ES modules: save as .mjs, or set
    // "type": "module" in package.json.
    import { readFile } from "node:fs/promises";

    const encoded = (await readFile("sign.png")).toString("base64");

    const response = await fetch("https://api.tristack.tech/v1/manifold/messages", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${process.env.TRISTACK_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "nova-lite",
        max_tokens: 512,
        messages: [
          {
            role: "user",
            content: [
              { type: "text", text: "What is written on this sign?" },
              {
                type: "image",
                source: { media_type: "image/png", data: encoded },
              },
            ],
          },
        ],
      }),
    });

    const body = await response.json();
    if (!response.ok) throw new Error(`${response.status} ${body.code}: ${body.error}`);

    console.log(body.content[0].text);
    console.log("cost:", body.cost.paise, "paise");
    ```

=== "curl"

    ```bash
    # base64 -w0 keeps it on one line (use `base64 -i sign.png` on macOS).
    ENCODED=$(base64 -w0 sign.png)

    jq -n --arg data "$ENCODED" '{
      model: "nova-lite",
      max_tokens: 512,
      messages: [{
        role: "user",
        content: [
          { type: "text", text: "What is written on this sign?" },
          { type: "image", source: { media_type: "image/png", data: $data } }
        ]
      }]
    }' | curl https://api.tristack.tech/v1/manifold/messages \
      -H "Authorization: Bearer $TRISTACK_API_KEY" \
      -H "Content-Type: application/json" \
      --data-binary @-
    ```

    Building the body with `jq` avoids the shell-quoting problems that come with pasting a
    300 KB base64 string into a `-d` argument.
