---
title: Authentication
description: API key formats, both accepted headers, rotation and revocation, and where a key must never be shipped.
---

# Authentication

Every Manifold call is authenticated with a project API key. There are no other
credentials on the product surface: no signatures, no timestamps, no client secrets.

## The two headers

Send the key either way. Both are equivalent.

=== "Authorization"

    ```http
    POST /v1/manifold/messages HTTP/1.1
    Host: api.tristack.tech
    Authorization: Bearer tsk_live_your_key_here
    Content-Type: application/json
    ```

=== "X-Api-Key"

    ```http
    POST /v1/manifold/messages HTTP/1.1
    Host: api.tristack.tech
    X-Api-Key: tsk_live_your_key_here
    Content-Type: application/json
    ```

Rules worth knowing:

- `Authorization` must use the `Bearer ` scheme, one space, then the token.
- A bearer value that does not start with `tsk_` is treated as a dashboard session token,
  not an API key, and will not authenticate a Manifold call. If you get `401` while
  holding a valid key, check that you did not paste a JWT.
- If both headers are present, `Authorization: Bearer tsk_...` wins.
- The token is never stored. Only its SHA-256 hash is kept, and authentication looks the
  presented key up by that hash.

## Key format

A key is the prefix followed by 43 characters of base64url, from 32 random bytes.

```text
tsk_live_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
└───┬───┘└─────────────────────┬─────────────────────┘
  prefix              43-character secret
```

| Prefix | Meaning |
|---|---|
| `tsk_live_` | Minted in `live` mode. |
| `tsk_test_` | Minted in `test` mode. |

!!! note "Test keys are not a sandbox"

    Mode picks the prefix and nothing else. A `tsk_test_` key calls the same models and
    debits the same wallet as a `tsk_live_` key. Use the prefix to keep your staging and
    production keys visibly apart, not to avoid charges.

## What a key carries

A key is bound to exactly one project, and the project decides what the key can do:

| Condition | Result |
|---|---|
| Key is active, project `Active`, Manifold enabled | The call proceeds. |
| Key unknown, mistyped, or revoked | `401 invalid_api_key` |
| Project archived | `401 project_archived` |
| Manifold not enabled on the project | `403 manifold_disabled` |

Unknown and revoked keys give the same answer on purpose. A distinct "this key was
revoked" response would confirm to whoever holds a leaked key that it was once real.

Billing is per account, not per key. Keys in different projects under one account draw on
the same wallet; usage is attributed to the project the key belongs to.

## Creating, rotating and revoking

Keys are managed per project in the dashboard, or through the
[dashboard API](../api/dashboard.md) if you automate it.

**Create.** Give the key a name and a mode. The full token is shown once, at creation, and
is stored only as a hash. Afterwards you can see the prefix and the last 4 characters,
which is enough to identify a key in a list but not to use it.

**Rotate.** Rotation is two keys living side by side for a moment:

1. Mint a new key in the same project.
2. Deploy it to every service that calls the API.
3. Confirm the old key has stopped being used. The dashboard shows a last-used timestamp
   per key. It is written periodically rather than on every call, so give it a few minutes
   before you read anything into it.
4. Revoke the old key.

**Revoke.** Revocation takes effect on the next request. In-flight calls finish. A revoked
key never comes back, so revoking is the correct response to any doubt about a key.

## Keeping keys safe

A Manifold key spends money from your wallet. Treat it like a password with a balance
attached.

- **Server side only.** Call the API from your backend. A key in a browser bundle, a
  mobile app, a desktop app, or anything else a user can unpack is a key you have given
  away, however obfuscated.
- **Never in source control.** Use environment variables or a secret manager. If a key
  reaches a repository, revoke it: rewriting history does not un-share it.
- **One key per deployment.** Separate keys for production, staging and each developer
  make it possible to revoke one without an outage.
- **Rotate on exposure.** A key pasted into a chat, a log, a screenshot or a support
  ticket is exposed. Mint, deploy, revoke.
- **Do not log the key.** Log the `id` from the response (`mfr_...`) instead. It
  identifies the request without identifying the credential.
- **Watch the wallet.** A prepaid balance caps the damage of a leak: an attacker can only
  spend what is loaded. Keep the balance to what your workload actually needs.

## Building a browser or mobile client

Put your own endpoint in front. Your app authenticates your user with your own session,
your backend holds the Tristack key, and your backend calls Manifold. That also gives you
the place to enforce per-user limits, which the API key alone cannot express.

## Dashboard API authentication

The `/api/v1/...` endpoints that back the dashboard use a JWT from
`POST /api/v1/account/login`, sent as `Authorization: Bearer <jwt>`, valid for 24 hours.
API keys do not work there, and JWTs do not work on Manifold. See the
[dashboard API page](../api/dashboard.md).
