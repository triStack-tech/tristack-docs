---
title: Support
description: How to reach us, what to include so the answer is useful, and the contact endpoint behind the form.
---

# Support

## Getting help

Write to [support@tristack.tech](mailto:support@tristack.tech).

An answer is only as fast as the detail in the question. Include:

- **The request id**, the `mfr_...` value from `id` on the response or `message_start.id`
  in a stream. It ties your call to the wallet ledger and the usage row, so it is the one
  field that turns "a call failed" into a specific record.
- **The `code`** from the error envelope, and the HTTP status.
- **The alias** you called and roughly when.

What not to send: your API key, or a password. Nobody at Tristack Technologies LLP needs
either, and a key pasted into an email should be revoked rather than explained. The
dashboard shows each key by prefix and last 4 characters, which is enough to identify one.

## Answers that are already written down

| Symptom | Page |
|---|---|
| A `4xx` or `5xx` you want explained | [Errors](api/errors.md) |
| `403 model_access_denied` on an alias from the catalog | [Availability](pricing/models.md#availability) |
| A bill that does not match what you expected | [Pricing and billing](pricing/billing.md) |
| A stream that stops early or costs more than it looks like it should | [Streaming](guides/streaming.md#aborting-a-stream) |
| An image refused with `400 provider_rejected` | [Models that accept images](guides/vision.md#models-that-accept-images) |

## The contact endpoint

The contact form on the site posts to a public endpoint, and nothing stops you posting to
it directly. It takes no authentication and stores nothing: a submission becomes an email.

<span class="ts-method">POST</span> `/api/v1/contact`

```bash
curl https://api.tristack.tech/api/v1/contact \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Your Name",
    "email": "you@example.com",
    "message": "What you need."
  }'
```

| Field | Required | Limit |
|---|:--:|---|
| `name` | yes | 100 characters |
| `email` | yes | 254 characters, and a plain address: `Name <a@b>` is refused |
| `message` | yes | 4000 characters |

A success answers `200` with `{ "message": "Thanks, we will get back to you." }`. Each
field has its own code when it fails:

| Status | `code` |
|---|---|
| 400 | `invalid_name` |
| 400 | `invalid_email` |
| 400 | `invalid_message` |

!!! warning "This endpoint is rate limited"

    5 requests per minute per caller IP, with a process-wide backstop of 60 per minute.
    Over either, the answer is `429` with an empty body. It is the tighter of the two
    limited surfaces on the API: see [rate limits](api/index.md#rate-limits).

For anything about an actual call, email is better than the form. The form has no place to
put a request id, and the request id is what makes the answer specific.

## Who you are writing to

TriStack Manifold is a product of Tristack Technologies LLP (LLPIN ACP-3743), registered
office B-35, Vinoba Kunj Apartments, Sector 9, Rohini, Delhi 110085, India.

There are two ways in, and they are the two on this page: the email address above, and the
contact form on [tristack.tech](https://tristack.tech), which posts to the endpoint
documented in the previous section. Neither carries a published response time.
