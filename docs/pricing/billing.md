---
title: Pricing and billing
description: How the prepaid wallet, the hold, and the settlement work, worked through with real numbers.
---

# Pricing and billing

## The short version

- One **prepaid wallet per account**, shared by every project under it.
- Everything is **integer paise**. Rs 1 = 100 paise. No floats, no rupee amounts.
- Before a call, an **estimate is held**. After it, the **real usage is settled**: the
  difference is returned, or the shortfall taken, as the case may be.
- A **failed call costs nothing**, with one exception (an aborted stream).
- Every response tells you what it cost, in `cost.paise`.

## The price of a call

```text
costPaise = ceil(
    (inputTokens * usdPerMTokIn + outputTokens * usdPerMTokOut)
    / 1e6 * usdToInr * 100
)
```

`usdPerMTokIn`, `usdPerMTokOut` and `usdToInr` all come from
[`GET /v1/manifold/models`](../api/models.md). The rounding up to a whole paise happens
once, at the very end, so any call that used tokens costs at least 1 paise.

That is the whole pricing model. There is no per-request fee, no minimum billable token
count, no separate charge for images, and no difference in price between a streamed and a
non-streamed call.

## Hold, then settle

Token usage is only known after a model has run, so charging up front would mean guessing
and charging users wrong. Instead:

```text
1. Estimate     ->  hold that much of the balance
2. Call the model
3. Settle       ->  debit the real cost, return the rest of the hold
```

**The hold** is deliberately pessimistic. It assumes the reply uses every one of your
`max_tokens`, and it estimates input tokens at 4 characters per token across your `system`
prompt, all message text and any base64 image data:

```text
estimatedInput  = ceil(billableCharacters / 4)
estimatedOutput = max_tokens

holdPaise = max(1, ceil(
    (estimatedInput * usdPerMTokIn + estimatedOutput * usdPerMTokOut)
    / 1e6 * usdToInr * 100
))
```

`max_tokens` is optional, and the hold is priced on whatever value ends up applying: omit
it and the default of **4096** is used, and anything above the cap of **65536** is clamped
to the cap first. The default matters more than it looks. On `mistral-large`, a 24
character prompt with no `max_tokens` holds 443 paise; the same call with
`max_tokens: 1024` holds 111.

If the balance cannot cover the hold, the call is rejected with
`402 insufficient_balance` and `requiredPaise` set to the hold. Nothing reaches a model,
and nothing is charged.

