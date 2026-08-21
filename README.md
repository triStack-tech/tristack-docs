# Tristack documentation

Source for the public Tristack developer documentation. It covers Manifold and Relay Voice.

The site is written for [Mintlify](https://mintlify.com). Pages are `.mdx` files at the top
level of the repo, and the navigation is `docs.json`. A page that is not listed in
`docs.json` is not in the navigation.

## Pushing does not publish yet

Read this before you expect a change to appear anywhere.

Mintlify is a hosted service. It does not produce a folder of HTML to deploy, so
there is nothing for GitHub Pages to serve and no build step that would put one there.
Publishing needs the repository connected at [mintlify.com](https://mintlify.com), through
their GitHub App, and Mintlify then builds and hosts the site itself on every push to
`main`.

The MkDocs site that used to be published here has been deleted, along with `mkdocs.yml`,
`docs/`, `includes/`, `requirements.txt` and the workflow that deployed it. It was serving
prices from before the margin existed, roughly 10 percent under what the API actually
billed, and keeping a second set of pages accurate in parallel is how that happened.

Anything still pointing at <https://tristack-tech.github.io/tristack-docs/> needs
repointing at the Mintlify address, including the links on the marketing site and the Docs
link in the dashboard.

## Working on it locally

```bash
npx mint dev      # live preview on http://localhost:3000
```

Needs Node 19 or newer. `mint dev` reads `docs.json` and the `.mdx` files directly; there
is no install step and no build output.

Two things it will not catch, because they are structural rather than visual:

```bash
npx mint broken-links          # links that go nowhere
python tools/verify_snippets.py  # the generated price tables, and the pages that import them
```

## Layout

```text
docs.json             The site: theme, navigation, navbar, footer
index.mdx             The landing page
manifold/             Manifold pages
relay-voice/          Relay Voice pages
platform/             What both products share: projects, keys, wallet, errors, support
api-reference/        Endpoint reference
changelog.mdx         Changelog
snippets/             Generated markdown, imported into pages. Never edited by hand
assets/               Wordmark and favicon, referenced from docs.json
data/models.json      A captured GET /v1/manifold/models response
tools/                The capture, the generator, and the checks
.github/workflows/    The weekly catalog refresh
```

## Updating the model and pricing tables

Every price on the site comes from `data/models.json`. Nothing is typed by hand.

`tools/generate_pricing.py` turns that capture into `snippets/*.mdx`, which a page picks up
with an import:

```mdx
import ModelCatalog from '/snippets/model-catalog.mdx';

<ModelCatalog />
```

The four snippets are `model-catalog.mdx` (every alias with its rates), `model-vision.mdx`
(the aliases that accept images), `model-budget.mdx` (the ten cheapest servable aliases) and
`catalog-summary.mdx` (the one-line summary above the tables).

`.github/workflows/catalog-refresh.yml` captures the catalog every Monday and opens a pull
request listing what moved: models added, removed, renamed or reprised. If nothing moved it
opens nothing. Run it on demand from the Actions tab. It needs one repository secret,
`TRISTACK_CATALOG_API_KEY`, holding an API key from the dashboard (Settings > Secrets and
variables > Actions > New repository secret). Without the secret the run stops on its first
step and says so in the run summary.

The same refresh by hand, for a local run:

```bash
TRISTACK_API_KEY=... python tools/fetch_catalog.py
python tools/generate_pricing.py
python tools/verify_snippets.py
```

Commit `snippets/` with `data/models.json`.

A few things the catalog response does not report are tracked in
`tools/generate_pricing.py`, documented at the constants themselves: which aliases accept
images, which are switched off on the deployment, and which family each belongs to. The
script fails rather than guessing when they fall out of step with the catalog.

### When the refresh fails

| It says | It means |
|---|---|
| The catalog key is missing | Add the `TRISTACK_CATALOG_API_KEY` secret and run it again. |
| The generator rejected the new catalog | A new alias needs a family in `FAMILIES`, and a decision about `VISION_ALIASES` and `PENDING_ALIASES`. |
| A rate does not survive rendering | The catalog carries a price at a precision the table cannot print. Widen the renderer rather than rounding the price. |
| `imports X but never renders <X />` | A page imports a snippet and does not use it, so that table is missing from the published page. |
| `No page imports ...` | A note, not a failure. The tables are generated and committed but no page shows them. Either import them, or delete the generator and let the pages send readers to `GET /v1/manifold/models` for live prices. |

## What checks a change before it publishes

Mintlify builds whatever is on `main`, correct or not. There is no staging step, so
`.github/workflows/docs-check.yml` is the only thing standing between a broken page and the
published site. It runs on every push and pull request:

- `python tools/verify_snippets.py` — every snippet import resolves, every imported snippet
  is actually rendered, and no MkDocs syntax survived the migration.
- `npx mint broken-links` — every internal link and anchor resolves against `docs.json`.

If either fails on `main`, the site has already published the broken version. Fix forward.
