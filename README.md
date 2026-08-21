# Tristack documentation

Source for the public Tristack developer documentation. It covers Manifold and Relay Voice.

The site is written for [Mintlify](https://mintlify.com). Pages are `.mdx` files at the top
level of the repo, and the navigation is `docs.json`. A page that is not listed in
`docs.json` is not in the navigation.

## Pushing does not publish yet

Read this before you expect a change to appear anywhere.

Mintlify is a hosted service. It does not produce a folder of HTML the way MkDocs did, so
there is nothing for GitHub Pages to serve and no build step that would put one there.
Publishing needs the repository connected at [mintlify.com](https://mintlify.com), through
their GitHub App, and Mintlify then builds and hosts the site itself on every push to
`main`.

Until that connection exists:

- Pushing changes nothing that a reader can see.
- The site the public reads is still the MkDocs one at
  <https://tristack-tech.github.io/tristack-docs/>, built and deployed by
  `.github/workflows/docs.yml` from `mkdocs.yml` and `docs/`.
- Once Mintlify is connected, the published address changes. It will be a Mintlify address,
  or a custom domain pointed at Mintlify, and not the `github.io` one above. Every link
  that points at the old address has to be updated, including the ones on the marketing
  site.

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
.github/workflows/    The weekly catalog refresh, and the MkDocs build that still deploys

mkdocs.yml            The old site, still published. See "The MkDocs files" below
docs/                 The old pages
includes/             The same generated tables, in the form MkDocs wanted
requirements.txt      MkDocs and its theme
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

Commit `snippets/` and `includes/` with `data/models.json`.

A few things the catalog response does not report are tracked in
`tools/generate_pricing.py`, documented at the constants themselves: which aliases accept
images, which are published but not servable yet, and which family each belongs to. The
script fails rather than guessing when they fall out of step with the catalog.

### When the refresh fails

| It says | It means |
|---|---|
| The catalog key is missing | Add the `TRISTACK_CATALOG_API_KEY` secret and run it again. |
| The generator rejected the new catalog | A new alias needs a family in `FAMILIES`, and a decision about `VISION_ALIASES` and `PENDING_ALIASES`. |
| A rate does not survive rendering | The catalog carries a price at a precision the table cannot print. Widen the renderer rather than rounding the price. |
| `imports X but never renders <X />` | A page imports a snippet and does not use it, so that table is missing from the published page. |
| `No page imports ...` | A note, not a failure. The tables are generated and committed but no page shows them. Either import them, or delete the generator and let the pages send readers to `GET /v1/manifold/models` for live prices. |

## The MkDocs files

`mkdocs.yml`, `docs/`, `includes/` and `requirements.txt` are still here on purpose. They
are the site the public currently reads, and deleting them before Mintlify is connected
would take the documentation offline.

While they exist, everything keeps working the way it did: `docs.yml` builds and deploys
the MkDocs site on every push to `main`, and `tools/generate_pricing.py` writes the tables
twice, once as `snippets/*.mdx` for Mintlify and once as `includes/*.md` for MkDocs, so a
price refresh updates both sites rather than leaving one of them quoting last month.

### Once Mintlify is connected and its address is the published one

Delete, in one commit:

```text
mkdocs.yml
docs/                            (assets/ already holds copies of docs/assets/)
includes/
requirements.txt
tools/verify_tables.py           (it parses the built MkDocs HTML, which will not exist)
.github/workflows/docs.yml       (it builds and deploys that site)
```

Then turn GitHub Pages off under Settings > Pages, and delete the local `.venv` and `site/`
if you have them.

Two things happen on their own when `mkdocs.yml` goes, so nothing else needs editing:

- `tools/generate_pricing.py` stops writing `includes/` and writes only `snippets/`.
- `catalog-refresh.yml` drops its MkDocs build and starts running `npx mint broken-links`
  instead, which is held back until then because the old `docs/` pages link to each other
  by `.md` filename and Mintlify cannot resolve those.

One gap to close while both sites exist: `docs.yml` regenerates the tables on every push
and fails if `includes/` came out different from what was committed, but it does not make
the same check on `snippets/`. Adding `snippets/` to that `git diff --exit-code` line
covers both. When you delete `docs.yml`, replace it with a workflow that runs
`npx mint broken-links` and `python tools/verify_snippets.py` on pull requests: Mintlify
builds whatever is on `main`, correct or not, so that workflow is what stops a broken page
reaching it.
