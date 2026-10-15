# User journeys

Every feature maps to one of these.

## J1 - Developer with their own CH key hitting 429s
1. Has a CH key and a script looping over company numbers; gets 429s and fears a ban.
2. `pip install companies-house`, swaps in `CompaniesHouse(key)`.
3. The client reads X-Ratelimit-* headers, waits for the window instead of erroring, retries
   transient 5xx, and raises a clear `RateLimited` only if waiting would exceed `max_wait`.
Features: Transport rate-limit logic, `iter_*` helpers, number normalisation, `AuthError` hint.

## J2 - Developer who needs turnover or the real owner
1. Finds the official API returns no figures and one PSC level at a time.
2. README's "Need financials or ownership chains?" shows the same code with `Registrum`.
3. Calls `financials()` and `psc_chain()`.
Features: `Registrum.company/search/financials/psc_chain/bundle`.

## J3 - Trial by email
1. Has no Registrum key. Calls `Registrum().start_trial("me@example.com")`.
2. Gets a key back, clicks the emailed link.
3. Until then every call raises `TrialUnverified` saying to click the link.
Features: `start_trial` with source "pypi", `TrialUnverified`.
