# TriStack documentation

The public developer documentation for TriStack Manifold, built with
[MkDocs](https://www.mkdocs.org/) and the
[Material](https://squidfunk.github.io/mkdocs-material/) theme.

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

Three facts live in `tools/generate_pricing.py` rather than in the catalog response,
because the endpoint does not report them:

- `VISION_ALIASES`: which aliases accept image blocks. The script fails if one of them
  disappears from the catalog. This one has no provenance behind it and the vision page
  says so; see the comment above the constant.
- `PENDING_ALIASES`: aliases published but not servable yet. It drives the "not servable
  yet" warning on both the catalog and the vision tables, and excludes those aliases from
  the "cheapest servable models" list. Never restate the pending list by hand in a page:
  it will outlive the entitlement it describes.
- `FAMILIES`: how the catalog is grouped into sections on the page.

All three are keyed on the alias, never on the display name, and the script fails rather
than guessing: an alias in the catalog with no family, an alias mapped here that the
catalog no longer carries, and a missing vision alias each stop the run.

## Deployment

`.github/workflows/docs.yml` builds on every push and pull request, and deploys `main` to
GitHub Pages. Repository settings must have **Pages > Build and deployment > Source** set
to **GitHub Actions**.

**Unresolved: the site's own hostname.** `site_url` in `mkdocs.yml` is
`https://docs.tristack.tech/`, and MkDocs bakes it into every `<link rel="canonical">` and
every `<loc>` in `sitemap.xml` at build time. That name does not resolve today, there is no
`CNAME` file in `docs/`, and the Pages deploy therefore serves the site at a `github.io`
address while every canonical tag points somewhere unreachable. Pick one before the site is
announced anywhere:

- Serve at `docs.tristack.tech`: create the DNS record first, then add a `docs/CNAME` file
  containing `docs.tristack.tech` so it lands in the built artifact. Adding the file before
  the record exists takes the site offline rather than moving it.
- Or set `site_url` to the address the deploy actually serves.

## House rules for this content

- Name models, never infrastructure. Model display names come from the API as-is; the
  systems behind them are not part of the public documentation. This covers vendors of
  every kind, not just model providers: the sign-in provider and the payment provider are
  described by what they do, never by who they are. Where a literal wire identifier carries
  a vendor's name (a field on a response, an endpoint path, an error code), leave it out of
  the page rather than renaming it, and say what the page needs to say without it. Nothing
  in the docs should be wrong in order to be neutral.
- No em dashes.
- Numbers are either generated from `data/models.json` or verified against the running
  API. No invented benchmarks, statistics or availability claims.
