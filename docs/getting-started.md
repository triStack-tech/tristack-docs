---
title: Getting started
description: From an empty account to a first Manifold response, with the error each skipped step produces.
---

# Getting started

Six steps take you from nothing to a billed response. Each step below lists what the
screen expects and the error you get if you skip it.

You need a browser for steps 1 to 5 and a terminal for step 6.

## 1. Create an account

Go to [tristack.tech](https://tristack.tech) and sign up with an email address and a
password, or with one of the federated sign-in buttons on the form.

- The password must be at least 8 characters.
- Signing up creates your user, your account, and a wallet holding 0 paise, all at once.
- You are signed in immediately. The session token is valid for 24 hours.

**Verify your email.** A verification link is sent on sign-up and is valid for 48 hours.
Federated sign-in verifies the address for you, when the provider has already verified it.
Verification is not needed to browse the dashboard or mint keys, but it *is* needed to add
money to the wallet, so do it now.

!!! failure "If you skip it"

    Topping up answers `403` with `code: "email_unverified"`. Resend the link from the
    dashboard and try again.

## 2. Create a project

In the dashboard, create a project and give it a name of 1 to 128 characters.

A project is the unit everything hangs off:

- API keys belong to a project, never to an account directly.
- Usage and cost are reported per project.
- Product access (Manifold) is switched on per project.

A project is `Active` when created. Archiving it later keeps the record but stops its keys
from working.

## 3. Enable Manifold on the project

Open the project and turn **Manifold** on.

This is a deliberate switch, not a default. A key on a project without it authenticates
correctly and still fails.

!!! failure "If you skip it"

    ```json
    { "error": "Manifold is not enabled for this project.", "code": "manifold_disabled" }
    ```

    HTTP `403`. Turn the toggle on. The change takes effect on the next request, with no
    need to mint a new key.

## 4. Mint an API key

In the project, create an API key. The form asks for two things:

| Field | Expects |
|---|---|
| Name | A label for you, so you can tell keys apart later. |
| Mode | `live` or `test`. This only decides the prefix: `tsk_live_` or `tsk_test_`. |

Both modes call the same models and bill the same wallet. The prefix is a label for your
own bookkeeping, not a sandbox.

!!! danger "The key is shown once"

    The full token appears exactly once, on the screen that creates it. It is stored
    hashed, so nobody, including support, can show it to you again. Copy it into your
    secret manager or `.env` file before you close the dialog.

    Afterwards the dashboard shows only the prefix and the last 4 characters, enough to
    identify a key but not to use it. If you lose a key, revoke it and mint another.

Put it in your environment:

```bash
export TRISTACK_API_KEY="tsk_live_your_key_here"
```

## 5. Top up the wallet

The wallet is prepaid and belongs to your account, shared by every project under it. Add
money in the dashboard through the checkout flow.

- Minimum top-up: **10000 paise (Rs 100)**.
- All amounts everywhere in the API are integer paise. Rs 1 = 100 paise.
- Your email must be verified (step 1).

The balance is charged per call, in paise, at the rates on the
[model catalog](pricing/models.md) page. Small models are cheap: the first request below
costs 1 paise.

!!! failure "If you skip it"

    ```json
    {
      "error": "The wallet balance cannot cover the estimated cost of this request.",
      "code": "insufficient_balance",
      "requiredPaise": 2
    }
    ```

    HTTP `402`. `requiredPaise` is what this specific call needed up front, not your
    account balance. Nothing is charged: the request never reaches a model. Top up, then
    retry.

## 6. Make the first call

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

    response = requests.post(
        "https://api.tristack.tech/v1/manifold/messages",
        headers={"Authorization": f"Bearer {os.environ['TRISTACK_API_KEY']}"},
        json={
            "model": "nova-micro",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": "Say hello from TriStack."}],
        },
        timeout=60,
    )
    if response.status_code != 200:
        # raise_for_status() would throw away the body, and the body is where the
        # code and requiredPaise this page tells you to read actually live.
        failure = response.json()
        raise RuntimeError(f"{response.status_code} {failure['code']}: {failure['error']}")

    body = response.json()
    print(body["content"][0]["text"])
    print(body["usage"], "cost:", body["cost"]["paise"], "paise")
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
        model: "nova-micro",
        max_tokens: 1024,
        messages: [{ role: "user", content: "Say hello from TriStack." }],
      }),
    });

    if (!response.ok) {
      const failure = await response.json();
      throw new Error(`${response.status} ${failure.code}: ${failure.error}`);
    }

    const body = await response.json();
    console.log(body.content[0].text);
    console.log(body.usage, "cost:", body.cost.paise, "paise");
    ```

A successful response:

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

Keep `id` if you log anything: it is the request id used in the wallet ledger and in
support conversations.

## What to read next

- [Authentication](guides/authentication.md) before you deploy the key anywhere.
- [Create a message](api/messages.md) for every parameter the request accepts.
- [Streaming](guides/streaming.md) to show tokens as they arrive instead of waiting.
- [Pricing and billing](pricing/billing.md) to understand the 1 paise above.

## Troubleshooting the first call

| Symptom | Cause | Fix |
|---|---|---|
| `401 invalid_api_key` | Key missing, mistyped, revoked, or from a deleted project. | Check the header. `Authorization: Bearer tsk_live_...` with a single space, no quotes, no trailing newline. |
| `401 project_archived` | The key's project was archived. | Unarchive the project or use a key from an active one. |
| `403 manifold_disabled` | Step 3 was skipped. | Enable Manifold on the project. |
| `402 insufficient_balance` | Step 5 was skipped, or the balance ran out. | Top up. `requiredPaise` says what this call needed. |
| `400 unknown_model` | The alias does not exist in this deployment. | Fetch [`GET /v1/manifold/models`](api/models.md) and copy an alias from it. |
| `403 model_access_denied` | The alias exists but is not servable here yet. | Pick another alias. See the [catalog](pricing/models.md). |

The full list is on the [errors page](api/errors.md).
