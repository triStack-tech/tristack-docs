---
title: Errors
description: The TriStack error codes, with the HTTP status, cause and fix for each, and what each one costs.
---

# Errors

## The envelope

```json
{ "error": "Manifold is not enabled for this project.", "code": "manifold_disabled" }
```

`code` is the stable identifier. Branch on it. `error` is a sentence for a human and its
wording can change between releases, so never match on it.

## Manifold codes

Everything `POST /v1/manifold/messages` and `GET /v1/manifold/models` can answer with. The
[dashboard API](#dashboard-api-codes) has a handful of its own, further down.

| Status | `code` | Meaning | What to do |
|---|---|---|---|
| 401 | `invalid_api_key` | The key is missing, malformed, unknown, or revoked. Unknown and revoked answer the same way on purpose. | Check the header form, then check the key in the dashboard. Mint a new one if in doubt. |
| 401 | `project_archived` | The key is valid but its project is archived. | Unarchive the project, or use a key from an active one. |
| 403 | `manifold_disabled` | Manifold is not enabled on the key's project. | Turn it on in the project settings. No new key is needed. |
| 400 | `invalid_request` | The body failed validation: a bad role, an empty message, a missing `text`, an unsupported block type, an unsupported `media_type`, malformed base64, or a non-positive `max_tokens`. | Read `error`, which names the offending field, and fix the body. |
| 400 | `unknown_model` | `model` is not an alias this deployment serves. | Fetch [`GET /v1/manifold/models`](models.md) and use an alias from it. |
| 402 | `insufficient_balance` | The wallet cannot cover the estimated cost. Carries `requiredPaise`. | Top up. Lowering `max_tokens` also lowers the estimate. |
| 429 | `provider_throttled` | The model is under load and refused the request. | Retry with exponential backoff and jitter. Consider a second alias as a fallback. |
| 400 | `provider_rejected` | The model refused the request itself: a parameter value outside its range, an image sent to a text-only model, or content it will not process. | Read `error`, which carries the model's own reason. |
| 403 | `model_access_denied` | The alias is published in the catalog but this deployment cannot serve it yet. | Use a different alias. The [catalog](../pricing/models.md) marks the affected rows. Branch on `code` here and ignore `error`: the sentence it carries describes the deployment's own configuration and is not something a caller can act on. |
| 502 | `provider_error` | The call failed after being accepted, for any other reason. | Retry once with backoff. If it repeats, try another alias. |
| 429 | none | Rate limit on one of the two limited surfaces, listed under [rate limits](index.md#rate-limits). The body is empty. | Slow down. Manifold itself is not rate limited. |
| 404 | none | `{ "error": "Unknown API route" }`. The path does not exist. | Check the URL. Manifold lives at `/v1/manifold/...`, the dashboard API at `/api/v1/...`. |

One code never appears in a response body:

| `code` | Where it appears | Meaning |
|---|---|---|
| `client_aborted` | Usage rows only | You closed the connection before the call finished. See [streaming](../guides/streaming.md) for what it costs. |

## Dashboard API codes

`/api/v1/...` uses the same envelope. These are the codes it adds, none of which Manifold
can return.

| Status | `code` | Where | Meaning |
|---|---|---|---|
| 403 | `email_unverified` | Top-up | The account's email address is not verified yet. Verify it and retry. |
| 400 | `below_minimum_topup` | Top-up | The amount is under the minimum of 10000 paise. |
| 400 | `invalid_status` | `GET /api/v1/usage` | `?status=` is not one of `all`, `succeeded`, `failed`, `provider_error`. |
| 400 | `invalid_range` | `GET /api/v1/usage` | `from` is after `to`. |
| 400 | `invalid_name`, `invalid_email`, `invalid_message` | [`POST /api/v1/contact`](../support.md#the-contact-endpoint) | The field is missing or too long. |

Not every dashboard failure carries a `code`: the account endpoints answer several
validation and conflict cases with `error` alone, among them a short password, an address
already registered, and an invalid or expired token. Branch on the HTTP status there.
Top-up creation has one more answer, a `503` when the server has no payment integration
configured, which is an operator problem rather than something a client can classify: treat
the status as the signal.

## What each error costs

| Outcome | Wallet | Appears in usage |
|---|---|---|
| `invalid_api_key`, `project_archived`, `manifold_disabled`, `invalid_request`, `unknown_model` | Untouched. Rejected before any hold. | No |
| `insufficient_balance` | Untouched. The hold could not be placed. | Yes, at 0 paise, recorded at most once per project per minute |
| `provider_throttled`, `provider_rejected`, `model_access_denied`, `provider_error` | Hold released in full. Nothing charged. | Yes, at 0 paise |
| `client_aborted` before any output | Hold released in full. | Yes, at 0 paise |
| `client_aborted` after some output | Settled at the whole input estimate plus the delivered output. | Yes, with a real cost |
| Success | Settled at real token usage. | Yes |

Every failure above is free except one: an abort after part of a stream arrived. That is
the point of holding an estimate and settling afterwards rather than charging up front.

One wrinkle in finding those rows again. An abort that arrives *after* the model reported
its usage settles at that real usage and is recorded as a **success**, because the call
did complete; only an abort that beat the usage event is recorded as
`client_aborted`. Filtering usage on `status=failed` will not show the first kind.

## Troubleshooting

### 401 with a key you just created

Almost always the header, not the key.

- `Authorization: Bearer tsk_live_...`: one space after `Bearer`, no quotes around the
  token, no trailing newline. A key read from a file with `$(cat key.txt)` often carries
  one.
- If your framework already sets `Authorization` for something else, use `X-Api-Key`
  instead.
- A bearer value that does not start with `tsk_` is read as a dashboard session token, not
  an API key. Pasting a JWT there produces a `401` that looks like a key problem.
- Confirm the key still exists and is not revoked. The dashboard shows the prefix and the
  last 4 characters of each key: compare them against what you deployed.

### 403 manifold_disabled

The project has the toggle off. It is a per-project switch, so a key that works in one
project can fail in another under the same account. Enable Manifold on the project the key
belongs to. The next request picks it up.

### 402 insufficient_balance on a small request

`requiredPaise` is the **hold**, not the bill. The hold assumes you will use all of
`max_tokens`, so a request with `max_tokens: 65536` on an expensive model can hold a
noticeable amount for a reply that ends up being two lines. Two fixes:

- Set `max_tokens` to what you actually expect to need.
- Keep enough balance for the peak number of calls you have in flight at once. Holds
  overlap.

Image requests hold more than they spend, for the same reason. See
[what images cost](../guides/vision.md#what-images-cost).

### 400 unknown_model

Aliases are exact, lowercase, and hyphenated: `llama-3-3-70b`, not `Llama-3.3-70B`. The
catalog is per deployment, so an alias from another environment can genuinely not exist
here. Fetch [`GET /v1/manifold/models`](models.md) and copy the alias out of the response.

### 400 provider_rejected

Three common causes:

1. **An image sent to a text-only model.** Check the
   [vision list](../guides/vision.md#models-that-accept-images).
2. **A parameter outside the model's range**, usually `temperature` or `top_p`. Omit them
   and see whether the call succeeds, then reintroduce them.
3. **The media type does not match the bytes**, for example a JPEG labelled `image/png`.

`error` carries the model's own words, which usually name the parameter.

### 429 provider_throttled

The model is busy. This is not your quota: Manifold does not rate limit the product
surface.

- Retry with exponential backoff and jitter, at least three attempts.
- Nothing is charged, so retrying costs only latency.
- If it persists, spread work across more than one alias, or move to a smaller model for
  the retry.

### 502 provider_error

Something failed after the call was accepted. The hold is released, so it costs nothing.
Retry once. If a second attempt fails on the same alias but another alias works, the
problem is with that model rather than with your request.

### The stream stopped without a cost

A stream that ends without a `message_delta` event did not complete. Look for an `error`
event just before the end. Treat "no `message_delta`" as failure in your consumer, so a
truncated reply never reaches your users as if it were whole. See
[streaming failures](../guides/streaming.md#failures).

### Nothing shows up in usage

Requests rejected before the wallet hold (`invalid_api_key`, `manifold_disabled`,
`invalid_request`, `unknown_model`) are answered but not recorded. If a client is failing
loudly and usage is empty, the failure is in that group: look at the HTTP responses your
client is getting rather than at the dashboard.

`insufficient_balance` is recorded at most once per project per minute, so a retry loop
against an empty wallet shows up as a handful of rows rather than thousands.
