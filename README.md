# Tristack documentation

Source for the public Tristack developer documentation, built with
[MkDocs](https://www.mkdocs.org/) and the
[Material](https://squidfunk.github.io/mkdocs-material/) theme.

It covers Tristack Manifold today. Other Tristack products will be added here as they ship.

## Layout

```text
mkdocs.yml            Site configuration, theme, navigation
docs/                 The pages
includes/             Generated markdown fragments, pulled in with the snippets syntax
data/models.json      A captured GET /v1/manifold/models response
tools/                The capture and the generator that turns it into includes/
.github/workflows/    Build and deploy, and the weekly catalog refresh
```

## Working on it locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

mkdocs serve            # live preview on http://127.0.0.1:8000
mkdocs build --strict   # what CI runs; fails on broken links and stray files
```

## Updating the model and pricing tables

Every price on the site comes from `data/models.json`. Nothing is typed by hand.

`.github/workflows/catalog-refresh.yml` captures the catalog every Monday and opens a
pull request listing what moved: models added, removed, renamed or reprised. If nothing
moved it opens nothing. Run it on demand from the Actions tab. It needs one repository
secret, `TRISTACK_CATALOG_API_KEY`, holding an API key from the dashboard (Settings >
Secrets and variables > Actions > New repository secret).

The same refresh by hand, for a local run:

```bash
TRISTACK_API_KEY=... python tools/fetch_catalog.py
python tools/generate_pricing.py
```

Commit `includes/` with `data/models.json`. CI regenerates both and fails if the
committed output is stale, so the published tables always match the capture.

A few things the catalog response does not report are tracked in
`tools/generate_pricing.py`, documented at the constants themselves. The script fails
rather than guessing when they fall out of step with the catalog.

## Deployment

`.github/workflows/docs.yml` builds on every push and pull request, and deploys `main` to
GitHub Pages, which is set to build from GitHub Actions.
