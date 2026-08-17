---
title: Dashboard API
description: The JWT-authenticated endpoints behind the dashboard, as far as automating keys, wallet checks and usage requires.
---

# Dashboard API

Everything the dashboard does is an HTTP call you can make yourself: projects, API keys,
wallet balance and usage. It shares a host with Manifold but is a different surface.

|  | Manifold | Dashboard API |
|---|---|---|
| Path | `/v1/manifold/...` | `/api/v1/...` |
| Auth | API key (`tsk_...`) | JWT from login |
| JSON style | `snake_case` | `camelCase` |
| Purpose | Calling models | Managing the account that calls them |

The two credentials are not interchangeable. An API key on `/api/v1/...` fails, and a JWT
on `/v1/manifold/...` fails.

!!! note "Most integrations do not need this page"

    Mint a key in the dashboard once, put it in your environment, and call Manifold. This
    page is for the cases where you want key creation or usage reporting automated.

## Authentication

```bash
curl https://api.tristack.tech/api/v1/account/login \
  -H "Content-Type: application/json" \
  -d '{ "email": "you@example.com", "password": "your-password" }'
```

```json
{
  "token": "<jwt>",
  "userId": "1f5b...",
  "email": "you@example.com",
  "displayName": "You",
  "emailVerified": true
}
```

Send it as `Authorization: Bearer <jwt>` on every other call here. The token is valid for
24 hours. There is no refresh endpoint: log in again.

!!! warning "Rate limit"

    `/api/v1/account/...` allows 10 requests per minute per caller IP, with a process-wide
    backstop of 120 per minute. Over either limit the answer is `429` with an empty body.
    Log in once and reuse the token.

Storing an account password in a service so it can log in is worse than storing an API
key: the password can create keys and spend money, and it cannot be revoked without
changing it everywhere. If you automate this, keep it in one place, well away from the
code that calls models.

## Projects

A project object:

```json
{
  "id": "8f1c...",
  "name": "production",
  "manifoldEnabled": true,
  "relaySmsEnabled": false,
  "relayOtpEnabled": false,
  "relayVoiceEnabled": false,
  "status": "Active",
  "createdAt": "2026-08-17T09:12:44Z"
}
```

`status` is `Active` or `Archived`. The `relay*` flags belong to products that are not
live yet: they are accepted and stored by `PATCH`, but nothing reads them today.

| Endpoint | Body | Returns |
|---|---|---|
| `GET /api/v1/projects` | none | Every project on the account. |
| `POST /api/v1/projects` | `{ "name": "production" }`, 1 to 128 characters | The created project. |
| `GET /api/v1/projects/{id}` | none | One project. `404` if it is not yours. |
| `PATCH /api/v1/projects/{id}` | any of `name`, `manifoldEnabled`, `archived`, `relaySmsEnabled`, `relayOtpEnabled`, `relayVoiceEnabled` | The updated project. Omitted fields are unchanged. |

Enabling Manifold on a project is a `PATCH`:

```bash
curl -X PATCH https://api.tristack.tech/api/v1/projects/$PROJECT_ID \
  -H "Authorization: Bearer $TRISTACK_JWT" \
  -H "Content-Type: application/json" \
  -d '{ "manifoldEnabled": true }'
```

## API keys

| Endpoint | Body | Returns |
|---|---|---|
| `POST /api/v1/projects/{id}/keys` | `{ "name": "ci", "mode": "live" }` | `{ id, name, token, prefix, hint, createdAt }` |
| `GET /api/v1/projects/{id}/keys` | none | `[{ id, name, prefix, hint, createdAt, revokedAt, lastUsedAt }]` |
| `DELETE /api/v1/projects/{id}/keys/{keyId}` | none | `{ message }`. Revokes the key. |

`mode` is `live` or `test` and only decides the prefix.

!!! danger "`token` appears once"

    The create response is the only place the full key exists. It is stored as a hash, so
    a lost key can be revoked but never recovered. The list endpoint returns `hint`, the
    last 4 characters, which identifies a key without exposing it.

Deleting an already-revoked key, a key that never existed, and a key in someone else's
project all answer `404`. That is deliberate: it tells a caller nothing about keys that
are not theirs.

