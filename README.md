# TriStack documentation

Source for the public TriStack developer documentation, built with
[MkDocs](https://www.mkdocs.org/) and the
[Material](https://squidfunk.github.io/mkdocs-material/) theme.

It covers TriStack Manifold today. Other TriStack products will be added here as they ship.

## Layout

```text
mkdocs.yml            Site configuration, theme, navigation
docs/                 The pages
includes/             Generated markdown fragments, pulled in with the snippets syntax
data/models.json      A captured GET /v1/manifold/models response
tools/                The generator that turns data/models.json into includes/
.github/workflows/    Build on every push, deploy to GitHub Pages from main
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

```bash
curl -s https://api.tristack.tech/v1/manifold/models \
  -H "Authorization: Bearer $TRISTACK_API_KEY" > data/models.json
python tools/generate_pricing.py
```

That rewrites the files in `includes/`. Commit `data/models.json` and `includes/` together.
CI regenerates them and fails if the committed output is stale, so the published tables
always match the captured catalog.

A few things the catalog response does not report are tracked in
`tools/generate_pricing.py`, documented at the constants themselves. The script fails
rather than guessing when they fall out of step with the catalog.

## Deployment

`.github/workflows/docs.yml` builds on every push and pull request, and deploys `main` to
GitHub Pages, which is set to build from GitHub Actions.
