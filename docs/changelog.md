---
title: Changelog
description: Changes to the Tristack API and to this documentation.
---

# Changelog

Changes to the API and to these pages, newest first. Dates are the day the change went
live.

Additive changes (new fields on a response, new models in the catalog, new optional
request fields) do not change the `/v1` path. Parse leniently and ignore fields you do not
recognise.

## 2026-08-17

First public release of the documentation, describing Tristack Manifold as it runs today.

**API surface**

- `POST /v1/manifold/messages`: text and image messages, optional `system` prompt,
  `max_tokens` (default 4096, cap 65536), `temperature`, `top_p`, `stop_sequences`, and
  `stream` for server-sent events.
- `GET /v1/manifold/models`: the catalog with per-model rates in USD per million tokens
  and paise per 1000 tokens, plus the `usdToInr` rate used to convert them.
- API-key authentication on both, as `Authorization: Bearer tsk_...` or `X-Api-Key`.

**Catalog**

- 54 aliases across 19 families, converted at 90.0 INR per USD.
- Five aliases are published but not servable yet: `opus-5`, `opus-4-8`, `sonnet-5`,
  `sonnet-4-6` and `haiku-4-5`. Account-level access is still being finalised, and calls to
  them answer `403 model_access_denied`. The other 49 serve normally.
- 21 aliases accept image blocks. The list is on the
  [vision page](guides/vision.md#models-that-accept-images).

**Billing**

- Prepaid wallet per account, in integer paise, minimum top-up 10000 paise (Rs 100).
- Hold before the call, settle on real token usage afterwards, difference returned.
- Failed calls cost nothing. A client abort mid-stream settles, for the whole input
  estimate plus whatever output had been delivered.

**Documentation**

- Getting started, authentication, streaming, vision, the full API reference, the error
  catalog, the model catalog, the billing model and how to get support.
- Model and price tables are generated from a captured `GET /v1/manifold/models` response,
  so they match the deployment they were captured from.