**The settlement** replaces the estimate with the truth. The whole hold comes back and the
real cost from the formula above is debited, so the balance nets out at the remainder. Both
movements land in the [transaction ledger](../api/dashboard.md#wallet) against the same
`mfr_...` request id, as a `HoldRelease` for the full hold and a `Debit` for the cost.

!!! note "The hold is an estimate, not a ceiling"

    4 characters per token over-counts Latin text and under-counts dense scripts, so a
    settled cost above the hold is possible: 2000 characters of Devanagari on `nova-lite`
    with `max_tokens: 1024` holds 3 paise and can settle at 4. When that happens the
    `Debit` line is larger than the `Hold` line and the extra comes out of the balance
    rather than being refused, because the call has already run. If the balance cannot
    cover the overage, the debit is capped at what is there and the remainder is written
    off, never taken into a negative balance.

Holds are per call and overlap. Ten concurrent requests hold ten estimates at once, so a
balance that covers one call comfortably can still refuse the tenth.

## A worked example

The response on the [home page](../index.md) is a real one. Here is the money behind it.

The request: `nova-micro`, `max_tokens: 1024`, one user message reading
`Say hello from TriStack.` (24 characters).

`nova-micro` is priced at **0.035 USD per million input tokens** and **0.14 USD per
million output tokens**, converted at **90 INR per USD**.

### Step 1: the hold

| Term | Value |
|---|---|
| Billable characters | 24 |
| Estimated input tokens, `ceil(24 / 4)` | 6 |
| Estimated output tokens, from `max_tokens` | 1024 |
| Input part, `6 * 0.035` | 0.21 |
| Output part, `1024 * 0.14` | 143.36 |
| Sum, in USD, `(0.21 + 143.36) / 1e6` | 0.00014357 |
| In INR, `* 90` | 0.01292 |
| In paise, `* 100`, rounded up | **2 paise** |

2 paise leaves the available balance and sits in a hold.

### Step 2: the call

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

The model counted 10 input tokens where the estimate guessed 6, and wrote 6 output tokens
where the estimate allowed 1024. Both directions of error are normal: 4 characters per
token is a rough rule, and `max_tokens` is a ceiling rather than a prediction.

### Step 3: the settlement

| Term | Value |
|---|---|
| Input part, `10 * 0.035` | 0.35 |
| Output part, `6 * 0.14` | 0.84 |
| Sum, in USD, `(0.35 + 0.84) / 1e6` | 0.00000119 |
| In INR, `* 90` | 0.0001071 |
| In paise, `* 100`, rounded up | **1 paise** |

1 paise is debited and 1 paise returns to the balance. The ledger shows that as three
lines against the same request id: `Hold` 2 paise, then `HoldRelease` 2 paise, the whole
hold coming back, then `Debit` 1 paise, the settled cost taken from the returned money.
The release line is never the unused remainder, so read the `Debit` line for what a call
actually cost.

### The same request on a dearer model

Nothing changes except the rate. `nova-pro`, at 0.80 and 3.20 USD per million tokens,
would hold **30 paise** for the same `max_tokens: 1024`, and a reply of 12 input and 210
output tokens would settle at **7 paise**, returning 23.

That gap between hold and settlement is why a tight `max_tokens` is worth setting. It does
not change the price of the tokens you use, but it stops the wallet reserving money for an
answer you were never going to receive.

## What a failure costs

Nothing, with one exception.

| Outcome | Charge |
|---|---|
| Rejected before the hold: bad key, Manifold off, invalid body, unknown model | 0. The wallet is never touched. |
| `insufficient_balance` | 0. The hold could not be placed. |
| `provider_throttled`, `provider_rejected`, `model_access_denied`, `provider_error` | 0. The hold is released in full. |
| You aborted before any output arrived | 0. The hold is released in full. |
| You aborted after part of a stream arrived | The whole input estimate, exactly as the hold priced it, plus the delivered output, also estimated at 4 characters per token and capped at `max_tokens`. |
| Success | The real token cost. |

The exception exists so that "abort just before the end" is not a way to get free
inference. A model failure is not your doing and costs you nothing; hanging up on output
you already received does.

Note which half of that estimate moves. The output half shrinks with how little arrived;
the input half does not shrink at all, because the model read your prompt whether or not
you stayed to hear the answer. Aborting the 200 KiB image call from
[what images cost](../guides/vision.md#what-images-cost) after a line or two of output
settles at 37 paise, not the 1 paise the delivered text alone would suggest.

Retrying a failed call is therefore free apart from latency. Retry `429` and `502` with
backoff, without worrying about double charging.

## Adding money

Top-ups happen in the dashboard, through the checkout flow.

| Rule | Value |
|---|---|
| Minimum top-up | 10000 paise (Rs 100) |
| Unit | Integer paise |
| Requirement | A verified email address |

An unverified account answers `403 email_unverified` on a top-up. Resend the verification
mail from the dashboard, click the link, and try again. The link is valid for 48 hours.

Payment is confirmed in two independent ways: the browser hands the signed result back,
and the payment provider posts a webhook. Whichever arrives first credits the wallet, and
the other is ignored, so a credit is never applied twice. If a payment leaves your bank
but the balance has not moved, wait a minute: a reconciliation sweep settles anything the
other two paths missed.

A wallet cannot be funded end to end from a script. The dashboard API can create the
top-up order and confirm a paid one, but paying it happens in the browser checkout, so
there is no headless path from an empty wallet to a funded one. See
[the wallet endpoints](../api/dashboard.md#wallet). Note also what cannot do any of this:
an API key. Keys reach `/v1/manifold/...` only, so a leaked key cannot buy anything.

## Reading what you spent

### In the response

`cost.paise` on every completion, and in the `message_delta` event of every stream. This
is the settled amount, not the estimate. It is the cheapest way to attribute cost to a
feature in your own product: log it next to the `id`.

One case makes it larger than what the wallet actually gave up. If the settled cost
exceeds the balance left, the `Debit` line is capped at the available balance and carries a
`description` saying so, while `cost.paise` and the usage totals still report the full
figure. On a wallet with money in it the two always agree; on one that ran dry mid-call,
read the ledger for what was taken.

### In the dashboard

The usage view groups requests by day, project and model, and separates successes from
failures. Read the two apart rather than summing them: a failed request usually carries
zero tokens and zero cost, so mixing them into one "requests" number hides the failure
rate.

### Through the API

- [`GET /api/v1/wallet`](../api/dashboard.md#wallet) for the balance. Alarm on it before
  it reaches zero.
- [`GET /api/v1/wallet/transactions`](../api/dashboard.md#wallet) for the ledger, one line
  per movement, each carrying the `mfr_...` reference.
- [`GET /api/v1/usage`](../api/dashboard.md#usage) for aggregates by day, project, model
  and outcome, plus a `failures` breakdown by error code.

## Keeping the bill down

1. **Pick the smallest model that passes your own evaluation.** The catalog spans more
   than a hundredfold in price per token. Nothing else you do will match that.
2. **Set `max_tokens` to what you need.** It caps the hold, and it caps runaway replies.
3. **Send less input.** Long system prompts are charged on every single call. Trim them
   once and the saving repeats forever.
4. **Downscale images.** Image bytes become base64 characters, which become a large hold.
   See [what images cost](../guides/vision.md#what-images-cost).
5. **Watch output-heavy workloads.** Output usually costs several times what input costs,
   so "make it shorter" is often a bigger saving than "send less context".
6. **Keep the balance to what the workload needs.** A prepaid wallet caps what a leaked
   key can spend.
