---
title: API overview
description: Base URL, conventions, error envelope and the endpoint index for the TriStack API.
---

# API overview

## Base URL

```text
https://api.tristack.tech
```

Every request is HTTPS. The dashboard and the marketing site live at
[tristack.tech](https://tristack.tech); the API is on its own host.

## Endpoints

| Endpoint | Auth | Purpose |
|---|---|---|
| [`POST /v1/manifold/messages`](messages.md) | API key | Send messages to a model and get a completion. |
| [`GET /v1/manifold/models`](models.md) | API key | The model catalog with current prices. |
| [`/api/v1/...`](dashboard.md) | JWT | Projects, keys, wallet and usage: what the dashboard does. |
| `GET /health` | none | Liveness. Returns `{ "status": "healthy", "timestamp": ... }`. |
| `GET /health/ready` | none | Readiness. Returns `{ "status", "totalDurationMs", "checks": [{ "name", "status", "description", "data", "error" }] }`, one entry per dependency. |
| [`POST /api/v1/contact`](../support.md#the-contact-endpoint) | none | The contact form behind [support](../support.md). |

`/health/ready` touches the dependencies it reports on, including the database, so point a
monitor at it on a sensible interval and leave `/health` for the load balancer's own tick.

## Conventions

**JSON both ways.** Send `Content-Type: application/json`. Manifold request and response
bodies use `snake_case` (`max_tokens`, `stop_reason`, `input_tokens`). The dashboard API
uses `camelCase`.

**Money is integer paise.** Never rupees, never floats. Rs 1 = 100 paise. A cost of
`{ "paise": 137 }` is Rs 1.37.

**Timestamps are UTC ISO-8601.**

**Request ids.** Every Manifold call gets an id of the form `mfr_` plus 24 hex characters.
It appears as `id` in the response and as `message_start.id` in a stream, and it is the
reference the wallet ledger and usage rows carry. Log it.

**Unknown routes.** Any unmatched path under `/api/...` or `/v1/...` answers
`404 { "error": "Unknown API route" }` rather than an HTML page, so a typo in a URL is
never mistaken for a broken response body.

## Error envelope

Errors that carry a body use the same envelope:

```json
{ "error": "The wallet balance cannot cover the estimated cost of this request.",
  "code": "insufficient_balance" }
```

| Field | Type | Notes |
|---|---|---|
| `error` | string | A human-readable sentence. Wording can change: do not match on it. |
| `code` | string, optional | A stable `snake_case` identifier. Branch on this where it is present. |

Not every error has both, so read the body defensively rather than assuming the two keys
are there:

- A `429` rate-limit rejection and the unauthenticated `401` challenge on `/api/v1/...`
  have **no body at all**. Calling `.json()` on one throws.
- The `404` for an unknown route, most dashboard `404`s and several dashboard `401`s carry
  `error` alone.
- A `400` from a body the server could not parse carries `title` and an `errors` object
  instead, and no `code`.
- An unexpected server error answers `500 { "error", "detail", "traceId" }`, with `detail`
  only outside production.

Branch on `code` and fall back to the HTTP status: that is the only rule that survives all
of these shapes.

Two errors add a field:

- `insufficient_balance` adds `requiredPaise`, the amount this call needed up front.
- Validation failures on the dashboard API may add a `fields` object keyed by field name.

Branch on `code` first and fall back to the HTTP status. The complete list is on the
[errors page](errors.md).

## Rate limits

Manifold (`/v1/manifold/...`) is not rate limited. Your wallet balance is the limit that
matters: a call that the balance cannot cover is rejected before it reaches a model.

Two surfaces are limited, each with its own numbers, and both answer `429` with an empty
body when exceeded:

| Surface | Per caller IP | Process-wide backstop |
|---|---|---|
| `/api/v1/account/...` | 10 per minute | 120 per minute |
| [`/api/v1/contact`](../support.md#the-contact-endpoint) | 5 per minute | 60 per minute |

The IP is the socket address. Everything else, the rest of the dashboard API included, is
unlimited.

A model can still refuse work under load. That surfaces as `429 provider_throttled`, which
is a signal to back off and retry, not a quota you have crossed.

## Versioning

The version lives in the path (`/v1/`). Additive changes (new fields on a response, new
models in the catalog, new optional request fields) ship without a version bump, so parse
JSON leniently and ignore fields you do not know. Anything that would break a correct
client gets a new path.

## Timeouts and retries

- Set a generous client timeout on `POST /v1/manifold/messages`. A large `max_tokens` on a
  large model can run for a while. Use [streaming](../guides/streaming.md) if you need
  output sooner.
- Retry `429 provider_throttled` and `502 provider_error` with exponential backoff and
  jitter. Both leave the wallet untouched, so a retry costs nothing extra.
- Do not retry `400`, `401`, `402` or `403`. They describe something only you can fix.
- There is no idempotency key. A retried call is a new call with a new `id`, and it is
  billed on its own.