```python
# pip install requests
import os

import requests

API = "https://api.tristack.tech"
session = requests.Session()
session.headers["Authorization"] = f"Bearer {os.environ['TRISTACK_JWT']}"

project_id = os.environ["TRISTACK_PROJECT_ID"]
created = session.post(
    f"{API}/api/v1/projects/{project_id}/keys",
    json={"name": "ci-runner", "mode": "live"},
    timeout=30,
)
created.raise_for_status()

key = created.json()
print("store this now, it will not be shown again:", key["token"])
```

## Wallet

`GET /api/v1/wallet`

```json
{
  "balancePaise": 98422,
  "minTopUpPaise": 10000,
  "recentTopups": [
    {
      "id": "3a91...",
      "amountPaise": 100000,
      "status": "Paid",
      "invoiceUrl": null,
      "createdAt": "2026-08-16T18:02:11Z",
      "paidAt": "2026-08-16T18:02:48Z"
    }
  ]
}
```

`status` is `Pending` or `Paid`, and the ten most recent top-ups are returned. Each top-up
also carries an opaque payment-provider order reference, omitted from the example above
because nothing you write needs it. A good health check for a service that calls models:
read `balancePaise` on a schedule and alarm before it runs out.

### Adding money

Paying happens in the browser checkout, so **top up in the dashboard**. Two endpoints do
exist around it, and a provisioning script can use the first, but neither replaces the
checkout: an order that is never paid stays `Pending` forever.

| Endpoint | Body | Returns |
|---|---|---|
| `POST /api/v1/wallet/topup` | `{ "amountPaise": 10000 }` | `{ topUpId, orderId, keyId, amountPaise }`. Creates the order the checkout then pays. |
| `POST /api/v1/wallet/topup/confirm` | the signed result the checkout hands back | `{ "status": "credited" }` or `{ "status": "pending" }`. |

`POST /api/v1/wallet/topup` needs a verified email address on top of the JWT, and it is
the only place three error codes appear:

| Status | `code` | Meaning |
|---|---|---|
| 403 | `email_unverified` | Verify the address first. |
| 400 | `below_minimum_topup` | The amount is under `minTopUpPaise`. |
| 503 | not documented | The server has no payment integration configured. It carries a `code`, but branch on the status instead: it is an operator problem, not one a client can classify further. |

`"credited"` and `"pending"` are what `POST /api/v1/wallet/topup/confirm` answers once the
signature verifies. Before that it has two other answers: `400` with `error` alone when the
signature does not verify, and a bodiless `401` when the token carries no usable subject.
Neither is a pending payment. Both are caller bugs, so do not read a non-2xx here as
`"pending"` and do not retry it.

`confirm` is belt and braces rather than the thing that credits you: a webhook and an
hourly reconciliation sweep settle the same top-up independently, and crediting is
idempotent, so `"pending"` means "not yet", never "lost".

An API key can do none of this. Keys only reach `/v1/manifold/...`, so a leaked key cannot
buy anything.

`GET /api/v1/wallet/transactions?limit=&before=`

The ledger, newest first. `limit` clamps to 1 to 100 (default 50), `before` is a timestamp
cursor. It returns a bare array:

```json
[
  {
    "id": "7c22...",
    "projectId": "8f1c...",
    "type": "Debit",
    "amountPaise": 1,
    "balanceAfterPaise": 98422,
    "reference": "mfr_9f7922159e6dab6a72166e1f",
    "description": null,
    "createdAt": "2026-08-17T10:31:02Z"
  }
]
```

`description` is usually `null`. It is filled in where a line needs explaining: `Wallet
top-up` on a credit, the reason a hold was released on a `HoldRelease`, which is where the
error code of a failed call ends up, and a note on a `Debit` that was capped at the
available balance.

| `type` | Meaning |
|---|---|
| `Topup` | Money added. |
| `Hold` | An estimate reserved before a call. |
| `Debit` | The settled cost of a call. If that cost is more than the wallet has left, the debit is capped at the balance and `description` says so, which is the one case where it is smaller than the `cost.paise` the call reported. |
| `HoldRelease` | The hold returned in full. The settled cost is taken separately, on the `Debit` line with the same `reference`. |
| `Grant` | Credit added by TriStack. |
| `Reversal` | A correction. |

`amountPaise` is always positive: the direction is implied by `type`. `reference` carries
the `mfr_...` request id, so a line in the ledger ties back to the exact call that produced
it.

## Usage

`GET /api/v1/usage`

