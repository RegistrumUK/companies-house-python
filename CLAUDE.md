# companies-house-python - Claude Code Instructions

PyPI package `companies-house` (import `companies_house`): a Companies House API client with an
optional Registrum upgrade path. Sibling repo in the claude-ch-proj workspace; parent issue
RegistrumUK/registrum-website#183 (item 4). Policy only, no stored state.

## Rules

- **TDD.** Failing test first. **Fixtures are real captured responses** (`scripts/capture_fixtures.py`,
  needs `CH_API_KEY` and `REGISTRUM_API_KEY` in the environment); never hand-author a success body for
  an external API. Tests may override status or headers on a real fixture. The one exception is
  Registrum's 403 TRIAL_UNVERIFIED body, whose source is `ch-enrichment-api/src/api/middleware.py`.
- **Never create real trials in tests** and never commit a key. Keys come from `secret.py get`.
- **The User-Agent is the attribution channel.** Registrum logs it to see which client calls. Change
  it deliberately, in `_version.py`/`_http.py`, never by accident; a test pins its shape.
- **YAGNI.** Sync only, plain dicts, one dependency. No model layer, no async until asked.
- **README is customer-facing.** Read the `registrum-landscape` skill before editing it. State no
  prices, quotas or trial length; link to https://registrum.co.uk/pricing. No em dashes, emojis or hype.
- **Rate-limit facts come from captured headers**, not memory: CH reports its own limit and an epoch
  `X-Ratelimit-Reset`; Registrum's reset can be a month away and must not be slept on.

## Shipping

Releases are tags `v*.*.*` through PyPI Trusted Publishing (`.github/workflows/publish.yml`), no
tokens. Bump `src/companies_house/_version.py` and `CHANGELOG.md` first. Verify a release by
installing it from PyPI into a fresh venv and calling both APIs. Open issues are the backlog.

## Commits

Every commit `refs #N` / `closes #N`.
