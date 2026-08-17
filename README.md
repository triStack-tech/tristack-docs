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

Three things live in `tools/generate_pricing.py` rather than in the catalog response,
because the endpoint does not report them:

- `VISION_ALIASES`: which aliases accept image blocks.
- `PENDING_ALIASES`: aliases published but not servable yet. It drives the availability
  warning on the catalog and vision tables and keeps those aliases out of the cheapest
  models list.
- `FAMILIES`: how the catalog is grouped into sections on the page.

All three are keyed on the alias rather than the display name, and the script fails rather
than guessing: an alias in the catalog with no family, an alias mapped here that the
catalog no longer carries, and a missing vision alias each stop the run.

## Deployment

`.github/workflows/docs.yml` builds on every push and pull request, and deploys `main` to
GitHub Pages. Repository settings need **Pages > Build and deployment > Source** set to
**GitHub Actions**.

`site_url` in `mkdocs.yml` is baked into every `<link rel="canonical">` and every `<loc>`
in `sitemap.xml` at build time, so it has to match the address the site is actually served
from. To move the site to `docs.tristack.tech`, create the DNS record first, then add a
`docs/CNAME` file containing the hostname and update `site_url` in the same change. Adding
the file before the DNS record exists takes the site offline rather than moving it.