| Query | Notes |
|---|---|
| `projectId` | Narrow to one project. A project that is not yours returns an empty result, never someone else's data. |
| `status` | `all` (default), `succeeded`, `failed` or `provider_error`. Matching is case-insensitive and ignores `_` and `-`, so `ProviderError` and `provider-error` work too; anything that does not canonicalize to one of the four answers `400 invalid_status`. |
| `from`, `to` | Timestamps. Default: the last 30 days. `from > to` answers `400 invalid_range`. |

A `projectId` that is not a uuid, or a `from`/`to` that is not a timestamp, is rejected by
the framework before the endpoint runs: a `400` carrying `title` and `errors`, with no
`code`. See [the error envelope](index.md#error-envelope).

!!! warning "`status=failed` is narrower than the `failed*` response fields"

    The filter matches the stored status exactly, and provider failures are stored as
    `ProviderError`, not `Failed`. So `?status=failed` returns balance rejections and
    aborts only, while the `failed*` fields described [below](#the-fields) count every
    non-success, `provider_error` included. The same field therefore means different
    things with and without the filter. For a complete failure picture, leave `status`
    off.

!!! warning "The query parameter and the response field are spelled differently"

    You send `?status=provider_error`, and the response echoes `"status": "ProviderError"`.
    Every `status` in the response body, the echoed filter and each `byStatus[].status`,
    is the enum name: `Succeeded`, `Failed`, `ProviderError`, or the literal `all` when no
    filter was applied. A client that round-trips the value it sent, or keys a lookup off
    `byStatus[].status`, matches nothing.

The response aggregates requests by day, project, model and outcome:

```json
{
  "from": "2026-07-18T00:00:00Z",
  "to": "2026-08-17T00:00:00Z",
  "projectId": null,
  "status": "all",
  "totalRequests": 3,
  "totalInputTokens": 4010,
  "totalOutputTokens": 46,
  "totalCostPaise": 3,
  "succeededRequests": 1,
  "succeededInputTokens": 10,
  "succeededOutputTokens": 6,
  "succeededCostPaise": 1,
  "failedRequests": 2,
  "failedInputTokens": 4000,
  "failedOutputTokens": 40,
  "failedCostPaise": 2,
  "rows": [
    {
      "day": "2026-08-17",
      "projectId": "8f1c...",
      "projectName": "production",
      "modelAlias": "nova-micro",
      "requests": 3,
      "inputTokens": 4010,
      "outputTokens": 46,
      "costPaise": 3,
      "succeededRequests": 1,
      "failedRequests": 2,
      "succeededCostPaise": 1,
      "failedCostPaise": 2,
      "failedInputTokens": 4000,
      "failedOutputTokens": 40
    }
  ],
  "byDay": [
    {
      "day": "2026-08-17",
      "requests": 3,
      "inputTokens": 4010,
      "outputTokens": 46,
      "costPaise": 3,
      "succeededRequests": 1,
      "failedRequests": 2,
      "succeededCostPaise": 1,
      "failedCostPaise": 2
    }
  ],
  "byModel": [
    {
      "modelAlias": "nova-micro",
      "requests": 3,
      "inputTokens": 4010,
      "outputTokens": 46,
      "costPaise": 3,
      "succeededRequests": 1,
      "failedRequests": 2,
      "succeededCostPaise": 1,
      "failedCostPaise": 2
    }
  ],
  "byStatus": [
    { "status": "Succeeded", "requests": 1, "inputTokens": 10, "outputTokens": 6, "costPaise": 1 },
    { "status": "Failed", "requests": 2, "inputTokens": 4000, "outputTokens": 40, "costPaise": 2 },
    { "status": "ProviderError", "requests": 0, "inputTokens": 0, "outputTokens": 0, "costPaise": 0 }
  ],
  "failures": [
    {
      "errorCode": "client_aborted",
      "description": "The caller hung up mid-request; anything already streamed is still billed.",
      "requests": 2,
      "costPaise": 2,
      "lastSeen": "2026-08-17T10:31:02Z",
      "projects": [{ "projectId": "8f1c...", "projectName": "production", "requests": 2 }],
      "models": [{ "modelAlias": "nova-micro", "requests": 2 }]
    }
  ]
}
```

### The fields

| Top level | Notes |
|---|---|
| `from`, `to`, `projectId`, `status` | The window and filters that were applied, echoed back. A bare `to` date covers the whole of that day. |
| `total*` | `Requests`, `InputTokens`, `OutputTokens`, `CostPaise` across every outcome. |
| `succeeded*`, `failed*` | The same four numbers each, split by outcome. `failed*` covers everything that is not a success, `provider_error` included. That is wider than the `?status=failed` filter, which matches the stored `Failed` status only. |

| Array | One entry per | Fields |
|---|---|---|
| `rows` | day, project and model | `day`, `projectId`, `projectName`, `modelAlias`, then `requests`, `inputTokens`, `outputTokens`, `costPaise`, `succeededRequests`, `failedRequests`, `succeededCostPaise`, `failedCostPaise`, `failedInputTokens`, `failedOutputTokens`. |
| `byDay` | day | `day`, then `requests`, `inputTokens`, `outputTokens`, `costPaise`, `succeededRequests`, `failedRequests`, `succeededCostPaise`, `failedCostPaise`. |
| `byModel` | model alias | `modelAlias` and the same eight numbers as `byDay`. Dearest first. |
| `byStatus` | outcome | `status`, `requests`, `inputTokens`, `outputTokens`, `costPaise`. |
| `failures` | error code | `errorCode`, `description`, `requests`, `costPaise`, `lastSeen`, `projects[{ projectId, projectName, requests }]`, `models[{ modelAlias, requests }]`. |

What matters when you read it:

- **Totals cover every outcome.** `succeeded*` and `failed*` split the same totals, so
  never add them together.
- **A failure can carry real cost**, but only one kind does: a client abort that settled
  against streamed output. Everything else failed at 0 paise.
- **`byDay`, `byModel` and `byStatus`** are the same numbers grouped three ways.
  `byStatus` always returns all three statuses, zero-filled when absent, and a `status`
  filter zero-fills the two it excluded rather than dropping them.
- **`failures`** groups non-succeeded requests by error code, most frequent first, with a
  plain description, when it was last seen, and per-project and per-model counts. That is
  the fastest way to find out what is going wrong.
- **Rejections before the wallet hold are not here.** `invalid_request`, `unknown_model`,
  `manifold_disabled`, `invalid_api_key` and `project_archived` are answered but not
  recorded.

Leave `status` off to see every failure at once: `failures` already groups them by code,
and the filter would hide whichever group you did not ask for.

```bash
curl -s "https://api.tristack.tech/api/v1/usage" \
  -H "Authorization: Bearer $TRISTACK_JWT" | jq '.failures'
```

## Account endpoints

The rest of `/api/v1/account/...` mirrors the sign-up flow. They exist for the dashboard,
and there is rarely a reason to call them from a service, with one exception noted below.

| Endpoint | Auth | Body | Returns |
|---|---|---|---|
| `POST /api/v1/account/register` | none | `{ email, password, displayName }`, password at least 8 characters | The same object as `login`. `409` if the address is already registered. |
| `POST /api/v1/account/login` | none | `{ email, password }` | `{ token, userId, email, displayName, emailVerified }` |
| `POST /api/v1/account/verify-email` | none | `{ email, token }` | `{ message }` |
| `POST /api/v1/account/resend-verification` | JWT | none | `{ message }`. The only one here that needs a token. |
| `POST /api/v1/account/forgot-password` | none | `{ email }` | `{ message }`, always `200`. |
| `POST /api/v1/account/reset-password` | none | `{ email, token, newPassword }` | `{ message }`. Completing a reset also verifies the address. |
| `GET /api/v1/account/profile` | JWT | none | `{ userId, email, displayName, emailVerified, createdAt }` |

The dashboard sign-up form also offers federated sign-in, which has an endpoint of its own.
It takes an identity token minted in the browser, so there is nothing a script can do with
it.

`GET /api/v1/account/profile` is the exception worth knowing: `emailVerified` gates topping
up the wallet, and this is the only way to read it from code. A provisioning script that
checks it before calling `POST /api/v1/wallet/topup` gets a clear answer instead of a
`403`.

Two behaviours are worth knowing because they look like bugs otherwise:

- `forgot-password` always answers `200`, whether or not the address is registered. So
  does `verify-email` failure handling, which gives one generic `400` for an unknown
  email, a wrong token and an expired token alike. Both are anti-enumeration measures.
- Registering returns a session token immediately, even before the email is verified.
  Verification gates the sensitive actions, such as topping up the wallet, rather than
  logging in.
